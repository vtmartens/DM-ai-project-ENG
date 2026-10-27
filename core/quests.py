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

    if quest_id in _active_ids(player) or (
        quest_id in _completed_ids(player)
        and not definition.get("repeatable")
    ):
        if game:
            game.io.show_message(f"You already know about {definition['title']}.")
        return False

    if definition.get("repeatable"):
        # Keep only the latest completion record for a repeatable contract.
        player.completed_quests = [
            quest
            for quest in getattr(player, "completed_quests", [])
            if not (
                isinstance(quest, dict) and quest.get("id") == quest_id
            )
        ]

    if not isinstance(getattr(player, "progress_quests", None), dict):
        player.progress_quests = {}

    quest = {
        "id": quest_id,
        "title": definition.get("title", quest_id),
        "description": definition.get("description", ""),
        "objective": definition.get("objective", ""),
        "target": definition.get("target", ""),
        "target_item": definition.get("target_item", ""),
        "target_type": definition.get("target_type", ""),
        "target_count": int(definition.get("target_count", 1) or 1),
        "bounty": bool(definition.get("bounty", False)),
        "turn_in": definition.get("turn_in", ""),
        "status": "active",
    }
    player.active_quests.append(quest)
    player.progress_quests[quest_id] = {
        "status": "active",
        "combat_encounters": 0,
        "progress": 0,
    }
    if game:
        game.io.show_message(f"\nQuest started: {quest['title']}")
        if quest["objective"]:
            game.io.show_message(f"Objective: {quest['objective']}")

    # The player may already carry an item-based objective (for example if
    # they explored the vault before accepting the quest).
    target_item = quest.get("target_item")
    if target_item and any(
        _normalize(getattr(item, "name", item)) == _normalize(target_item)
        for item in getattr(player, "inventory", [])
    ):
        mark_quest_ready(player, quest_id, game)

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


def record_item_acquired(player, item_name, game=None):
    """Marks active quests whose ``target_item`` was just acquired."""
    if not item_name:
        return []

    wanted = _normalize(item_name)
    changed = []
    for quest in list(getattr(player, "active_quests", [])):
        if not isinstance(quest, dict):
            continue
        if quest.get("status") == "ready":
            continue
        target_item = quest.get("target_item")
        if not target_item or _normalize(target_item) != wanted:
            continue
        game_ctx = game if game is not None else getattr(player, "game", None)
        if mark_quest_ready(player, quest.get("id"), game_ctx):
            changed.append(quest.get("id"))
    return changed


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


ITEM_FILES = (
    "weapons.json",
    "armor.json",
    "accessories.json",
    "keys.json",
    "potions.json",
)


def _reward_item(item_name):
    """Builds an Item from the data files, or None when it is not defined."""
    if not item_name:
        return None

    from items.item import Item

    data_manager = get_data_manager()
    wanted = _normalize(item_name)
    for file_name in ITEM_FILES:
        for data in data_manager.load_data("items", file_name):
            if (
                isinstance(data, dict)
                and _normalize(data.get("name")) == wanted
            ):
                return Item.from_dict(data)
    return None


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
    reward_items = reward.get("items", []) if isinstance(reward, dict) else []
    granted = []

    from core.cycles import reward_multiplier

    cycle_multiplier = reward_multiplier(
        getattr(player, "cycle", 1)
    )
    gold = int(gold * cycle_multiplier)
    experience = int(experience * cycle_multiplier)

    faction_id = (
        definition.get("faction") if isinstance(definition, dict) else None
    )
    bonus_gold = 0
    if faction_id and gold:
        from core.factions import faction_bonus_percent

        percent = faction_bonus_percent(player, faction_id)
        bonus_gold = int(gold * percent / 100)

    total_gold = gold + bonus_gold
    if total_gold:
        player.gold += total_gold
    if experience:
        player.gain_experience(experience, game)
    for item_name in reward_items:
        item = _reward_item(item_name)
        if item is not None:
            player.add_item(item)
            granted.append(item_name)

    if game:
        game.io.show_message(f"\nQuest complete: {completed.get('title', quest_id)}")
        if total_gold:
            game.io.show_message(f"Reward: {total_gold} gold coins.")
        if bonus_gold:
            game.io.show_message(
                f"Faction bonus: +{bonus_gold} gold."
            )
        if experience:
            game.io.show_message(f"Reward: {experience} experience points.")
        if granted:
            game.io.show_message(f"Reward: {', '.join(granted)}.")

    if faction_id:
        from core.factions import adjust_reputation

        adjust_reputation(
            player,
            faction_id,
            int(definition.get("reputation", 0) or 0),
            game,
        )

    from core.achievements import record_event

    record_event(
        player,
        "quest_completed",
        game=game,
        combat_encounters=combat_encounters,
    )
    return True


def record_enemy_defeat(player, enemy_name, game=None, monster_type=None):
    """Marks target quests ready (or completes quests without a turn-in NPC).

    Bounty quests may track a monster type and a required count. Plain quests
    continue to match the exact target name.
    """
    if enemy_name:
        from core.achievements import record_event

        record_event(
            player,
            "enemy_defeated",
            game=game,
            enemy=enemy_name,
        )

    changed = []
    for quest in list(getattr(player, "active_quests", [])):
        if not isinstance(quest, dict):
            continue

        if quest.get("bounty"):
            if quest.get("status") == "ready":
                continue
            target_type = quest.get("target_type")
            target_name = quest.get("target")
            matches = False
            if target_type and monster_type:
                matches = _normalize(target_type) == _normalize(monster_type)
            if not matches and target_name:
                wanted = _normalize(target_name)
                actual = _normalize(enemy_name)
                matches = bool(wanted) and wanted in actual
            if not matches:
                continue

            quest_id = quest.get("id")
            progress = player.progress_quests.setdefault(quest_id, {})
            current = int(progress.get("progress", 0) or 0) + 1
            required = max(1, int(quest.get("target_count", 1) or 1))
            progress["progress"] = min(current, required)
            quest["progress"] = progress["progress"]
            quest["target_count"] = required
            if game:
                game.io.show_message(
                    f"Bounty progress: {progress['progress']}/{required}."
                )
            if progress["progress"] >= required:
                if mark_quest_ready(player, quest_id, game):
                    changed.append(quest_id)
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
