"""Non-combat road events on the Trade Road."""

from __future__ import annotations

from core.checks import skill_check
from core.item_catalogue import item_definition
from core.road_events import grant_event_reward, mark_event_claimed
from core.shop import buy_item
from states.base_state import BaseGameState
from util.helpers import press_enter


class RoadEventState(BaseGameState):
    """A small choice-driven roadside encounter."""

    def __init__(self, event=None, game=None):
        super().__init__(game)
        self.state_name = "road_event"
        self.event = dict(event) if isinstance(event, dict) else {}
        self.phase = "main_menu"
        self.last_input = None

    def available_actions(self) -> list[str]:
        event_type = self.event.get("type")
        if event_type == "merchant":
            stock = [
                name
                for name in self.event.get("stock", []) or []
                if item_definition(name) is not None
            ]
            return [*stock, "leave"]
        if event_type == "shrine":
            return ["pray", "leave"]
        if event_type == "wagon":
            return ["search", "leave"]
        if event_type == "traveler":
            return ["help", "leave"]
        return ["leave"]

    def run(self, game):
        if not self.event:
            if game.current_state():
                game.pop_state()
            return
        if self.phase == "main_menu":
            event_type = self.event.get("type")
            if event_type == "merchant":
                self._merchant_menu(game)
            elif event_type == "shrine":
                self._shrine_menu(game)
            elif event_type == "wagon":
                self._wagon_menu(game)
            elif event_type == "traveler":
                self._traveler_menu(game)
            else:
                if game.current_state():
                    game.pop_state()
        else:
            self.phase = "main_menu"
            self.run(game)

    def _show_header(self, game):
        game.io.show_message(
            f"\n=== {self.event.get('title', 'ROAD EVENT')} ==="
        )
        description = self.event.get("description", "")
        if description:
            game.io.show_message(description)

    def _leave(self, game):
        if game.current_state():
            game.pop_state()

    def _claimed(self, player):
        flag = self.event.get("reward_flag")
        return flag in (getattr(player, "claimed_rewards", []) or [])

    def _merchant_menu(self, game):
        self._show_header(game)
        player = game.player
        stock = []
        for name in self.event.get("stock", []) or []:
            definition = item_definition(name)
            if definition is not None:
                stock.append(definition)

        game.io.show_message(f"\nGold: {player.gold}")
        if not stock:
            game.io.show_message("The merchant has nothing left to sell.")
            game.io.show_message("0. Leave")
            choice = str(
                game.io.request_input("\nChoice: ") or ""
            ).strip().casefold()
            self.last_input = choice
            self._leave(game)
            return

        for index, definition in enumerate(stock, 1):
            game.io.show_message(
                f"{index}. {definition.get('name')} — "
                f"{int(definition.get('value', 0) or 0)} gold"
            )
        game.io.show_message("0. Leave")

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice
        if choice in {"0", "leave", "back", "exit"}:
            self._leave(game)
            return

        selected = None
        if choice.isdigit():
            position = int(choice) - 1
            if 0 <= position < len(stock):
                selected = stock[position]
        else:
            matches = [
                definition
                for definition in stock
                if choice in str(definition.get("name", "")).casefold()
            ]
            if len(matches) == 1:
                selected = matches[0]

        if selected is None:
            game.io.show_message("The merchant does not have that.")
        else:
            buy_item(player, selected.get("name"), game)

        self.phase = "main_menu"
        press_enter(game)

    def _shrine_menu(self, game):
        self._show_header(game)
        player = game.player
        if self._claimed(player):
            game.io.show_message(
                "\nThe shrine is quiet now. Its blessing has already been spent."
            )
            game.io.show_message("1. Leave")
            choice = str(
                game.io.request_input("\nChoice: ") or ""
            ).strip().casefold()
            self.last_input = choice
            self._leave(game)
            return

        game.io.show_message("\n1. Kneel and pray")
        game.io.show_message("2. Leave")
        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if choice in {"1", "pray", "kneel"}:
            amount = max(0, int(self.event.get("heal", 0) or 0))
            before = player.hp
            player.hp = min(player.hp_max, player.hp + amount)
            if self.event.get("clear_conditions"):
                conditions = getattr(player, "conditions", None)
                if isinstance(conditions, dict):
                    conditions.clear()
            mark_event_claimed(player, self.event)
            game.io.show_message(
                f"You kneel at the shrine. The water restores "
                f"{player.hp - before} HP"
                + (" and clears your conditions." if self.event.get("clear_conditions") else ".")
            )
        elif choice in {"2", "leave", "back", "exit"}:
            self._leave(game)
            return
        else:
            game.io.show_message("Invalid choice.")

        self.phase = "main_menu"
        press_enter(game)

    def _wagon_menu(self, game):
        self._show_header(game)
        player = game.player
        if self._claimed(player):
            game.io.show_message("\nThe wagon has already been searched.")
            game.io.show_message("1. Leave")
            choice = str(
                game.io.request_input("\nChoice: ") or ""
            ).strip().casefold()
            self.last_input = choice
            self._leave(game)
            return

        game.io.show_message("\n1. Search the wagon")
        game.io.show_message("2. Leave")
        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if choice in {"1", "search", "investigate", "loot"}:
            check = self.event.get("check", {}) or {}
            passed = skill_check(
                player,
                str(check.get("skill", "investigation")),
                int(check.get("dc", 12) or 12),
                game,
            )
            if passed:
                granted = grant_event_reward(
                    player, self.event.get("reward", {}), game
                )
                mark_event_claimed(player, self.event)
                game.io.show_message(
                    "You find a strongbox beneath the driver's bench."
                )
                if granted:
                    game.io.show_message(
                        "You recover: " + ", ".join(granted) + "."
                    )
            else:
                game.io.show_message(
                    "The strongbox is jammed. You cannot open it this time."
                )
        elif choice in {"2", "leave", "back", "exit"}:
            self._leave(game)
            return
        else:
            game.io.show_message("Invalid choice.")

        self.phase = "main_menu"
        press_enter(game)

    def _traveler_menu(self, game):
        self._show_header(game)
        player = game.player
        if self._claimed(player):
            game.io.show_message("\nThe traveller has already moved on.")
            game.io.show_message("1. Leave")
            choice = str(
                game.io.request_input("\nChoice: ") or ""
            ).strip().casefold()
            self.last_input = choice
            self._leave(game)
            return

        game.io.show_message("\n1. Help the traveller")
        game.io.show_message("2. Leave")
        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip().casefold()
        self.last_input = choice

        if choice in {"1", "help", "aid"}:
            granted = grant_event_reward(
                player, self.event.get("reward", {}), game
            )
            mark_event_claimed(player, self.event)
            game.io.show_message(
                "You bind the traveller's wound and share what you can. "
                "They press a reward into your hand."
            )
            if granted:
                game.io.show_message(
                    "You receive: " + ", ".join(granted) + "."
                )
        elif choice in {"2", "leave", "back", "exit"}:
            self._leave(game)
            return
        else:
            game.io.show_message("Invalid choice.")

        self.phase = "main_menu"
        press_enter(game)

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        data["event"] = dict(self.event)
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(data.get("event"), game)
        state.phase = data.get("phase", "main_menu")
        return state
