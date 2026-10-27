"""Tavern bounty board for accepting and claiming bounty quests."""

from core.bounties import (
    accept_bounty,
    bounty_entries,
    claim_bounty,
)
from states.base_state import BaseGameState
from util.helpers import press_enter


class BountyBoardState(BaseGameState):
    """Lists available, active and claimable bounty contracts."""

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "bounty_board"
        self.phase = "main_menu"
        self.last_input = None

    def run(self, game):
        if self.phase == "main_menu":
            self._main_menu(game)
        else:
            self.phase = "main_menu"
            self.run(game)

    def _main_menu(self, game):
        player = game.player
        entries = bounty_entries(player)

        game.io.show_message("\n=== BOUNTY BOARD ===")
        game.io.show_message(f"Gold: {player.gold}")
        if not entries:
            game.io.show_message("There are no contracts on the board.")
            press_enter(game)
            if game.current_state():
                game.pop_state()
            return

        for index, entry in enumerate(entries, 1):
            reward = entry.get("reward", {})
            reward_parts = []
            if reward.get("gold"):
                reward_parts.append(f"{reward['gold']} gold")
            if reward.get("experience"):
                reward_parts.append(f"{reward['experience']} XP")
            if reward.get("items"):
                reward_parts.append(", ".join(reward["items"]))
            reward_text = (
                "Reward: " + ", ".join(reward_parts)
                if reward_parts
                else "Reward: none"
            )

            status = entry["status"]
            if status == "active":
                status_text = (
                    f"in progress ({entry['progress']}/"
                    f"{entry['target_count']})"
                )
            elif status == "ready":
                status_text = "ready to claim"
            else:
                status_text = status

            game.io.show_message(
                f"{index}. {entry['title']} — {entry['objective']} "
                f"[{status_text}]"
            )
            game.io.show_message(f"   {reward_text}")
        game.io.show_message("0. Leave")
        game.io.show_message(
            "\nChoose a contract number to accept or claim, "
            "or use 'accept N' / 'claim N'."
        )

        choice = str(
            game.io.request_input("\nChoice: ") or ""
        ).strip()
        self.last_input = choice
        low = choice.casefold()

        if low in {"0", "leave", "back", "exit"}:
            if game.current_state():
                game.pop_state()
            return

        action = None
        selected = None
        words = low.split()
        if words == ["accept"] or words == ["take"]:
            action = "accept"
            selected = next(
                (
                    entry
                    for entry in entries
                    if entry["status"] == "available"
                ),
                None,
            )
        elif words == ["claim"] or words == ["turn"]:
            action = "claim"
            selected = next(
                (
                    entry
                    for entry in entries
                    if entry["status"] == "ready"
                ),
                None,
            )
        elif len(words) == 2 and words[0] in {"accept", "take"}:
            action = "accept"
            token = words[1]
            if token.isdigit():
                position = int(token) - 1
                if 0 <= position < len(entries):
                    selected = entries[position]
        elif len(words) == 2 and words[0] in {"claim", "turn"}:
            action = "claim"
            token = words[1]
            if token.isdigit():
                position = int(token) - 1
                if 0 <= position < len(entries):
                    selected = entries[position]
        elif low.isdigit():
            position = int(low) - 1
            if 0 <= position < len(entries):
                selected = entries[position]
                if selected["status"] == "available":
                    action = "accept"
                elif selected["status"] == "ready":
                    action = "claim"

        if selected is None:
            if action == "accept":
                game.io.show_message("No new contracts are available.")
            elif action == "claim":
                game.io.show_message("No bounties are ready to claim.")
            else:
                game.io.show_message("Choose a valid contract number.")
            press_enter(game)
            self.phase = "main_menu"
            return

        if action == "accept":
            accept_bounty(player, selected["id"], game)
        elif action == "claim":
            claim_bounty(player, selected["id"], game)
        elif selected["status"] == "active":
            game.io.show_message(
                f"{selected['title']} is in progress: "
                f"{selected['progress']}/{selected['target_count']}."
            )
        elif selected["status"] == "completed":
            game.io.show_message(f"{selected['title']} is already complete.")
        else:
            game.io.show_message("That contract cannot be used right now.")

        self.phase = "main_menu"
        press_enter(game)

    def to_dict(self):
        data = super().to_dict()
        data["phase"] = self.phase
        return data

    @classmethod
    def from_dict(cls, data, game=None):
        state = cls(game)
        state.phase = data.get("phase", "main_menu")
        return state
