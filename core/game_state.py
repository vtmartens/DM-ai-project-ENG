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
            target = getattr(current, "opponent", None)
            living = [
                enemy
                for enemy in current.enemies
                if getattr(enemy, "hp", 0) > 0
            ]
            actions = [
                "attack",
                "use item",
                "use ability",
                "change equipment",
                "flee",
            ]
            if len(living) > 1:
                actions.append("choose target")
            return {
                "in_combat": True,
                "round": getattr(current, "turn", 1),
                "turn_of": "player",
                "target": getattr(target, "name", None),
                "enemies": [
                    {
                        "name": getattr(enemy, "name", "Unknown"),
                        "hp": getattr(enemy, "hp", 0),
                        "max_hp": getattr(enemy, "hp_max", 0),
                    }
                    for enemy in current.enemies
                ],
                "allies": [
                    {
                        "name": getattr(ally, "name", "Unknown"),
                        "hp": getattr(ally, "hp", 0),
                        "max_hp": getattr(ally, "hp_max", 0),
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
                conversation.get("options", []), start=1
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
            "initiative": getattr(self.game.player, "initiative", 0),
        }
        
        return {
            "name": self.game.player.name,
            "char_class": self.game.player.char_class,
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