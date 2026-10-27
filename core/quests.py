"""Quest state, rewards and recruitable combat allies."""

from __future__ import annotations

from util.data_manager import get_data_manager


def _normalize(value) -> str:
    return (
        str(value or "")
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .casefold()
    )


def quest_catalogue():
    data = get_data_manager().get_quests()
    return data if isinstance(data, dict) else {}


def _active_ids(player):
    return {
        quest.get("id")
        for quest in getattr(player, "active_quests", [])
        if isinstance(quest, dict)
    }


def _completed_ids(player):
    return {
        quest.get("id")
        for quest in getattr(player, "completed_quests", [])
        if isinstance(quest, dict)
    }


def start_quest(player, quest_id, game=None):
    """Adds a quest to the player's log. Returns True if it was new."""
    definition = quest_catalogue().get(quest_id)
    if not isinstance(definition, dict):
        if game:
            game.io.show_message(f"Unknown quest: {quest_id}.")
        return False

    if quest_id in _active_ids(player) or quest_id in _completed_ids(player):
        if game:
            game.io.show_message(f"You already know about {definition['title']}.")
        return False

    if not isinstance(getattr(player, "progress_quests", None), dict):
        player.progress_quests = {}

    quest = {
        "id": quest_id,
        "title": definition.get("title", quest_id),
        "description": definition.get("description", ""),
        "objective": definition.get("objective", ""),
        "target": definition.get("target", ""),
        "turn_in": definition.get("turn_in", ""),
        "status": "active",
    }
    player.active_quests.append(quest)
    player.progress_quests[quest_id] = {
        "status": "active",
        "combat_encounters": 0,
    }
    if game:
        game.io.show_message(f"\nQuest started: {quest['title']}")
        if quest["objective"]:
            game.io.show_message(f"Objective: {quest['objective']}")
    return True


def record_combat(player):
    """Notes that a fight happened while the player's active quests were open.

    ``diplomacy`` asks for a quest completed without fighting, so the count is
    per quest and only advances while that quest is active.
    """
    progress = getattr(player, "progress_quests", None)
    if not isinstance(progress, dict):
        return
    for quest in getattr(player, "active_quests", []):
        if not isinstance(quest, dict):
            continue
        quest_id = quest.get("id")
        if not quest_id:
            continue
        entry = progress.setdefault(quest_id, {})
        entry["combat_encounters"] = int(entry.get("combat_encounters", 0) or 0) + 1


def mark_quest_ready(player, quest_id, game=None):
    """Marks an active quest's objective complete without granting rewards."""
    for quest in getattr(player, "active_quests", []):
        if not isinstance(quest, dict) or quest.get("id") != quest_id:
            continue
        if quest.get("status") == "ready":
            return False

        quest["status"] = "ready"
        if not isinstance(getattr(player, "progress_quests", None), dict):
            player.progress_quests = {}
        player.progress_quests.setdefault(quest_id, {})["status"] = "ready"

        if game:
            game.io.show_message(
                f"\nObjective complete: {quest.get('title', quest_id)}"
            )
            turn_in = quest.get("turn_in")
            if turn_in:
                game.io.show_message(
                    f"Return to {turn_in} to collect your reward."
                )
        return True
    return False


def complete_quest(player, quest_id, game=None):
    """Moves a quest to the completed list and grants its reward."""
    definition = quest_catalogue().get(quest_id, {})
    active = [
        quest
        for quest in getattr(player, "active_quests", [])
        if isinstance(quest, dict) and quest.get("id") == quest_id
    ]
    if not active:
        return False

    player.active_quests = [
        quest
        for quest in player.active_quests
        if not (isinstance(quest, dict) and quest.get("id") == quest_id)
    ]
    completed = dict(active[0])
    completed["status"] = "completed"
    player.completed_quests.append(completed)
    progress = player.progress_quests.setdefault(quest_id, {})
    progress["status"] = "completed"
    combat_encounters = int(progress.get("combat_encounters", 0) or 0)

    reward = definition.get("reward", {}) if isinstance(definition, dict) else {}
    gold = int(reward.get("gold", 0) or 0)
    experience = int(reward.get("experience", 0) or 0)
    if gold:
        player.gold += gold
    if experience:
        player.gain_experience(experience, game)

    if game:
        game.io.show_message(f"\nQuest complete: {completed.get('title', quest_id)}")
        if gold:
            game.io.show_message(f"Reward: {gold} gold coins.")
        if experience:
            game.io.show_message(f"Reward: {experience} experience points.")

    from core.achievements import record_event

    record_event(
        player,
        "quest_completed",
        game=game,
        combat_encounters=combat_encounters,
    )
    return True


def record_enemy_defeat(player, enemy_name, game=None):
    """Marks target quests ready (or completes quests without a turn-in NPC)."""
    changed = []
    for quest in list(getattr(player, "active_quests", [])):
        if not isinstance(quest, dict):
            continue
        if _normalize(quest.get("target")) != _normalize(enemy_name):
            continue

        quest_id = quest.get("id")
        turn_in = quest.get("turn_in")
        if turn_in:
            if mark_quest_ready(player, quest_id, game):
                changed.append(quest_id)
        elif complete_quest(player, quest_id, game):
            changed.append(quest_id)
    return changed


def recruit_ally(player, npc_name, game=None):
    """Adds a named NPC to the player's combat party."""
    allies = getattr(player, "allies", None)
    if not isinstance(allies, list):
        allies = []
        player.allies = allies
    if npc_name in allies:
        if game:
            game.io.show_message(f"{npc_name} is already travelling with you.")
        return False
    allies.append(npc_name)
    if game:
        game.io.show_message(f"{npc_name} joins you.")
    return True


def build_ally_party(player):
    """Creates the NPC combatants for the player's recruited allies."""
    from entities.npc import NPC

    party = []
    for npc_name in getattr(player, "allies", []) or []:
        if not isinstance(npc_name, str):
            continue
        ally = NPC(npc_name)
        if getattr(ally, "hp", 0) > 0:
            party.append(ally)
    return party
