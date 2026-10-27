"""New Cycle difficulty and reward scaling."""

from __future__ import annotations

from util.data_manager import get_data_manager


def cycle_config() -> dict:
    data = get_data_manager().load_data("cycles", "cycles.json")
    return data if isinstance(data, dict) else {}


def cycle_number(player) -> int:
    try:
        return max(1, int(getattr(player, "cycle", 1) or 1))
    except (TypeError, ValueError):
        return 1


def enemy_scaling(cycle) -> dict:
    """Returns the cumulative enemy scaling for a cycle number."""
    extra = max(0, int(cycle or 1) - 1)
    config = cycle_config()
    return {
        "hp_percent": max(
            0, int(config.get("enemy_hp_percent_per_cycle", 0) or 0)
        )
        * extra,
        "damage_bonus": max(
            0, int(config.get("enemy_damage_bonus_per_cycle", 0) or 0)
        )
        * extra,
        "ac_bonus": max(
            0, int(config.get("enemy_ac_bonus_per_cycle", 0) or 0)
        )
        * extra,
    }


def reward_multiplier(cycle) -> float:
    extra = max(0, int(cycle or 1) - 1)
    percent = max(
        0, int(cycle_config().get("reward_percent_per_cycle", 0) or 0)
    )
    return 1 + (percent * extra / 100)
