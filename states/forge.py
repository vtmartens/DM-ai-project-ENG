"""The Sanctum Forge: Rune Shard crafting."""

from core.crafting import (
    craft_recipe,
    recipe_entries,
    rune_shards,
)
from states.base_state import BaseGameState
from states.sanctum import SanctumState
from util.helpers import press_enter


class ForgeState(BaseGameState):
    """Menu-driven crafting station in the cleared Sanctum."""

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "forge"
        self.phase = "menu"
        self.last_input = None

    def available_actions(self, game=None):
        return [entry["id"] for entry in recipe_entries(self.game.player)] + [
            "leave"
        ]

    def run(self, game):
        game.io.show_message("\n=== THE SANCTUM FORGE ===")
        game.io.show_message(
            "Rune-light pools in a basin of black stone. Shards from the "
            "trials can be worked into potions and living-metal gear."
        )
        game.io.show_message(
            f"Rune Shards: {rune_shards(game.player)} · Gold: {game.player.gold}"
        )
        entries = recipe_entries(game.player)
        if not entries:
            game.io.show_message("The forge has no recipes.")
            game.io.show_message("0. Leave")
        else:
            game.io.show_message("\nWhat will you forge?")
            for index, entry in enumerate(entries, 1):
                status = " [forged]" if entry.get("crafted") else ""
                game.io.show_message(
                    f"{index}. {entry['name']} — {entry['shards']} shards, "
                    f"{entry['gold']} gold → {entry['result']}{status}"
                )
                if entry.get("reasons"):
                    game.io.show_message(
                        "   " + "; ".join(entry["reasons"])
                    )
            game.io.show_message(f"{len(entries) + 1}. Leave the forge")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if not entries:
            self._leave(game)
            return
        if choice in {str(len(entries) + 1), "0", "leave", "back", "exit"}:
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
                    if choice in {
                        str(entry.get("id", "")).casefold(),
                        str(entry.get("name", "")).casefold(),
                    }
                ),
                None,
            )

        if selected is None:
            game.io.show_message("The forge does not know that recipe.")
        else:
            craft_recipe(game.player, selected["id"], game)

        self.phase = "menu"
        press_enter(game)

    def _leave(self, game):
        game.io.show_message("You step away from the Rune Forge.")
        game.change_state(SanctumState(game))

    def resume(self, game):
        game.io.show_message("\nThe Rune Forge waits for your next command.")

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game)
        state.phase = data.get("phase", "menu")
        return state
