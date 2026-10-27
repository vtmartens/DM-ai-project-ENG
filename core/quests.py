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

    quest = {
        "id": quest_id,
        "title": definition.get("title", quest_id),
        "description": definition.get("description", ""),
        "objective": definition.get("objective", ""),
        "target": definition.get("target", ""),
        "status": "active",
    }
    player.active_quests.append(quest)
    player.progress_quests[quest_id] = {"status": "active"}
    if game:
        game.io.show_message(f"\nQuest started: {quest['title']}")
        if quest["objective"]:
            game.io.show_message(f"Objective: {quest['objective']}")
    return True


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
    player.progress_quests.setdefault(quest_id, {})["status"] = "completed"

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
    return True


def record_enemy_defeat(player, enemy_name, game=None):
    """Completes any active quest whose target was just defeated."""
    completed = []
    for quest in list(getattr(player, "active_quests", [])):
        if not isinstance(quest, dict):
            continue
        if _normalize(quest.get("target")) == _normalize(enemy_name):
            if complete_quest(player, quest.get("id"), game):
                completed.append(quest.get("id"))
    return completed


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
