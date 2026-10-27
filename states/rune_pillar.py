"""The vault Rune Pillar: an Arcana check with a unique reward."""

from core.item_catalogue import item_definition
from items.item import Item
from states.base_state import BaseGameState
from util.dice import roll_d20
from util.helpers import press_enter


class RunePillarState(BaseGameState):
    ARCANA_DC = 15
    REWARD_FLAG = "vault_rune_pillar"

    def __init__(self, pillar=None, game=None):
        super().__init__(game)
        self.state_name = "rune_pillar"
        self.pillar = pillar
        self.phase = "main_menu"
        self.last_input = None

    def run(self, game):
        if self.phase == "main_menu":
            self._main_menu(game)
        else:
            self.phase = "main_menu"
            self.run(game)

    def _solved(self, player):
        claimed = getattr(player, "claimed_rewards", []) or []
        if self.REWARD_FLAG in claimed:
            return True
        return any(
            getattr(item, "name", None) == "Rune-Ward Amulet"
            for item in getattr(player, "inventory", []) or []
        )

    def _consume_guidance(self, player, game):
        conditions = getattr(player, "conditions", None)
        if not isinstance(conditions, dict):
            return 0
        guidance = conditions.pop("guidance", None)
        if isinstance(guidance, dict):
            bonus = int(guidance.get("bonus", 0) or 0)
        else:
            try:
                bonus = int(guidance or 0)
            except (TypeError, ValueError):
                bonus = 0
        if bonus:
            game.io.show_message(f"Guidance adds {bonus} to the check.")
        return bonus

    def _main_menu(self, game):
        player = game.player
        game.io.show_message("\n=== RUNE PILLAR ===")
        if self.pillar is not None:
            description = getattr(self.pillar, "description", "")
            if description:
                game.io.show_message(description)
        else:
            game.io.show_message(
                "A pillar of black stone is covered in warding runes."
            )

        if self._solved(player):
            game.io.show_message(
                "The runes are dormant now. You have already deciphered "
                "their ward."
            )
            game.io.show_message("\n1. Leave")
        else:
            game.io.show_message(
                "\nWhat do you want to do?"
            )
            game.io.show_message("1. Study the runes (Arcana DC 15)")
            game.io.show_message("2. Leave")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if self._solved(player):
            if choice in {"1", "leave", "back", "exit"}:
                if game.current_state():
                    game.pop_state()
                return
            game.io.show_message("The runes are dormant.")
            press_enter(game)
            return

        if choice in {"1", "study", "arcana", "check"}:
            self._study(game)
        elif choice in {"2", "leave", "back", "exit"}:
            if game.current_state():
                game.pop_state()
            return
        else:
            game.io.show_message("Invalid choice.")
        press_enter(game)

    def _study(self, game):
        player = game.player
        if self._solved(player):
            game.io.show_message("The runes are already deciphered.")
            return False

        advantage, disadvantage = player.roll_flags("check")
        roll, rolls = roll_d20(advantage, disadvantage)
        if rolls:
            mode = (
                "advantage"
                if advantage and not disadvantage
                else "disadvantage"
            )
            game.io.show_message(
                f"{mode.capitalize()} roll: {rolls[0]} / {rolls[1]} -> {roll}."
            )

        bonus = player.ability_modifier("arcana", game)
        guidance = self._consume_guidance(player, game)
        total = roll + bonus + guidance
        game.io.show_message(
            f"Arcana check: {roll} + {bonus} (INT"
            + (f", +{guidance} Guidance" if guidance else "")
            + f") = {total} vs DC {self.ARCANA_DC}."
        )

        if total < self.ARCANA_DC:
            player.hp = max(1, int(getattr(player, "hp", 0) or 0) - 2)
            game.io.show_message(
                "The runes flare and sear your mind. You take 2 damage."
            )
            return False

        definition = item_definition("Rune-Ward Amulet")
        if definition is not None:
            player.add_item(Item.from_dict(definition))
            game.io.show_message(
                "The runes unfold into a pattern you can read. "
                "You take the Rune-Ward Amulet from the hidden niche."
            )

        claimed = getattr(player, "claimed_rewards", None)
        if not isinstance(claimed, list):
            claimed = []
            player.claimed_rewards = claimed
        if self.REWARD_FLAG not in claimed:
            claimed.append(self.REWARD_FLAG)
        return True

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game=game)
        state.phase = data.get("phase", "main_menu")
        return state
