import time

from ai.io import attach_game, create_game_io
from core.game import Game
from core.io_interface import GameIO, NeedsInput


class WebGameIO(GameIO):
    """Game input/output handler specific to the web interface"""
    
    def __init__(self):
        self.buffer = []
        self.last_input = ""
        self._pending_input = ""
        self._input_available = False
        self._input_consumed = False

    def show_message(self, text: str):
        """Stores a narrative message in the buffer"""
        self.buffer.append({"type": "narrative", "text": text})

    def show_narration(self, text: str):
        """Stores AI-generated prose separately so clients can style it"""
        self.buffer.append({"type": "narration", "text": text})

    def show_map(self, text: str):
        """Stores preformatted map text so clients keep it monospaced"""
        self.buffer.append({"type": "map", "text": text})

    @property
    def pause_for_confirmation(self) -> bool:
        return False

    @property
    def dialogue_options_in_log(self) -> bool:
        return False

    def system_message(self, text: str):
        """Stores a system message in the buffer"""
        self.buffer.append({"type": "system", "text": text})
    
    def error_message(self, text: str):
        """Stores an error message in the buffer"""
        self.buffer.append({"type": "error", "text": text})
    
    def request_input(self, prompt: str = "") -> str:
        """Returns the pending command once, then asks the caller to wait.

        The engine's states show a prompt and read input in one run, then process
        it in the next. A blocked terminal gives them a second loop iteration;
        over HTTP the prompt has to pause the run instead. ``NeedsInput`` is that
        pause: the prompt is recorded, the run stops, and the next command is
        supplied to the following run.
        """
        self.buffer.append({"type": "prompt", "text": prompt})
        if self._input_available:
            self._input_available = False
            self._input_consumed = True
            return self._pending_input
        raise NeedsInput()

    def begin_turn(self, input_text: str = "", available: bool = True):
        """Prepares one command for a turn; ``available=False`` shows the menu only."""
        self.last_input = input_text
        self._pending_input = input_text
        self._input_available = available
        self._input_consumed = not available

    def set_input(self, input_text: str):
        """Sets the input that will be returned on the next request_input call"""
        self.begin_turn(input_text, available=True)

    def consume_pending_input(self):
        """Marks the turn's command as used even when a state read last_input directly."""
        self._input_available = False
        self._input_consumed = True

    def input_consumed(self) -> bool:
        return self._input_consumed
    
    def get_output(self) -> list:
        """Returns all accumulated output as a list of dictionaries"""
        return self.buffer
    
    def get_output_text(self) -> str:
        """Returns all accumulated output as a string"""
        return "\n".join([msg["text"] for msg in self.buffer])
    
    def get_structured_output(self) -> list:
        """
        Returns the structured output in the form of a list of dictionaries
        Example:
        [
            {"type": "system", "text": "You opened the chest"},
            {"type": "narrative", "text": "Inside you find a scroll"}
        ]
        """
        return self.buffer
    
    def clear(self):
        """Clears the buffer and any turn-scoped input state"""
        self.buffer = []
        self._pending_input = ""
        self._input_available = False
        self._input_consumed = False


class GameState:
    """
    Class that encapsulates the entire game state in a single object
    to ease serialization and state management across HTTP requests
    """
    
    def __init__(self, player, initial_state):
        """
        Initializes a new game state

        Args:
            player: The player object
            initial_state: The initial game state (e.g. TavernState)
        """
        self.io_buffer = create_game_io(WebGameIO())
        self.game = Game(player, initial_state, io_handler=self.io_buffer)
        attach_game(self.io_buffer, self.game)
        self.last_output = ""
        # Per-session player preferences (client settings, not game rules)
        self.preferences = {}
        # Rolling log of structured I/O events produced during this session
        self.event_log = []
    
    @classmethod
    def from_dict(cls, data):
        """
        Creates a GameState instance from a dictionary of data

        Args:
            data (dict): Dictionary containing the serialized game data

        Returns:
            GameState: New GameState instance built from the data
        """
        from core.game import Game
        from entities.player import Player

        # Create the player from the serialized data
        player = Player.from_dict(data["player"])

        # Create an io_buffer instance
        io_buffer = create_game_io(WebGameIO())

        # Create a temporary Game instance
        game = Game(player, None, io_handler=io_buffer, temporary=True)
        attach_game(io_buffer, game)
        game.load()  # load the game state

        # Create the GameState instance
        instance = cls(player, game.current_state())
        instance.game = game
        instance.io_buffer = io_buffer
        attach_game(instance.io_buffer, game)
        instance.last_output = data.get("output", "")
        instance.preferences = data.get("preferences", {})
        instance.event_log = list(data.get("event_log", []))

        return instance
        
    def process_command(self, command: str, provide_input: bool = True) -> str:
        """
        Processes a player command and returns the output.

        Args:
            command: The command to process.
            provide_input: False renders the current state without consuming a
                command. This is how a session is opened: it shows the first
                menu and leaves the state waiting for the first real command.

        Returns:
            The output generated by processing the command.
        """
        # Clear the buffer before processing the command
        self.io_buffer.clear()

        if provide_input:
            self.io_buffer.set_input(command)
        elif hasattr(self.io_buffer, "begin_turn"):
            self.io_buffer.begin_turn("", available=False)

        current = self.game.current_state()

        # The phase-based states show a prompt in one run and process its input
        # in the next. Seed last_input so a web command is processed on this
        # turn instead of one command late.
        if provide_input and current is not None and hasattr(current, "last_input"):
            current.last_input = command

        if current is not None:
            # Run the state until it needs a new command (or completes a turn).
            # The cap is a guard against a state that never asks for input.
            for _ in range(12):
                state = self.game.current_state()
                if state is None or not self.game.active:
                    break

                before_phase = getattr(state, "phase", None)
                before_stack = len(self.game.state_stack)

                try:
                    state.run(self.game)
                except NeedsInput:
                    break

                consumed = (
                    self.io_buffer.input_consumed()
                    if hasattr(self.io_buffer, "input_consumed")
                    else True
                )
                if hasattr(self.io_buffer, "consume_pending_input"):
                    self.io_buffer.consume_pending_input()

                after = self.game.current_state()
                changed = (
                    after is not state
                    or len(self.game.state_stack) != before_stack
                )
                after_phase = getattr(after, "phase", None) if after else None

                # Nothing consumed the command and the state did not advance;
                # waiting again cannot produce anything until the next command.
                if not changed and after_phase == before_phase and not consumed:
                    break

        # Flush any buffered output (AI narration, when enabled) before reading it
        self.io_buffer.flush()
        self._record_output()

        return self.last_output

    def _record_output(self):
        """Stores the current buffer as ``last_output`` and appends it to the log."""
        self.last_output = self.io_buffer.get_output_text()
        for message in self.io_buffer.get_structured_output():
            entry = dict(message)
            entry.setdefault("time", time.time())
            self.event_log.append(entry)
        if len(self.event_log) > 500:
            del self.event_log[:-500]

    def use_ability(self, ability_name):
        """Uses one of the player's class abilities; returns True when handled."""
        from core.abilities import resolve_ability, use_ability

        name, definition = resolve_ability(self.game.player, ability_name)
        if not name:
            return False

        from states.combat import CombatState

        current = self.game.current_state()
        if isinstance(current, CombatState):
            # Run the normal combat flow so retaliation and victory resolution
            # happen after the ability. Reset a half-open combat submenu first.
            if getattr(current, "phase", "selection") != "selection":
                current.phase = "selection"
                current.temporary_data.clear()
            current.last_ability_used = None
            self.process_command(f"use ability {name}")
            return bool(getattr(current, "last_ability_used", False))

        self.io_buffer.clear()
        used = use_ability(self.game, name, definition)
        self.io_buffer.flush()
        self._record_output()
        return used

    def get_landmark_state(self):
        """Returns a UI summary for the current menu-driven landmark."""
        from core.trials import max_waves
        from states.forge import ForgeState
        from states.rune_trials import RuneTrialsState
        from states.runeheart_gate import RuneheartGateState
        from states.sanctum import SanctumState
        from states.underroad import UnderroadState
        from states.waystation import WaystationState

        state = self.game.current_state()
        name = type(state).__name__ if state else "NoneState"
        player = self.game.player

        chooser = getattr(state, "available_actions", None)
        actions = []
        if callable(chooser):
            try:
                actions = list(chooser(self.game))
            except TypeError:
                actions = list(chooser())

        if isinstance(state, WaystationState):
            cleared = state._is_cleared(player)
            looted = state._is_looted(player)
            status = [
                "cleared" if cleared else "occupied",
                "strongbox looted" if looted else "strongbox waiting",
            ]
            description = (
                "The ruined waystation is quiet. The bandits are gone, and "
                "the old strongbox waits beside the cold campfire."
                if cleared
                else "Bandits have fortified the ruined waystation. Their "
                "chief holds court beside a cold campfire."
            )
            return {
                "active": True,
                "id": "waystation",
                "title": "The Broken Waystation",
                "description": description,
                "status": status,
                "actions": actions,
            }

        if isinstance(state, UnderroadState):
            cleared = state._cleared(player)
            looted = state._looted(player)
            status = [
                "cleared" if cleared else "smugglers active",
                "cache looted" if looted else "cache waiting",
            ]
            description = (
                "The smuggler tunnel is quiet now. Crates and old lanterns "
                "line the walls."
                if cleared
                else "A low tunnel runs beneath the waystation. Shadowed "
                "runners guard the route."
            )
            return {
                "active": True,
                "id": "underroad",
                "title": "The Underroad",
                "description": description,
                "status": status,
                "actions": actions,
            }

        if isinstance(state, SanctumState):
            ward = state._ward_passed(player)
            cleared = state._cleared(player)
            looted = state._looted(player)
            status = [
                "ward passed" if ward else "warded threshold",
                "cleared" if cleared else "Rune Warden standing",
                "vault looted" if looted else "vault sealed",
            ]
            description = (
                "The Rune Warden is still and the Runeheart vault waits in "
                "the silence."
                if cleared
                else "A black threshold of interlocking runes fills the hall. "
                "The Rune Warden waits beyond."
            )
            return {
                "active": True,
                "id": "sanctum",
                "title": "The Sealed Sanctum",
                "description": description,
                "status": status,
                "actions": actions,
            }

        if isinstance(state, RuneheartGateState):
            branch = state._branch(player)
            wardens = state._wardens_cleared(player)
            cleared = state._sovereign_cleared(player)
            branch_labels = {
                "kept": "Runeheart kept",
                "mirt": "Mirt's factor present",
                "violet": "Watch medic present",
                "none": "Runeheart unclaimed",
            }
            status = [
                branch_labels.get(branch, "Runeheart unclaimed"),
                "gate wardens broken" if wardens else "gate wardens standing",
                "sovereign defeated" if cleared else "sovereign waiting",
            ]
            description = (
                "The Runeheart Gate is silent. The stair spirals back toward "
                "the Sanctum."
                if cleared
                else "White rune-light coils down the spiral stair. "
                "Something below the heart-shaped floor is still beating."
            )
            return {
                "active": True,
                "id": "runeheart_gate",
                "title": "The Runeheart Gate",
                "description": description,
                "status": status,
                "actions": actions,
            }

        if isinstance(state, RuneTrialsState):
            limit = max_waves()
            status = [
                f"wave {state.wave} / {limit}"
                if state.wave <= limit
                else "all waves complete",
                f"best wave {int(getattr(player, 'rune_trials_best', 0) or 0)}",
            ]
            if state.boons:
                status.append("boons: " + ", ".join(state.boons))
            description = (
                "Rune-light circles the silent sanctum. Each victory offers "
                "a boon before the next wave."
                if state.wave <= limit
                else "The trial gate is quiet. Another run waits."
            )
            return {
                "active": True,
                "id": "rune_trials",
                "title": "The Rune Trials",
                "description": description,
                "status": status,
                "actions": actions,
            }

        if isinstance(state, ForgeState):
            from core.crafting import recipe_entries, rune_shards

            recipes = recipe_entries(player)
            status = [
                f"{rune_shards(player)} Rune Shards",
                f"{int(getattr(player, 'gold', 0) or 0)} gold",
                f"{len(recipes)} recipes",
            ]
            return {
                "active": True,
                "id": "forge",
                "title": "The Rune Forge",
                "description": "Rune-light pools in a basin of black stone. "
                "Shards can be worked into potions and living-metal gear.",
                "status": status,
                "actions": actions,
            }

        return {"active": False, "state": name}

    def get_party_state(self):
        """Returns recruited allies and their current stances."""
        from core.party import party_entries

        return {"allies": party_entries(self.game.player)}

    def set_ally_stance(self, ally_name, stance):
        """Changes one recruited ally's stance and records the output."""
        from core.party import set_ally_stance

        self.io_buffer.clear()
        changed = set_ally_stance(
            self.game.player, ally_name, stance, self.game
        )
        self.io_buffer.flush()
        self._record_output()
        return changed

    def get_campaign_state(self):
        """Returns main-story progress plus endgame progression."""
        from core.abilities import player_abilities
        from core.quests import quest_catalogue

        player = self.game.player
        catalogue = quest_catalogue()
        chapter_ids = (
            "shadows_of_the_market",
            "vargas_debt",
            "violet_warning",
            "sentinel_sigil",
            "waystation_trouble",
            "underroad_chapter",
            "sanctum_chapter",
            "runeheart_gate",
        )
        active = {
            quest.get("id"): quest
            for quest in (getattr(player, "active_quests", []) or [])
            if isinstance(quest, dict)
        }
        completed = {
            quest.get("id")
            for quest in (getattr(player, "completed_quests", []) or [])
            if isinstance(quest, dict)
        }

        chapters = []
        for quest_id in chapter_ids:
            definition = catalogue.get(quest_id, {})
            active_quest = active.get(quest_id)
            if active_quest is not None:
                status = str(active_quest.get("status", "active"))
            elif quest_id in completed:
                status = "completed"
            else:
                status = "not_started"
            chapters.append(
                {
                    "id": quest_id,
                    "title": definition.get("title", quest_id),
                    "objective": definition.get("objective", ""),
                    "turn_in": definition.get("turn_in", ""),
                    "status": status,
                }
            )

        claimed = {
            flag
            for flag in (getattr(player, "claimed_rewards", []) or [])
            if isinstance(flag, str)
        }
        runeheart_choice = None
        if "runeheart_kept" in claimed:
            runeheart_choice = "kept"
        elif "runeheart_mirt" in claimed:
            runeheart_choice = "mirt"
        elif "runeheart_violet" in claimed:
            runeheart_choice = "violet"

        capstone = None
        for ability in player_abilities(player, include_locked=True):
            if int(ability.get("required_level", 0) or 0) == 10:
                capstone = {
                    "name": ability.get("name", ""),
                    "unlocked": bool(ability.get("unlocked", False)),
                }
                break

        state = self.game.current_state()
        state_name = type(state).__name__ if state else "NoneState"
        location = str(getattr(player, "current_map", "") or "")
        landmark = {
            "state": state_name,
            "location": location,
        }

        from core.difficulty import (
            difficulty_definition,
            player_difficulty,
        )

        difficulty_id = player_difficulty(player)
        difficulty = difficulty_definition(difficulty_id) or {}

        return {
            "difficulty": {
                "id": difficulty_id,
                "name": difficulty.get("name", difficulty_id.title()),
                "description": difficulty.get("description", ""),
            },
            "chapters": chapters,
            "completed_chapters": sum(
                1 for chapter in chapters if chapter["status"] == "completed"
            ),
            "total_chapters": len(chapters),
            "campaign_complete": {
                "sanctum_chapter",
                "runeheart_gate",
            }
            <= completed,
            "runeheart_choice": runeheart_choice,
            "reputation": self.get_reputation_state(),
            "rune_trials": {
                "best": int(
                    getattr(player, "rune_trials_best", 0) or 0
                ),
                "runs": int(
                    getattr(player, "rune_trials_runs", 0) or 0
                ),
            },
            "rune_shards": int(getattr(player, "rune_shards", 0) or 0),
            "cycle": max(1, int(getattr(player, "cycle", 1) or 1)),
            "capstone": capstone,
            "landmark": landmark,
        }

    def get_reputation_state(self):
        """Returns faction standing and the current shop discount."""
        from core.factions import reputation_entries, shop_discount

        player = self.game.player
        return {
            "factions": reputation_entries(player),
            "shop_discount": shop_discount(player),
        }

    def get_shop_state(self):
        """Returns the market stock and the player's sellable inventory."""
        from core.shop import sellable_items, shop_stock

        player = self.game.player
        return {
            "gold": int(getattr(player, "gold", 0) or 0),
            "stock": shop_stock(player),
            "sellable": sellable_items(player),
            "reputation": self.get_reputation_state(),
        }

    def get_forge_state(self):
        """Returns the Sanctum Forge recipes and current resources."""
        from core.crafting import recipe_entries, rune_shards
        from states.forge import ForgeState

        current = self.game.current_state()
        if not isinstance(current, ForgeState):
            return None
        player = self.game.player
        return {
            "shards": rune_shards(player),
            "gold": int(getattr(player, "gold", 0) or 0),
            "recipes": recipe_entries(player),
        }

    def forge_craft(self, recipe_id):
        """Crafts one recipe and records its engine output."""
        from core.crafting import craft_recipe
        from states.forge import ForgeState

        current = self.game.current_state()
        if not isinstance(current, ForgeState):
            return {"success": False, "message": "The forge is not available."}

        self.io_buffer.clear()
        result = craft_recipe(self.game.player, recipe_id, self.game)
        self.io_buffer.flush()
        self._record_output()
        return result

    def get_black_market_state(self):
        """Returns Nessa's cache stock, tier and gold."""
        from core.black_market import black_market_state
        from states.black_market import BlackMarketState

        current = self.game.current_state()
        if not isinstance(current, BlackMarketState):
            return None
        return black_market_state(self.game.player)

    def black_market_buy(self, item_name):
        """Buys one black-market item and records its engine output."""
        from core.black_market import buy_black_market_item
        from states.black_market import BlackMarketState

        current = self.game.current_state()
        if not isinstance(current, BlackMarketState):
            return {
                "success": False,
                "message": "Nessa's cache is not open.",
            }

        self.io_buffer.clear()
        result = buy_black_market_item(
            self.game.player, item_name, self.game
        )
        self.io_buffer.flush()
        self._record_output()
        return result

    def shop_buy(self, item_name):
        """Buys a market item and records its engine output."""
        from core.shop import buy_item

        self.io_buffer.clear()
        result = buy_item(self.game.player, item_name, self.game)
        self.io_buffer.flush()
        self._record_output()
        return result

    def shop_sell(self, item_name):
        """Sells a market item and records its engine output."""
        from core.shop import sell_item

        self.io_buffer.clear()
        result = sell_item(self.game.player, item_name, self.game)
        self.io_buffer.flush()
        self._record_output()
        return result

    def get_bounty_state(self):
        """Returns the bounty board's contracts and active limit."""
        from core.bounties import (
            MAX_ACTIVE_BOUNTIES,
            active_bounty_count,
            bounty_entries,
        )

        player = self.game.player
        return {
            "gold": int(getattr(player, "gold", 0) or 0),
            "bounties": bounty_entries(player),
            "active_count": active_bounty_count(player),
            "max_active": MAX_ACTIVE_BOUNTIES,
        }

    def bounty_accept(self, bounty_id):
        """Accepts a bounty and records its engine output."""
        from core.bounties import accept_bounty

        self.io_buffer.clear()
        accepted = accept_bounty(self.game.player, bounty_id, self.game)
        self.io_buffer.flush()
        self._record_output()
        return accepted

    def bounty_claim(self, bounty_id):
        """Claims a ready bounty and records its engine output."""
        from core.bounties import claim_bounty

        self.io_buffer.clear()
        claimed = claim_bounty(self.game.player, bounty_id, self.game)
        self.io_buffer.flush()
        self._record_output()
        return claimed

    def get_log(self, max_events=50):
        """Returns the most recent structured events, oldest first."""
        if max_events <= 0:
            return []
        return self.event_log[-max_events:]

    def save_preferences(self, preferences):
        """Merges client preferences into the session's preference store."""
        if not isinstance(preferences, dict):
            raise TypeError("preferences must be a dictionary")
        self.preferences.update(preferences)
        return True

    def get_preferences(self):
        """Returns a copy of the session's preferences."""
        return dict(self.preferences)

    def get_combat_state(self):
        """Returns serializable information about an active combat, if any."""
        from states.combat import CombatState

        current = self.game.current_state()
        if isinstance(current, CombatState) and getattr(current, "enemies", None):
            from core.conditions import (
                condition_escape_action,
                condition_stand_up,
            )
            from core.enemy_abilities import load_abilities
            from core.maneuvers import maneuver_actions
            from core.party import (
                STANCES,
                ally_loyalty,
                ally_stance,
                ally_will_act,
                load_ally_abilities,
            )

            target = getattr(current, "opponent", None)
            living = [
                enemy
                for enemy in current.enemies
                if getattr(enemy, "hp", 0) > 0
            ]
            actions = [
                "attack",
                "defend",
                "aim",
                "use item",
                "use ability",
                "change equipment",
                "flee",
                *maneuver_actions(),
            ]
            if current.cover_available(self.game):
                actions.append("take cover")
            if condition_stand_up(self.game.player):
                actions.append("stand up")
            escape = condition_escape_action(self.game.player)
            if escape:
                _, escape_action = escape
                label = str(
                    escape_action.get("label", "Break free")
                ).strip().casefold()
                if label and label not in actions:
                    actions.append(label)
            for ally in getattr(current, "allies", []) or []:
                if getattr(ally, "hp", 0) <= 0:
                    continue
                ally_name = getattr(ally, "name", "Ally")
                actions.extend(
                    f"{ally_name}: {stance}" for stance in STANCES
                )
                for ability in load_ally_abilities(
                    getattr(ally, "ally_ability_ids", [])
                ):
                    actions.append(
                        f"{ally_name}: {ability.get('id')}"
                    )
            if len(living) > 1:
                actions.append("choose target")

            enemies = []
            for index, enemy in enumerate(current.enemies):
                abilities = getattr(enemy, "abilities", None)
                if not abilities:
                    abilities = load_abilities(
                        getattr(enemy, "ability_ids", [])
                    )
                ability_names = {
                    ability.get("id"): ability.get("name", ability.get("id"))
                    for ability in abilities or []
                    if isinstance(ability, dict)
                }
                cooldowns = current.ability_cooldowns.get(str(index), {}) or {}
                alive = getattr(enemy, "hp", 0) > 0
                enemies.append(
                    {
                        "name": getattr(enemy, "name", "Unknown"),
                        "hp": getattr(enemy, "hp", 0),
                        "max_hp": getattr(enemy, "hp_max", 0),
                        "ac": getattr(enemy, "armor_class", 10),
                        "elite": bool(
                            getattr(enemy, "elite", False)
                        )
                        and alive,
                        "conditions": (
                            dict(getattr(enemy, "conditions", {}) or {})
                            if alive
                            else {}
                        ),
                        "surprised": bool(
                            getattr(current, "surprised", False)
                        )
                        and alive,
                        "guard": (
                            int(current.enemy_guard.get(str(index), 0) or 0)
                            if alive
                            else 0
                        ),
                        "cooldowns": (
                            [
                                {
                                    "id": ability_id,
                                    "name": ability_names.get(
                                        ability_id, ability_id
                                    ),
                                    "remaining": int(remaining or 0),
                                }
                                for ability_id, remaining in cooldowns.items()
                                if int(remaining or 0) > 0
                                and not str(ability_id).startswith(
                                    "maneuver:"
                                )
                            ]
                            if alive
                            else []
                        ),
                    }
                )

            return {
                "in_combat": True,
                "round": getattr(current, "turn", 1),
                "turn_of": "player",
                "surprised": bool(
                    getattr(current, "surprised", False)
                ),
                "target": getattr(target, "name", None),
                "conditions": dict(
                    getattr(self.game.player, "conditions", {}) or {}
                ),
                "effects": {
                    "defending": bool(
                        (getattr(current, "effects", {}) or {}).get("defend")
                    ),
                    "aiming": bool(
                        (getattr(current, "effects", {}) or {}).get("aim")
                    ),
                    "covering": bool(
                        (getattr(current, "effects", {}) or {}).get("cover")
                    ),
                    "flanking": bool(current._flanking_bonus()),
                },
                "enemies": enemies,
                "allies": [
                    {
                        "name": getattr(ally, "name", "Unknown"),
                        "hp": getattr(ally, "hp", 0),
                        "max_hp": getattr(ally, "hp_max", 0),
                        "stance": ally_stance(
                            self.game.player,
                            getattr(ally, "name", "Unknown"),
                        ),
                        "stance_label": STANCES[
                            ally_stance(
                                self.game.player,
                                getattr(ally, "name", "Unknown"),
                            )
                        ],
                        "loyalty": ally_loyalty(
                            self.game.player,
                            getattr(ally, "name", "Unknown"),
                        ),
                        "loyalty_label": ally_loyalty(
                            self.game.player,
                            getattr(ally, "name", "Unknown"),
                        ).title(),
                        "will_act": ally_will_act(
                            self.game.player,
                            getattr(ally, "name", "Unknown"),
                        ),
                        "abilities": [
                            ability.get("name")
                            for ability in load_ally_abilities(
                                getattr(ally, "ally_ability_ids", [])
                            )
                        ],
                        "cooldowns": {
                            key.split(":", 1)[1]: int(value or 0)
                            for key, value in (
                                getattr(
                                    current, "ally_ability_cooldowns", {}
                                )
                                or {}
                            ).items()
                            if key.startswith(
                                f"{getattr(ally, 'name', 'Unknown')}:"
                            )
                            and int(value or 0) > 0
                        },
                    }
                    for ally in getattr(current, "allies", [])
                ],
                "available_actions": actions,
            }
        return {"in_combat": False}

    def get_available_directions(self):
        """Returns the cardinal directions the player can currently walk into."""
        player = self.game.player
        if not player.current_map:
            return []

        current_map = self.game.map_manager.get_map(player.current_map)
        if not current_map:
            return []

        directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
        }
        return [
            name
            for name, (dx, dy) in directions.items()
            if current_map.is_valid_position(player.x + dx, player.y + dy)
        ]

    def get_npcs_in_location(self):
        """Returns the names of the NPCs placed on the player's current map."""
        player = self.game.player
        if not player.current_map:
            return []

        current_map = self.game.map_manager.get_map(player.current_map)
        if not current_map:
            return []

        return [getattr(npc, "name", str(npc)) for npc in current_map.npc.values()]

    def get_player_summary(self):
        """Returns a compact, serializable summary of the player."""
        player = self.game.player
        from core.difficulty import player_difficulty

        return {
            "name": player.name,
            "char_class": player.char_class,
            "hp": player.hp,
            "hp_max": player.hp_max,
            "level": player.level,
            "experience": player.experience,
            "gold": player.gold,
            "map": player.current_map,
            "position": {"x": player.x, "y": player.y},
            "mana": getattr(player, "mana", 0),
            "mana_max": getattr(player, "mana_max", 0),
            "ac": getattr(player, "armor_class", 10),
            "attack_bonus": getattr(player, "attack_bonus", 0),
            "stealthed": bool(getattr(player, "stealthed", False)),
            "disguised": bool(getattr(player, "disguised", False)),
            "rune_shards": int(getattr(player, "rune_shards", 0) or 0),
            "difficulty": player_difficulty(player),
        }

    def get_abilities(self):
        """Returns the player's class abilities, skills and mana pool."""
        from core.abilities import player_abilities
        from states.combat import CombatState

        player = self.game.player
        details = player_abilities(player, include_locked=True)
        unlocked = [ability for ability in details if ability["unlocked"]]
        current = self.game.current_state()
        return {
            "abilities": [ability["name"] for ability in unlocked],
            "ability_details": details,
            "skills": sorted(
                skill
                for skill, proficient in player.skill_proficiencies.items()
                if proficient
            ),
            "skill_proficiencies": dict(player.skill_proficiencies),
            "mana": getattr(player, "mana", 0),
            "mana_max": getattr(player, "mana_max", 0),
            "in_combat": isinstance(current, CombatState),
        }

    def get_dialogue_state(self):
        """Returns the current dialogue node and options, if a dialogue is active."""
        from states.dialogue import DialogueState

        current = self.game.current_state()
        if not isinstance(current, DialogueState) or getattr(current, "npc", None) is None:
            return {"active": False}

        conversation = current.npc.get_conversation(current.current_state) or {}
        options = [
            {"index": index, "text": text, "target": target}
            for index, (text, target) in enumerate(
                current.visible_options(self.game, conversation), start=1
            )
        ]
        return {
            "active": True,
            "npc": current.npc.name,
            "node": current.current_state,
            "text": conversation.get("text", ""),
            "options": options,
        }

    def get_map_view(self):
        """Returns the current map as an ASCII grid with the player marked."""
        player = self.game.player
        if not player.current_map:
            return None

        current_map = self.game.map_manager.get_map(player.current_map)
        if not current_map:
            return None

        legend = [{"token": "P", "names": ["You"], "types": ["player"]}]
        legend.extend(current_map.token_legend())

        return {
            "map": player.current_map,
            "width": current_map.width,
            "height": current_map.height,
            "position": {"x": player.x, "y": player.y},
            "ascii": current_map.generate_ascii_representation((player.x, player.y)),
            "legend": legend,
        }

    def get_nearby_targets(self):
        """Returns names of nearby items/NPCs and walkable directions."""
        position = self.get_player_position() or {}
        nearby_items = position.get("nearby_items", {}) or {}
        nearby_npcs = position.get("nearby_npcs", {}) or {}
        return {
            "items": [getattr(obj, "name", str(obj)) for obj in nearby_items.values()],
            "npc": [getattr(obj, "name", str(obj)) for obj in nearby_npcs.values()],
            "directions": self.get_available_directions(),
        }

    def get_current_state(self):
        """
        Returns a dictionary with the current state of the game

        Returns:
            Dictionary with information about the current state
        """
        # Get equipped items in serializable form
        equipped_weapon = self.game.player.weapon.name if self.game.player.weapon else ""
        equipped_armor = self.game.player.armor.name if self.game.player.armor else ""
        equipped_accessories = [acc.name for acc in self.game.player.accessories] if self.game.player.accessories else []
        
        # Simplified inventory list
        inventory = [obj.name for obj in self.game.player.inventory]
        
        # Current state as a string
        current_state = self.game.current_state()
        state_name = type(current_state).__name__ if current_state else "NoneState"
        
        # Serializable and simplified stats
        stats = {
            "strength": self.game.player.strength,
            "dexterity": self.game.player.dexterity,
            "constitution": self.game.player.constitution,
            "intelligence": self.game.player.intelligence,
            "wisdom": self.game.player.wisdom,
            "charisma": self.game.player.charisma,
            "strength_base": getattr(self.game.player, "strength_base", 10),
            "dexterity_base": getattr(self.game.player, "dexterity_base", 10),
            "constitution_base": getattr(self.game.player, "constitution_base", 10),
            "intelligence_base": getattr(self.game.player, "intelligence_base", 10),
            "wisdom_base": getattr(self.game.player, "wisdom_base", 10),
            "charisma_base": getattr(self.game.player, "charisma_base", 10),
            "gold": self.game.player.gold,
            "level": self.game.player.level,
            "experience": self.game.player.experience,
            "mana": getattr(self.game.player, "mana", 0),
            "mana_max": getattr(self.game.player, "mana_max", 0),
            "ac": getattr(self.game.player, "armor_class", 10),
            "attack_bonus": getattr(self.game.player, "attack_bonus", 0),
            "defense": getattr(self.game.player, "defense", 0),
            "initiative": getattr(self.game.player, "initiative", 0),
        }
        
        from core.difficulty import player_difficulty

        return {
            "name": self.game.player.name,
            "char_class": self.game.player.char_class,
            "difficulty": player_difficulty(self.game.player),
            "hp": self.game.player.hp,
            "max_hp": self.game.player.hp_max,
            "state": state_name,
            "output": self.last_output,
            "position": {
                "map": self.game.player.current_map,
                "x": self.game.player.x,
                "y": self.game.player.y
            },
            "inventory": inventory,
            "equipment": {
                "weapon": equipped_weapon,
                "armor": equipped_armor,
                "accessories": equipped_accessories
            },
            "stats": stats,
            "active_quests": list(self.game.player.active_quests),
            "completed_quests": list(self.game.player.completed_quests),
            "achievements": list(
                getattr(self.game.player, "achievements", []) or []
            ),
            "timestamp_achievements": dict(
                getattr(self.game.player, "achievement_timestamps", {}) or {}
            ),
            "conditions": dict(
                getattr(self.game.player, "conditions", {}) or {}
            ),
            "stealthed": bool(
                getattr(self.game.player, "stealthed", False)
            ),
            "disguised": bool(
                getattr(self.game.player, "disguised", False)
            ),
            "reputation": self.get_reputation_state(),
            "party": self.get_party_state(),
            "campaign": self.get_campaign_state(),
            "landmark": self.get_landmark_state(),
            "rune_trials": {
                "best": int(
                    getattr(self.game.player, "rune_trials_best", 0) or 0
                ),
                "runs": int(
                    getattr(self.game.player, "rune_trials_runs", 0) or 0
                ),
            },
            "rune_shards": int(
                getattr(self.game.player, "rune_shards", 0) or 0
            ),
            "preferences": dict(self.preferences),
            "combat": self.get_combat_state(),
            "dialogue": self.get_dialogue_state(),
        }
    
    def save(self, file_path="save.json"):
        """
        Saves the current state to a file

        Args:
            file_path: Path of the save file

        Returns:
            bool: True if the save succeeded, False otherwise
        """
        try:
            # Import the unstable state classes
            from states.combat import CombatState
            from states.market import MarketState
            from states.dialogue import DialogueState
            from states.ability_check import AbilityCheckState
            
            # Check whether the game is in an unstable state
            if isinstance(self.game.current_state(), (CombatState, AbilityCheckState, DialogueState)):
                self.io_buffer.show_message("You cannot save during combat, a check or a dialogue.")
                return False

            # Check the phase in MarketState (saving is only disallowed during sales)
            if isinstance(self.game.current_state(), MarketState) and hasattr(self.game.current_state(), 'phase'):
                market_phase = self.game.current_state().phase
                if market_phase in ["item_sale_list", "confirm_item_sale", "buy_potion"]:
                    self.io_buffer.show_message("You cannot save during a market transaction.")
                    return False
            
            # Get the complete state
            current_state = self.get_current_state()

            # Get map information if available
            maps_data = {}
            if hasattr(self.game, 'map_manager') and hasattr(self.game.map_manager, 'maps'):
                for map_name, map in self.game.map_manager.maps.items():
                    if hasattr(map, 'to_dict'):
                        maps_data[map_name] = map.to_dict()
            
            # Add map information to the state
            current_state['maps'] = maps_data

            # Delegate to Game to save to file
            result = self.game.save(file_path)

            if result:
                self.io_buffer.show_message(f"Game saved successfully to {file_path}")
            else:
                self.io_buffer.show_message("Error while saving")

            return result
        except Exception as e:
            self.io_buffer.show_message(f"Error while saving: {e}")
            return False
    
    def load(self, file_path="save.json"):
        """
        Loads the state from a file

        Args:
            file_path: Path of the save file

        Returns:
            True if the load succeeded, False otherwise
        """
        return self.game.load(file_path)
    
    def get_player_position(self):
        """
        Returns information about the player's current position

        Returns:
            Dictionary with the position information
        """
        return self.game.get_player_position()
    
    def move_player(self, direction):
        """
        Moves the player in the specified direction

        Args:
            direction: "north", "south", "east", "west"

        Returns:
            True if the movement happened, False otherwise
        """
        return self.game.move_player(direction) 