"""The Underroad: the smuggler chapter beneath the Broken Waystation."""

from core.item_catalogue import item_definition
from core.quests import start_quest
from items.item import Item
from states.base_state import BaseGameState
from util.helpers import press_enter


class UnderroadState(BaseGameState):
    """Menu-driven chapter area with a boss and a one-time cache."""

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "underroad"
        self.phase = "main_menu"
        self.last_input = None

    def available_actions(self, game=None):
        game = game or getattr(self, "game", None)
        if game is not None and self._cleared(game.player):
            actions = [
                "confront",
                "cache",
                "sanctum",
                "talk to Nessa",
            ]
            from core.black_market import black_market_unlocked

            if black_market_unlocked(game.player):
                actions.append("Nessa's cache")
            actions.append("leave")
            return actions
        return ["confront", "cache", "leave"]

    def run(self, game):
        self._ensure_map(game)
        self._ensure_quest(game)
        if self.phase == "main_menu":
            self._main_menu(game)
        else:
            self.phase = "main_menu"
            self.run(game)

    def _ensure_map(self, game):
        map_obj = game.map_manager.get_map("underroad")
        if map_obj is None:
            return
        game.map_manager.set_current_map("underroad")
        if (
            game.player.current_map != "underroad"
            or not map_obj.is_valid_position(game.player.x, game.player.y)
        ):
            x, y = map_obj.player_start_position
            game.player.set_position("underroad", x, y)

    def _ensure_quest(self, game):
        player = game.player
        active = {
            quest.get("id")
            for quest in getattr(player, "active_quests", []) or []
            if isinstance(quest, dict)
        }
        completed = {
            quest.get("id")
            for quest in getattr(player, "completed_quests", []) or []
            if isinstance(quest, dict)
        }
        if "underroad_chapter" not in active | completed:
            start_quest(player, "underroad_chapter", game)

    @staticmethod
    def _cleared(player):
        return "underroad" in (
            getattr(player, "cleared_areas", []) or []
        )

    @staticmethod
    def _looted(player):
        return "underroad_cache" in (
            getattr(player, "claimed_rewards", []) or []
        )

    def _main_menu(self, game):
        player = game.player
        cleared = self._cleared(player)

        game.io.show_message("\n=== THE UNDERROAD ===")
        if cleared:
            game.io.show_message(
                "The smuggler tunnel is quiet now. Crates and old lanterns "
                "line the walls, and a locked cache waits in the shadows."
            )
        else:
            game.io.show_message(
                "A low tunnel runs beneath the waystation. Shadowed runners "
                "guard the route, and their lord holds court beyond them."
            )
        game.io.show_message(f"Gold: {player.gold}")
        game.io.show_message("\nWhat do you want to do?")
        game.io.show_message(
            "1. The Underroad is quiet"
            if cleared
            else "1. Confront the smugglers"
        )
        game.io.show_message("2. Open the smugglers' cache")
        game.io.show_message("3. Return to the waystation")
        if cleared:
            game.io.show_message("4. Enter the Sealed Sanctum")
            game.io.show_message("5. Speak with Nessa")
            from core.black_market import black_market_unlocked

            if black_market_unlocked(player):
                game.io.show_message("6. Visit Nessa's cache")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if choice in {
            "1",
            "confront",
            "advance",
            "tunnel",
            "fight",
            "smugglers",
        }:
            if self._confront(game):
                return
        elif choice in {"2", "cache", "loot", "strongbox"}:
            open_cache = self._open_cache(game)
            if open_cache:
                press_enter(game)
                self.phase = "main_menu"
                return
        elif choice in {"4", "sanctum", "sealed", "ward"}:
            if self._enter_sanctum(game):
                return
        elif choice in {
            "5",
            "nessa",
            "talk to nessa",
            "speak with nessa",
            "talk",
        }:
            if self._talk_to_nessa(game):
                return
        elif choice in {
            "6",
            "black market",
            "black_market",
            "nessa's cache",
            "nessas cache",
            "runner's cache",
            "runners cache",
            "smugglers market",
        }:
            if self._open_black_market(game):
                return
        elif choice in {"3", "leave", "return", "waystation", "exit"}:
            self._leave(game)
            return
        else:
            game.io.show_message("Invalid choice.")

        self.phase = "main_menu"
        press_enter(game)

    def _confront(self, game):
        if self._cleared(game.player):
            game.io.show_message("The Underroad is already clear.")
            return False

        from core.encounters import build_encounter
        from core.quests import build_ally_party
        from states.combat import CombatState

        encounter = build_encounter("underroad_boss")
        if encounter is None:
            game.io.show_message("The smugglers cannot be found.")
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

    def _open_cache(self, game):
        player = game.player
        if not self._cleared(player):
            game.io.show_message(
                "The smugglers still hold the Underroad. The cache is not safe."
            )
            return False
        if self._looted(player):
            game.io.show_message("The smugglers' cache is empty.")
            return False

        definition = item_definition("Underroad Signet")
        if definition is not None:
            player.add_item(Item.from_dict(definition))
            game.io.show_message(
                "You open the cache and find the Underroad Signet!"
            )

        claimed = getattr(player, "claimed_rewards", None)
        if not isinstance(claimed, list):
            claimed = []
            player.claimed_rewards = claimed
        claimed.append("underroad_cache")
        player.add_gold(75, game)
        return True

    def _enter_sanctum(self, game):
        player = game.player
        if not self._cleared(player):
            game.io.show_message(
                "The smugglers still hold the Underroad. The sealed door "
                "will not open while they remain."
            )
            return False
        if "underroad_cache" not in (
            getattr(player, "claimed_rewards", []) or []
        ):
            game.io.show_message(
                "A signet-shaped hollow waits in the sealed door. Open the "
                "smugglers' cache first."
            )
            return False

        game.io.show_message(
            "The Underroad Signet fits the hollow. Runes wake along the "
            "sealed door and it grinds open onto the sanctum."
        )
        game.map_manager.set_current_map("sanctum")
        game.player.set_position("sanctum", 2, 7)
        from states.sanctum import SanctumState

        game.change_state(SanctumState(game))
        return True

    def _talk_to_nessa(self, game):
        """Opens the surviving runner's dialogue from the cleared tunnel."""
        if not self._cleared(game.player):
            game.io.show_message(
                "The tunnel is still held by the smugglers. No one is "
                "waiting to talk."
            )
            return False

        from entities.npc import NPC
        from states.dialogue import DialogueState

        game.push_state(DialogueState(NPC("Nessa")))
        return True

    def _open_black_market(self, game):
        """Opens Nessa's cache once the side quest and standing allow it."""
        from core.black_market import black_market_unlocked
        from states.black_market import BlackMarketState

        if not self._cleared(game.player):
            game.io.show_message(
                "The smugglers still hold the tunnel. Nessa's cache is not "
                "open."
            )
            return False
        if not black_market_unlocked(game.player):
            game.io.show_message(
                "Nessa's cache is closed. Finish The Quiet Cargo and earn "
                "the Underroad's trust."
            )
            return False

        game.push_state(BlackMarketState(game))
        return True

    def _leave(self, game):
        game.io.show_message(
            "You follow the tunnel back up to the Broken Waystation."
        )
        game.map_manager.set_current_map("waystation")
        game.player.set_position("waystation", 5, 7)
        from states.waystation import WaystationState

        game.change_state(WaystationState(game))

    def resume(self, game):
        if self._cleared(game.player):
            game.io.show_message("\nThe Underroad is quiet.")
        else:
            game.io.show_message("\nYou return to the smuggler tunnel.")

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game)
        state.phase = data.get("phase", "main_menu")
        return state
