"""Data-driven Story / Standard / Hard difficulty modifiers."""

from __future__ import annotations

from util.data_manager import get_data_manager

DEFAULT_DIFFICULTY = "standard"


def difficulty_catalogue() -> dict:
    data = get_data_manager().load_data(
        "difficulty", "difficulty.json"
    )
    return data if isinstance(data, dict) else {}


def difficulty_definition(difficulty_id) -> dict | None:
    key = str(difficulty_id or "").strip().casefold()
    definition = difficulty_catalogue().get(key)
    return definition if isinstance(definition, dict) else None


def player_difficulty(player) -> str:
    """Returns the player's difficulty id, falling back to Standard."""
    key = str(getattr(player, "difficulty", DEFAULT_DIFFICULTY) or "").casefold()
    return key if difficulty_definition(key) is not None else DEFAULT_DIFFICULTY


def difficulty_entries() -> list[dict]:
    entries = []
    for difficulty_id, definition in difficulty_catalogue().items():
        if not isinstance(definition, dict):
            continue
        entries.append(
            {
                "id": difficulty_id,
                "name": definition.get("name", difficulty_id.title()),
                "description": definition.get("description", ""),
                "enemy": dict(definition.get("enemy", {}) or {}),
                "reward_percent": int(
                    definition.get("reward_percent", 100) or 100
                ),
                "rest_cost": int(definition.get("rest_cost", 10) or 10),
                "defeat_gold_loss": int(
                    definition.get("defeat_gold_loss", 20) or 20
                ),
                "default": difficulty_id == DEFAULT_DIFFICULTY,
            }
        )
    return entries


def enemy_scaling(player) -> dict:
    definition = difficulty_definition(player_difficulty(player)) or {}
    enemy = definition.get("enemy", {})
    if not isinstance(enemy, dict):
        enemy = {}
    return {
        "hp_percent": int(enemy.get("hp_percent", 0) or 0),
        "damage_bonus": int(enemy.get("damage_bonus", 0) or 0),
        "ac_bonus": int(enemy.get("ac_bonus", 0) or 0),
    }


def reward_multiplier(player) -> float:
    definition = difficulty_definition(player_difficulty(player)) or {}
    percent = int(definition.get("reward_percent", 100) or 100)
    return max(0.0, percent / 100)


def rest_cost(player, default=10) -> int:
    definition = difficulty_definition(player_difficulty(player)) or {}
    return max(0, int(definition.get("rest_cost", default) or default))


def defeat_gold_loss(player, default=20) -> int:
    definition = difficulty_definition(player_difficulty(player)) or {}
    return max(
        0, int(definition.get("defeat_gold_loss", default) or default)
    )
