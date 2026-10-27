"""The Broken Waystation: a small road landmark with a boss and rewards."""

from states.base_state import BaseGameState
from items.item import Item
from util.helpers import press_enter


class WaystationState(BaseGameState):
    """Menu-driven landmark at the end of the Trade Road."""

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "waystation"
        self.phase = "main_menu"
        self.last_input = None

    def run(self, game):
        self._ensure_map(game)
        if self.phase == "main_menu":
            self._main_menu(game)
        else:
            self.phase = "main_menu"
            self.run(game)

    def _ensure_map(self, game):
        map_obj = game.map_manager.get_map("waystation")
        if map_obj is None:
            return
        game.map_manager.set_current_map("waystation")
        if (
            game.player.current_map != "waystation"
            or not map_obj.is_valid_position(game.player.x, game.player.y)
        ):
            x, y = map_obj.player_start_position
            game.player.set_position("waystation", x, y)

    @staticmethod
    def _is_cleared(player):
        return "waystation" in (
            getattr(player, "cleared_areas", []) or []
        )

    @staticmethod
    def _is_looted(player):
        return "waystation_chest" in (
            getattr(player, "claimed_rewards", []) or []
        )

    def _main_menu(self, game):
        player = game.player
        cleared = self._is_cleared(player)
        looted = self._is_looted(player)

        game.io.show_message("\n=== THE BROKEN WAYSTATION ===")
        if cleared:
            game.io.show_message(
                "The ruined waystation is quiet. The bandits are gone, and "
                "the old strongbox waits beside the cold campfire."
            )
        else:
            game.io.show_message(
                "A ruined waystation stands at the end of the trade road. "
                "Bandits have fortified the old walls, and their chief holds "
                "court beside a cold campfire."
            )
        game.io.show_message(f"Gold: {player.gold}")
        game.io.show_message("\nWhat do you want to do?")
        game.io.show_message(
            "1. The waystation is quiet" if cleared else "1. Confront the bandits"
        )
        game.io.show_message("2. Open the strongbox")
        game.io.show_message("3. Rest at the campfire")
        if cleared:
            game.io.show_message("4. Return to the road")
            game.io.show_message("5. Descend into the Underroad")
        else:
            game.io.show_message("4. Return to the road")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if choice in {"1", "confront", "attack", "fight", "bandits", "bandit"}:
            if self._confront_bandits(game):
                return
        elif choice in {"2", "strongbox", "chest", "loot"}:
            self._open_strongbox(game)
        elif choice in {"3", "rest", "campfire"}:
            self._rest_at_campfire(game)
        elif choice in {"4", "leave", "return", "road", "exit"}:
            self._leave(game)
            return
        elif choice in {"5", "underroad", "descend", "tunnel"}:
            if self._descend(game):
                return
        else:
            game.io.show_message("Invalid choice.")
            press_enter(game)
            self.phase = "main_menu"
            return

        self.phase = "main_menu"
        press_enter(game)

    def _confront_bandits(self, game):
        player = game.player
        if self._is_cleared(player):
            game.io.show_message(
                "The waystation is already clear. The strongbox is yours to open."
            )
            return False

        from core.encounters import build_encounter

        encounter = build_encounter("waystation_chief")
        if encounter is None:
            game.io.show_message(
                "The bandits are here, but their leader cannot be found."
            )
            return False

        from core.quests import build_ally_party
        from states.combat import CombatState

        game.io.show_message(
            f"\n{encounter['title']}: {encounter['description']}"
        )
        names = ", ".join(enemy.name for enemy in encounter["enemies"])
        game.io.show_message(f"Enemies: {names}")
        game.push_state(
            CombatState(
                enemies=encounter["enemies"],
                encounter=encounter,
                allies=build_ally_party(player),
            )
        )
        return True

    def _open_strongbox(self, game):
        player = game.player
        if not self._is_cleared(player):
            game.io.show_message(
                "The bandits still hold the waystation. The strongbox is not safe to open."
            )
            return False
        if self._is_looted(player):
            game.io.show_message("The strongbox is empty.")
            return False

        from core.item_catalogue import item_definition

        definition = item_definition("Wayfarer's Cloak")
        if definition is not None:
            player.add_item(Item.from_dict(definition))
            game.io.show_message("You found the Wayfarer's Cloak in the strongbox!")

        ledger = Item(
            "Bandit Ledger",
            "common",
            {},
            20,
            "A ledger naming buyers and a hidden route beneath the waystation",
        )
        player.add_item(ledger)
        game.io.show_message(
            "Among the coins is a bandit ledger. It names a Smuggler Lord "
            "in a hidden Underroad beneath the waystation."
        )
        from core.quests import start_quest

        start_quest(player, "underroad_chapter", game)

        claimed = getattr(player, "claimed_rewards", None)
        if not isinstance(claimed, list):
            claimed = []
            player.claimed_rewards = claimed
        claimed.append("waystation_chest")
        player.add_gold(50, game)
        return True

    def _descend(self, game):
        if not self._is_cleared(game.player):
            game.io.show_message(
                "The passage beneath the waystation is still held by the bandits."
            )
            return False

        game.io.show_message(
            "You lift the old trapdoor and descend into the Underroad."
        )
        game.player.set_position("underroad", 2, 7)
        game.map_manager.set_current_map("underroad")
        from states.underroad import UnderroadState

        game.change_state(UnderroadState(game))
        return True

    def _rest_at_campfire(self, game):
        if not self._is_cleared(game.player):
            game.io.show_message(
                "The campfire is not safe while the bandits still hold the waystation."
            )
            return False

        player = game.player
        player.hp = player.hp_max
        player.mana = int(getattr(player, "mana_max", 0) or 0)
        conditions = getattr(player, "conditions", None)
        if isinstance(conditions, dict):
            conditions.clear()
        game.io.show_message(
            "You rest at the campfire. HP, mana and conditions are fully restored."
        )
        return True

    def _leave(self, game):
        game.io.show_message("You leave the waystation and return to the trade road.")
        game.map_manager.set_current_map("road")
        game.player.set_position("road", 20, 7)
        from states.map_state import MapState

        game.change_state(MapState(origin_state=self))

    def resume(self, game):
        if self._is_cleared(game.player):
            game.io.show_message("\nThe waystation is quiet now.")
        else:
            game.io.show_message("\nYou return to the ruined waystation.")

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game)
        state.phase = data.get("phase", "main_menu")
        return state
