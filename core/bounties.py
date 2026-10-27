"""Repeatable goal framing on top of the quest log's bounty definitions."""

from __future__ import annotations

from core.quests import complete_quest, quest_catalogue, start_quest

MAX_ACTIVE_BOUNTIES = 2


def bounty_definitions() -> dict:
    return {
        quest_id: definition
        for quest_id, definition in quest_catalogue().items()
        if isinstance(definition, dict) and definition.get("bounty")
    }


def _active_quest(player, bounty_id):
    for quest in getattr(player, "active_quests", []) or []:
        if isinstance(quest, dict) and quest.get("id") == bounty_id:
            return quest
    return None


def _completed(player, bounty_id):
    return any(
        isinstance(quest, dict) and quest.get("id") == bounty_id
        for quest in getattr(player, "completed_quests", []) or []
    )


def bounty_progress(player, bounty_id) -> tuple[int, int]:
    active = _active_quest(player, bounty_id)
    if not isinstance(active, dict):
        return 0, 0
    progress = getattr(player, "progress_quests", {}).get(bounty_id, {})
    current = int(progress.get("progress", active.get("progress", 0)) or 0)
    required = int(active.get("target_count", 1) or 1)
    return current, required


def bounty_status(player, bounty_id) -> str:
    active = _active_quest(player, bounty_id)
    if isinstance(active, dict):
        return "ready" if active.get("status") == "ready" else "active"
    if _completed(player, bounty_id):
        definition = bounty_definitions().get(bounty_id, {})
        return "available" if definition.get("repeatable") else "completed"
    return "available"


def bounty_entries(player) -> list[dict]:
    entries = []
    for bounty_id, definition in bounty_definitions().items():
        current, required = bounty_progress(player, bounty_id)
        reward = definition.get("reward", {})
        entries.append(
            {
                "id": bounty_id,
                "title": definition.get("title", bounty_id),
                "description": definition.get("description", ""),
                "objective": definition.get("objective", ""),
                "reward": dict(reward) if isinstance(reward, dict) else {},
                "status": bounty_status(player, bounty_id),
                "progress": current,
                "target_count": required,
            }
        )
    return entries


def active_bounty_count(player) -> int:
    return sum(
        1
        for quest in getattr(player, "active_quests", []) or []
        if isinstance(quest, dict) and quest.get("bounty")
    )


def accept_bounty(player, bounty_id, game=None) -> bool:
    definition = bounty_definitions().get(bounty_id)
    if definition is None:
        if game:
            game.io.show_message("That contract is not on the board.")
        return False

    if bounty_status(player, bounty_id) != "available":
        if game:
            game.io.show_message("That contract is already in your log.")
        return False

    if active_bounty_count(player) >= MAX_ACTIVE_BOUNTIES:
        if game:
            game.io.show_message(
                f"You can carry at most {MAX_ACTIVE_BOUNTIES} active bounties. "
                "Finish one before taking another."
            )
        return False

    return start_quest(player, bounty_id, game)


def claim_bounty(player, bounty_id, game=None) -> bool:
    if bounty_status(player, bounty_id) != "ready":
        if game:
            game.io.show_message("That bounty is not ready to claim yet.")
        return False
    claimed = complete_quest(player, bounty_id, game)
    if claimed:
        from core.achievements import record_event

        record_event(player, "bounty_claimed", game=game)
    return claimed
