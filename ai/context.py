from __future__ import annotations

from typing import Any

from core.conditions import condition_catalogue
from core.factions import reputation_entries, shop_discount
from core.party import ally_loyalty, ally_stance


def _names(objects) -> list[str]:
    return [getattr(obj, "name", str(obj)) for obj in objects.values()]


def _condition_names(player) -> list[str]:
    conditions = getattr(player, "conditions", None)
    if not isinstance(conditions, dict):
        return []
    catalogue = condition_catalogue()
    names = []
    for condition_id in conditions:
        definition = catalogue.get(condition_id)
        if isinstance(definition, dict):
            names.append(definition.get("name", condition_id))
        else:
            names.append(str(condition_id).replace("_", " ").title())
    return names


def _active_quests(player) -> list[dict]:
    quests = []
    for quest in getattr(player, "active_quests", []) or []:
        if not isinstance(quest, dict):
            continue
        quests.append(
            {
                "id": quest.get("id"),
                "title": quest.get("title", quest.get("id", "")),
                "objective": quest.get("objective", ""),
                "status": quest.get("status", "active"),
                "turn_in": quest.get("turn_in", ""),
            }
        )
    return quests[:3]


def _campaign(player) -> dict:
    cleared = {
        str(area)
        for area in (getattr(player, "cleared_areas", []) or [])
        if isinstance(area, str)
    }
    claimed = {
        str(flag)
        for flag in (getattr(player, "claimed_rewards", []) or [])
        if isinstance(flag, str)
    }
    completed = {
        str(quest.get("id"))
        for quest in (getattr(player, "completed_quests", []) or [])
        if isinstance(quest, dict) and quest.get("id")
    }

    choice = None
    if "runeheart_kept" in claimed:
        choice = "kept"
    elif "runeheart_mirt" in claimed:
        choice = "mirt"
    elif "runeheart_violet" in claimed:
        choice = "violet"

    from core.omens import player_omen

    omen = player_omen(player)
    campaign = {
        "sanctum_cleared": "sanctum" in cleared,
        "runeheart_choice": choice,
        "sanctum_complete": "sanctum_chapter" in completed,
        "cycle_omen": omen["name"] if omen else None,
    }
    return {
        key: value
        for key, value in campaign.items()
        if value not in (None, False)
    }


def _combat_context(game) -> dict | None:
    from states.combat import CombatState

    state = game.current_state() if hasattr(game, "current_state") else None
    if not isinstance(state, CombatState):
        return None

    target = getattr(state, "opponent", None)
    enemies = []
    for enemy in getattr(state, "enemies", []) or []:
        if getattr(enemy, "hp", 0) <= 0:
            continue
        enemies.append(
            {
                "name": getattr(enemy, "name", "Unknown"),
                "hp": getattr(enemy, "hp", 0),
                "max_hp": getattr(enemy, "hp_max", 0),
                "ac": getattr(enemy, "armor_class", 10),
                "elite": bool(getattr(enemy, "elite", False)),
            }
        )

    effects = getattr(state, "effects", {}) or {}
    combat = {
        "round": getattr(state, "turn", 1),
        "target": getattr(target, "name", None),
        "enemies": enemies[:4],
        "allies": [
            {
                "name": getattr(ally, "name", "Unknown"),
                "hp": getattr(ally, "hp", 0),
                "stance": ally_stance(
                    game.player, getattr(ally, "name", "Unknown")
                ),
                "loyalty": ally_loyalty(
                    game.player, getattr(ally, "name", "Unknown")
                ),
            }
            for ally in (getattr(state, "allies", []) or [])
            if getattr(ally, "hp", 0) > 0
        ],
        "covering": bool(effects.get("cover")),
        "flanking": bool(
            getattr(state, "_flanking_bonus", lambda: 0)()
        ),
    }
    return combat


def build_context(game, memory=None) -> dict[str, Any]:
    """Builds the small, serializable snapshot sent to the narrator.

    Deliberately excludes inventory, full stats and map contents to keep each
    narration request small and cheap. ``memory`` is a short list of recent
    engine events used for continuity.
    """
    if game is None:
        return {}

    player = getattr(game, "player", None)
    if player is None:
        return {}

    from core.difficulty import difficulty_definition, player_difficulty

    difficulty_id = player_difficulty(player)
    difficulty = difficulty_definition(difficulty_id) or {}

    context: dict[str, Any] = {
        "player": {
            "name": getattr(player, "name", "Adventurer"),
            "class": getattr(player, "char_class", ""),
            "level": getattr(player, "level", 1),
            "cycle": getattr(player, "cycle", 1),
            "hp": getattr(player, "hp", 0),
            "hp_max": getattr(player, "hp_max", 0),
            "disguised": bool(getattr(player, "disguised", False)),
        },
        "difficulty": {
            "id": difficulty_id,
            "name": difficulty.get("name", difficulty_id.title()),
        },
    }

    current_map = getattr(player, "current_map", None)
    if current_map:
        context["map"] = current_map
        context["position"] = [getattr(player, "x", 0), getattr(player, "y", 0)]

    state = game.current_state() if hasattr(game, "current_state") else None
    if state is not None:
        context["state"] = type(state).__name__

    conditions = _condition_names(player)
    if conditions:
        context["conditions"] = conditions

    quests = _active_quests(player)
    if quests:
        context["quests"] = {
            "active": quests,
            "completed": len(
                getattr(player, "completed_quests", []) or []
            ),
        }

    allies = [
        {
            "name": name,
            "stance": ally_stance(player, name),
            "loyalty": ally_loyalty(player, name),
        }
        for name in (getattr(player, "allies", []) or [])
        if isinstance(name, str)
    ]
    if allies:
        context["party"] = allies

    factions = [
        {
            "id": entry["id"],
            "name": entry["name"],
            "value": entry["value"],
            "tier": entry["tier"],
            "tier_label": entry["tier_label"],
        }
        for entry in reputation_entries(player)
    ]
    if any(entry["value"] for entry in factions):
        context["factions"] = {
            "standing": factions,
            "shop_discount": shop_discount(player),
        }

    campaign = _campaign(player)
    if campaign:
        context["campaign"] = campaign

    best = int(getattr(player, "rune_trials_best", 0) or 0)
    runs = int(getattr(player, "rune_trials_runs", 0) or 0)
    if best or runs:
        context["rune_trials"] = {"best": best, "runs": runs}

    shards = int(getattr(player, "rune_shards", 0) or 0)
    if shards:
        context["rune_shards"] = shards

    combat = _combat_context(game)
    if combat:
        context["combat"] = combat

    position = (
        game.get_player_position()
        if hasattr(game, "get_player_position")
        else None
    )
    if isinstance(position, dict):
        nearby = {}
        if position.get("nearby_items"):
            nearby["items"] = _names(position["nearby_items"])
        if position.get("nearby_npcs"):
            nearby["npcs"] = _names(position["nearby_npcs"])
        if nearby:
            context["nearby"] = nearby

    recent = [entry for entry in (memory or []) if entry]
    if recent:
        context["recent"] = recent[-12:]

    return context
