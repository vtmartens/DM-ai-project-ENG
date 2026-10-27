"""Nessa's tiered Underroad black market."""

from core.black_market import (
    black_market_entries,
    black_market_state,
    buy_black_market_item,
)
from states.base_state import BaseGameState
from util.helpers import press_enter


class BlackMarketState(BaseGameState):
    """Menu-driven contraband shop in the cleared Underroad."""

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "black_market"
        self.phase = "menu"
        self.last_input = None

    def available_actions(self, game=None):
        player = (game or self.game).player
        entries = [
            entry["name"]
            for entry in black_market_entries(player)
            if entry.get("available") and not entry.get("purchased")
        ]
        return entries + ["leave"]

    def run(self, game):
        state = black_market_state(game.player)
        game.io.show_message("\n=== NESSA'S CACHE ===")
        game.io.show_message(
            "A false wall slides aside behind the smugglers' crates. Nessa "
            "keeps a small counter of goods the Watch never sees."
        )
        game.io.show_message(
            f"Standing: {state['tier_label']} "
            f"(Underroad +{state['reputation']}) · Gold: {state['gold']}"
        )
        if state["discount"]:
            game.io.show_message(
                f"Your standing earns a {state['discount']}% discount."
            )

        entries = state["items"]
        if not entries:
            game.io.show_message("The cache is empty.")
            game.io.show_message("1. Leave")
        else:
            game.io.show_message("\nWhat do you want to buy?")
            for index, entry in enumerate(entries, 1):
                status = ""
                if not entry["available"]:
                    status = f" [locked: {entry['tier_label']}]"
                elif entry["purchased"]:
                    status = " [sold]"
                game.io.show_message(
                    f"{index}. {entry['name']} — {entry['price']} gold"
                    f"{status}"
                )
                if entry.get("description"):
                    game.io.show_message(
                        f"   {entry['description']}"
                    )
                if entry.get("reasons"):
                    game.io.show_message(
                        "   " + "; ".join(entry["reasons"])
                    )
            game.io.show_message(f"{len(entries) + 1}. Leave")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if not entries:
            self._leave(game)
            return
        if choice in {str(len(entries) + 1), "leave", "back", "exit"}:
            self._leave(game)
            return

        selected = None
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(entries):
                selected = entries[index]
        else:
            selected = next(
                (
                    entry
                    for entry in entries
                    if choice
                    in {
                        str(entry.get("name", "")).casefold(),
                        str(entry.get("type", "")).casefold(),
                    }
                ),
                None,
            )

        if selected is None:
            game.io.show_message("Nessa does not stock that.")
        else:
            buy_black_market_item(
                game.player, selected["name"], game
            )

        self.phase = "menu"
        press_enter(game)

    def _leave(self, game):
        game.io.show_message("\nNessa closes the false wall behind you.")
        game.pop_state()

    def resume(self, game):
        game.io.show_message("\nNessa waits beside the hidden cache.")

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game)
        state.phase = data.get("phase", "menu")
        return state
