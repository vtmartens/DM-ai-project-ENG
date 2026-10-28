"""Data-driven Cycle Omens that alter each New Cycle run."""

from __future__ import annotations

from util.data_manager import get_data_manager


def omen_catalogue() -> dict:
    data = get_data_manager().load_data("cycles", "omens.json")
    return data if isinstance(data, dict) else {}


def omen_definition(omen_id) -> dict | None:
    key = str(omen_id or "").strip().casefold()
    definition = omen_catalogue().get(key)
    return definition if isinstance(definition, dict) else None


def player_omen_id(player) -> str | None:
    key = str(getattr(player, "cycle_omen", "") or "").strip().casefold()
    return key if omen_definition(key) is not None else None


def player_omen(player) -> dict | None:
    key = player_omen_id(player)
    if key is None:
        return None
    definition = omen_definition(key) or {}
    return {
        "id": key,
        "name": definition.get("name", key.title()),
        "description": definition.get("description", ""),
    }


def omen_entries() -> list[dict]:
    entries = []
    for omen_id, definition in omen_catalogue().items():
        if not isinstance(definition, dict):
            continue
        entries.append(
            {
                "id": omen_id,
                "name": definition.get("name", omen_id.title()),
                "description": definition.get("description", ""),
            }
        )
    return entries


def _definition(player) -> dict:
    key = player_omen_id(player)
    if key is None:
        return {}
    return omen_definition(key) or {}


def enemy_scaling(player) -> dict:
    enemy = _definition(player).get("enemy", {})
    if not isinstance(enemy, dict):
        enemy = {}
    return {
        "hp_percent": int(enemy.get("hp_percent", 0) or 0),
        "damage_bonus": int(enemy.get("damage_bonus", 0) or 0),
        "ac_bonus": int(enemy.get("ac_bonus", 0) or 0),
    }


def reward_multiplier(player) -> float:
    definition = _definition(player)
    return max(
        0.0, 1 + int(definition.get("reward_percent", 0) or 0) / 100
    )


def rune_shard_multiplier(player) -> float:
    definition = _definition(player)
    return max(
        0.0,
        1 + int(definition.get("rune_shards_percent", 0) or 0) / 100,
    )


def rest_cost_bonus(player) -> int:
    return max(0, int(_definition(player).get("rest_cost_bonus", 0) or 0))


def market_discount_bonus(player) -> int:
    return max(
        0, int(_definition(player).get("market_discount_bonus", 0) or 0)
    )


def black_market_discount_bonus(player) -> int:
    return max(
        0,
        int(
            _definition(player).get("black_market_discount_bonus", 0)
            or 0
        ),
    )
