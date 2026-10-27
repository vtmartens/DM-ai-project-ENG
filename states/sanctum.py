"""The Sealed Sanctum: the final chapter beneath the Underroad."""

from core.conditions import apply_condition
from core.item_catalogue import item_definition
from core.quests import start_quest
from items.item import Item
from states.base_state import BaseGameState
from util.helpers import press_enter


class SanctumState(BaseGameState):
    """Menu-driven capstone area with a warded hall, boss and vault."""

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "sanctum"
        self.phase = "ward"
        self.last_input = None

    def available_actions(self, game=None):
        game = game or getattr(self, "game", None)
        if game is None:
            return ["leave"]
        if not self._ward_passed(game.player):
            return ["amulet", "force", "leave"]
        if self._cleared(game.player):
            return ["vault", "trials", "forge", "leave"]
        return ["confront", "vault", "leave"]

    def run(self, game):
        self._ensure_map(game)
        self._ensure_quest(game)

        if self._ward_passed(game.player):
            if self.phase == "ward":
                self.phase = "main_menu"
        elif self.phase != "ward":
            self.phase = "ward"

        if self.phase == "ward":
            self._ward_menu(game)
        elif self.phase == "main_menu":
            self._main_menu(game)
        else:
            self.phase = "main_menu"
            self.run(game)

    def _ensure_map(self, game):
        map_obj = game.map_manager.get_map("sanctum")
        if map_obj is None:
            return
        game.map_manager.set_current_map("sanctum")
        if (
            game.player.current_map != "sanctum"
            or not map_obj.is_valid_position(game.player.x, game.player.y)
        ):
            x, y = map_obj.player_start_position
            game.player.set_position("sanctum", x, y)

    def _ensure_quest(self, game):
        player = game.player
        known = {
            quest.get("id")
            for quest in (
                list(getattr(player, "active_quests", []) or [])
                + list(getattr(player, "completed_quests", []) or [])
            )
            if isinstance(quest, dict)
        }
        if "sanctum_chapter" not in known:
            start_quest(player, "sanctum_chapter", game)

    @staticmethod
    def _ward_passed(player):
        return "sanctum_ward" in (
            getattr(player, "claimed_rewards", []) or []
        )

    @staticmethod
    def _cleared(player):
        return "sanctum" in (
            getattr(player, "cleared_areas", []) or []
        )

    @staticmethod
    def _looted(player):
        return "sanctum_vault" in (
            getattr(player, "claimed_rewards", []) or []
        )

    @staticmethod
    def _has_item(player, item_name):
        items = list(getattr(player, "inventory", []) or [])
        items.extend(
            item
            for item in (
                getattr(player, "weapon", None),
                getattr(player, "armor", None),
            )
            if item is not None
        )
        items.extend(getattr(player, "accessories", []) or [])
        return any(
            getattr(item, "name", item) == item_name for item in items
        )

    def _mark_ward_passed(self, player):
        claimed = getattr(player, "claimed_rewards", None)
        if not isinstance(claimed, list):
            claimed = []
            player.claimed_rewards = claimed
        if "sanctum_ward" not in claimed:
            claimed.append("sanctum_ward")

    def _ward_menu(self, game):
        player = game.player
        game.io.show_message("\n=== THE SEALED SANCTUM ===")
        game.io.show_message(
            "A black threshold of interlocking runes fills the far end of "
            "the hall. The air tastes of hot metal, and the floor vibrates "
            "with a slow heartbeat."
        )
        game.io.show_message(
            "\n1. Raise the Rune-Ward Amulet\n"
            "2. Force your way through the ward\n"
            "3. Return to the Underroad"
        )

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if choice in {"1", "amulet", "raise", "ward"}:
            if self._raise_amulet(game):
                self.phase = "main_menu"
                press_enter(game)
                return
            game.io.show_message(
                "You do not carry the Rune-Ward Amulet."
            )
        elif choice in {"2", "force", "push", "save"}:
            self._force_ward(game)
            self.phase = "main_menu"
            press_enter(game)
            return
        elif choice in {"3", "leave", "return", "underroad", "exit"}:
            self._leave(game)
            return
        else:
            game.io.show_message("Invalid choice.")

        self.phase = "ward"
        press_enter(game)

    def _raise_amulet(self, game):
        player = game.player
        if not self._has_item(player, "Rune-Ward Amulet"):
            return False

        self._mark_ward_passed(player)
        game.io.show_message(
            "The Rune-Ward Amulet flares white. The threshold recognizes "
            "its twin mark and parts without a sound."
        )
        return True

    def _force_ward(self, game):
        player = game.player
        passed = player.saving_throw("constitution", 14, game)
        if passed:
            game.io.show_message(
                "You brace against the pressure and force your way through "
                "the ward."
            )
        else:
            damage = min(8, max(0, int(getattr(player, "hp", 1)) - 1))
            if damage:
                player.hp -= damage
                game.io.show_message(
                    f"The ward sears you for {damage} damage, but you stumble "
                    "through."
                )
            else:
                game.io.show_message(
                    "The ward crushes the breath from you, but you crawl through."
                )
            apply_condition(player, "weakened", turns=2, game=game)
        self._mark_ward_passed(player)
        return True

    def _main_menu(self, game):
        player = game.player
        cleared = self._cleared(player)

        game.io.show_message("\n=== THE SEALED SANCTUM ===")
        if cleared:
            game.io.show_message(
                "The Rune Warden is still, its rune core dark. The vault at "
                "the heart of the hall waits in the silence."
            )
        else:
            game.io.show_message(
                "The warded hall opens into a vast chamber. A towering "
                "construct of black stone and burning runes waits on a "
                "throne of fractured marble."
            )
        game.io.show_message(f"\nGold: {player.gold}")
        game.io.show_message("\nWhat do you want to do?")
        game.io.show_message(
            "1. The sanctum is silent"
            if cleared
            else "1. Confront the Rune Warden"
        )
        game.io.show_message("2. Open the Runeheart vault")
        game.io.show_message("3. Return to the Underroad")
        if cleared:
            game.io.show_message("4. Enter the Rune Trials")
            game.io.show_message("5. Use the Rune Forge")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if choice in {"1", "confront", "attack", "fight", "warden"}:
            if self._confront(game):
                return
        elif choice in {"2", "vault", "cache", "loot", "open"}:
            self._open_vault(game)
        elif choice in {"3", "leave", "return", "underroad", "exit"}:
            self._leave(game)
            return
        elif choice in {"4", "trials", "trial", "rune trials"}:
            if self._enter_trials(game):
                return
        elif choice in {"5", "forge", "craft", "rune forge"}:
            if self._enter_forge(game):
                return
        else:
            game.io.show_message("Invalid choice.")

        self.phase = "main_menu"
        press_enter(game)

    def _confront(self, game):
        if self._cleared(game.player):
            game.io.show_message("The sanctum is already clear.")
            return False

        from core.encounters import build_encounter
        from core.quests import build_ally_party
        from states.combat import CombatState

        encounter = build_encounter("sanctum_boss")
        if encounter is None:
            game.io.show_message("The Rune Warden cannot be found.")
            return False

        game.io.show_message(
            f"\n{encounter['title']}: {encounter['description']}"
        )
        names = ", ".join(enemy.name for enemy in encounter["enemies"])
        game.io.show_message(f"Enemies: {names}")
        game.push_state(
            CombatState(
                enemies=encounter["enemies"],
                encounter=encounter,
                allies=build_ally_party(game.player),
            )
        )
        return True

    def _open_vault(self, game):
        player = game.player
        if not self._cleared(player):
            game.io.show_message(
                "The vault is sealed. The Rune Warden still holds the sanctum."
            )
            return False
        if self._looted(player):
            game.io.show_message("The Runeheart vault is empty.")
            return False

        game.io.show_message(
            "The vault opens on a heart of living rune-stone and 120 gold. "
            "The amulet is worth a fortune to the right buyer."
        )
        game.io.show_message(
            "\n1. Keep the Runeheart Amulet\n"
            "2. Give it to Mirt (+Mirt's Network, +200 gold)\n"
            "3. Give it to Violet (+Violet's Watch, +100 gold)\n"
            "4. Decide later"
        )
        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        if not self._apply_vault_choice(player, choice, game):
            game.io.show_message("You leave the vault untouched for now.")
            return False
        return True

    def _apply_vault_choice(self, player, choice, game):
        if not self._cleared(player) or self._looted(player):
            return False
        choice = str(choice or "").strip().casefold()
        if choice in {"4", "later", "leave", "back", "cancel"}:
            return False

        base_gold = 120
        if choice in {"1", "keep", "amulet"}:
            definition = item_definition("Runeheart Amulet")
            if definition is not None:
                player.add_item(Item.from_dict(definition))
            player.add_gold(base_gold, game)
            game.io.show_message(
                "You close your hand around the Runeheart Amulet."
            )
            reward_flag = "runeheart_kept"
        elif choice in {"2", "mirt", "give_mirt"}:
            from core.factions import adjust_reputation

            adjust_reputation(
                player,
                "mirt_network",
                12,
                game,
                reason="Mirt will remember the gift.",
            )
            player.add_gold(base_gold + 200, game)
            game.io.show_message(
                "Mirt accepts the Runeheart with a merchant's careful smile."
            )
            reward_flag = "runeheart_mirt"
        elif choice in {"3", "violet", "give_violet"}:
            from core.factions import adjust_reputation

            adjust_reputation(
                player,
                "violet_watch",
                12,
                game,
                reason="Violet will remember the gift.",
            )
            player.add_gold(base_gold + 100, game)
            game.io.show_message(
                "Violet turns the Runeheart in the light, already thinking "
                "of who it can protect."
            )
            reward_flag = "runeheart_violet"
        else:
            return False

        claimed = getattr(player, "claimed_rewards", None)
        if not isinstance(claimed, list):
            claimed = []
            player.claimed_rewards = claimed
        claimed.append("sanctum_vault")
        if reward_flag not in claimed:
            claimed.append(reward_flag)
        return True

    def _enter_trials(self, game):
        if not self._cleared(game.player):
            game.io.show_message(
                "The trial gate is dark. Defeat the Rune Warden first."
            )
            return False
        game.io.show_message(
            "You lay one hand on the Runeheart gate. The sanctum answers "
            "with a circle of white fire, and the first trial begins to form."
        )
        from states.rune_trials import RuneTrialsState

        game.change_state(RuneTrialsState(game))
        return True

    def _enter_forge(self, game):
        if not self._cleared(game.player):
            game.io.show_message(
                "The forge is cold. Defeat the Rune Warden first."
            )
            return False
        game.io.show_message(
            "You approach the Rune Forge. Shards hum in the black basin."
        )
        from states.forge import ForgeState

        game.change_state(ForgeState(game))
        return True

    def _leave(self, game):
        game.io.show_message(
            "You follow the rune-lit passage back to the Underroad."
        )
        game.map_manager.set_current_map("underroad")
        game.player.set_position("underroad", 2, 7)
        from states.underroad import UnderroadState

        game.change_state(UnderroadState(game))

    def resume(self, game):
        if self._cleared(game.player):
            game.io.show_message("\nThe sanctum is silent.")
        else:
            game.io.show_message("\nYou return to the warded hall.")

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game)
        state.phase = data.get("phase", "ward")
        return state
