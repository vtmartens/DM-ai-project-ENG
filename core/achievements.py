"""Achievement tracking and evaluation.

The engine records gameplay events on the player and evaluates the catalogue in
``data/achievements/achievements.json`` after each one. Every condition type the
catalogue uses is implemented here; unknown types simply stay locked, so adding a
new condition type to the data cannot break gameplay.
"""

from __future__ import annotations

import time

from util.data_manager import get_data_manager

# Condition types understood by ``condition_met``. Kept as a module constant so
# the data-integrity tests can assert the catalogue never drifts ahead of it.
SUPPORTED_CONDITIONS = frozenset(
    {
        "movement",
        "combat_victory",
        "unique_items_collected",
        "areas_visited",
        "equip_item",
        "coins",
        "combat_without_damage",
        "quest_without_combat",
        "bounty_claimed",
        "road_victory",
        "equipment_bought",
        "area_cleared",
        "defeats",
        "defeat_enemy",
        "rune_trials_best",
        "rune_trials_runs",
        "level",
        "cycle",
    }
)

DEFAULT_ACHIEVEMENT_STATS = {
    "movement": 0,
    "combat_victory": 0,
    "unique_items_collected": [],
    "areas_visited": [],
    "combat_without_damage": 0,
    "quests_without_combat": 0,
    "bounties_claimed": 0,
    "road_victories": 0,
    "items_bought": 0,
    "equipment_bought": 0,
    "enemies_defeated": [],
}


def _is_player(entity) -> bool:
    """True for the Player (NPCs inherit add_item/add_gold but are not tracked)."""
    return hasattr(entity, "char_class")


def ensure_achievement_state(entity):
    """Adds achievement attributes to players created before this feature."""
    if not _is_player(entity):
        return False
    if not isinstance(getattr(entity, "achievements", None), list):
        entity.achievements = []
    if not isinstance(getattr(entity, "achievement_timestamps", None), dict):
        entity.achievement_timestamps = {}
    if not isinstance(getattr(entity, "achievement_stats", None), dict):
        entity.achievement_stats = coerce_stats(None)
    else:
        entity.achievement_stats = coerce_stats(entity.achievement_stats)
    return True


def coerce_stats(raw) -> dict:
    """Returns a complete, safe stats dict from saved or partial data."""
    raw = raw if isinstance(raw, dict) else {}
    stats = {}
    for key, default in DEFAULT_ACHIEVEMENT_STATS.items():
        value = raw.get(key, default)
        if isinstance(default, list):
            stats[key] = [
                item for item in (value or []) if isinstance(item, str)
            ]
        else:
            try:
                stats[key] = int(value or 0)
            except (TypeError, ValueError):
                stats[key] = 0
    return stats


def achievement_definitions():
    """Returns the catalogue as a list, or an empty list for malformed data."""
    definitions = get_data_manager().get_achievements()
    return definitions if isinstance(definitions, list) else []


def _as_int(value, default=1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize(value) -> str:
    return (
        str(value or "")
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .casefold()
    )


def _all_map_names(game) -> set:
    maps = getattr(getattr(game, "map_manager", None), "maps", None)
    return set(maps) if isinstance(maps, dict) else set()


def _visited_areas(player):
    stats = player.achievement_stats
    visited = set(stats.get("areas_visited", []))
    current = getattr(player, "current_map", None)
    if current:
        visited.add(current)
    return visited


def condition_met(player, condition, game=None) -> bool:
    """Evaluates one catalogue condition against the player's tracked state."""
    if not ensure_achievement_state(player):
        return False

    condition = condition if isinstance(condition, dict) else {}
    condition_type = condition.get("type")
    value = condition.get("value")
    stats = player.achievement_stats

    if condition_type == "movement":
        return stats["movement"] >= _as_int(value, 1)

    if condition_type == "combat_victory":
        return stats["combat_victory"] >= _as_int(value, 1)

    if condition_type == "unique_items_collected":
        return len(set(stats["unique_items_collected"])) >= _as_int(value, 1)

    if condition_type == "areas_visited":
        visited = _visited_areas(player)
        if value == "all":
            required = _all_map_names(game)
            return bool(required) and required <= visited
        return len(visited) >= _as_int(value, 1)

    if condition_type == "equip_item":
        weapon = getattr(player, "weapon", None)
        if weapon is None:
            return False
        category = condition.get("category")
        if category and getattr(weapon, "type", None) != category:
            return False
        rarity = condition.get("rarity")
        return not rarity or getattr(weapon, "rarity", "common") == rarity

    if condition_type == "coins":
        return int(getattr(player, "gold", 0) or 0) >= _as_int(value, 0)

    if condition_type == "combat_without_damage":
        return stats["combat_without_damage"] >= _as_int(value, 1)

    if condition_type == "quest_without_combat":
        return stats["quests_without_combat"] >= _as_int(value, 1)

    if condition_type == "bounty_claimed":
        return stats["bounties_claimed"] >= _as_int(value, 1)

    if condition_type == "road_victory":
        return stats["road_victories"] >= _as_int(value, 1)

    if condition_type == "equipment_bought":
        return stats["equipment_bought"] >= _as_int(value, 1)

    if condition_type == "area_cleared":
        cleared = {
            _normalize(area)
            for area in getattr(player, "cleared_areas", []) or []
            if isinstance(area, str)
        }
        return _normalize(value) in cleared

    if condition_type == "defeats":
        return int(getattr(player, "defeats", 0) or 0) >= _as_int(value, 1)

    if condition_type == "defeat_enemy":
        defeated = {
            _normalize(name)
            for name in stats["enemies_defeated"]
        }
        return _normalize(value) in defeated

    if condition_type == "rune_trials_best":
        return int(getattr(player, "rune_trials_best", 0) or 0) >= _as_int(
            value, 1
        )

    if condition_type == "rune_trials_runs":
        return int(getattr(player, "rune_trials_runs", 0) or 0) >= _as_int(
            value, 1
        )

    if condition_type == "level":
        return int(getattr(player, "level", 1) or 1) >= _as_int(value, 1)

    if condition_type == "cycle":
        return int(getattr(player, "cycle", 1) or 1) >= _as_int(value, 1)

    return False


def evaluate(player, game=None) -> list:
    """Unlocks every satisfied achievement and returns the new ids."""
    if not ensure_achievement_state(player):
        return []

    game = game if game is not None else getattr(player, "game", None)
    unlocked = []
    for achievement in achievement_definitions():
        if not isinstance(achievement, dict):
            continue
        achievement_id = achievement.get("id")
        if not achievement_id or achievement_id in player.achievements:
            continue
        if not condition_met(player, achievement.get("condition", {}), game):
            continue

        player.achievements.append(achievement_id)
        player.achievement_timestamps[achievement_id] = time.time()
        unlocked.append(achievement_id)

        if game and getattr(game, "io", None):
            name = achievement.get("name", achievement_id)
            game.io.show_message(f"\nAchievement unlocked: {name}!")

    return unlocked


def check_achievements(player, game=None) -> list:
    """Re-evaluates the catalogue without recording an event."""
    return evaluate(player, game)


def record_event(entity, event, game=None, **details) -> list:
    """Records one gameplay event and evaluates achievements.

    Unknown events still trigger evaluation (so e.g. a gold change can unlock
    the coins achievement), which keeps call sites free of catalogue knowledge.
    """
    if not ensure_achievement_state(entity):
        return []

    game = game if game is not None else getattr(entity, "game", None)
    stats = entity.achievement_stats

    if event == "movement":
        stats["movement"] += _as_int(details.get("amount"), 1)
    elif event == "combat_victory":
        stats["combat_victory"] += 1
        if details.get("clean"):
            stats["combat_without_damage"] += 1
        else:
            stats["combat_without_damage"] = 0
    elif event == "combat_defeat":
        stats["combat_without_damage"] = 0
    elif event == "item_collected":
        name = details.get("item")
        if isinstance(name, str) and name and name not in stats["unique_items_collected"]:
            stats["unique_items_collected"].append(name)
    elif event == "area_visited":
        map_name = details.get("map")
        if isinstance(map_name, str) and map_name and map_name not in stats["areas_visited"]:
            stats["areas_visited"].append(map_name)
    elif event == "quest_completed":
        if _as_int(details.get("combat_encounters"), 0) == 0:
            stats["quests_without_combat"] += 1
    elif event == "bounty_claimed":
        stats["bounties_claimed"] += 1
    elif event == "road_victory":
        stats["road_victories"] += 1
    elif event == "item_bought":
        stats["items_bought"] += 1
        if details.get("item_type") in {"weapon", "armor", "accessory"}:
            stats["equipment_bought"] += 1
    elif event == "enemy_defeated":
        name = details.get("enemy")
        if isinstance(name, str) and name and name not in stats["enemies_defeated"]:
            stats["enemies_defeated"].append(name)

    return evaluate(entity, game)
