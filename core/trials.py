"""Data-driven waves and boons for the post-campaign Rune Trials."""

from __future__ import annotations

from util.data_manager import get_data_manager


def trial_catalogue() -> dict:
    data = get_data_manager().load_data("trials", "rune_trials.json")
    return data if isinstance(data, dict) else {}


def max_waves() -> int:
    try:
        return max(1, int(trial_catalogue().get("max_waves", 1) or 1))
    except (TypeError, ValueError):
        return 1


def completion_reward() -> dict:
    reward = trial_catalogue().get("completion_reward", {})
    return dict(reward) if isinstance(reward, dict) else {}


def wave_definitions() -> list[dict]:
    waves = trial_catalogue().get("waves", [])
    if not isinstance(waves, list):
        return []
    return [dict(wave) for wave in waves if isinstance(wave, dict)]


def wave_definition(number) -> dict | None:
    try:
        index = int(number) - 1
    except (TypeError, ValueError):
        return None
    waves = wave_definitions()
    if not 0 <= index < len(waves):
        return None
    return waves[index]


def modifier_definition(modifier_id) -> dict | None:
    modifiers = trial_catalogue().get("modifiers", {})
    if not isinstance(modifiers, dict):
        return None
    modifier = modifiers.get(str(modifier_id or ""))
    return dict(modifier) if isinstance(modifier, dict) else None


def boon_definitions() -> list[dict]:
    boons = trial_catalogue().get("boons", [])
    if not isinstance(boons, list):
        return []
    return [dict(boon) for boon in boons if isinstance(boon, dict)]


def get_boon(boon_id) -> dict | None:
    wanted = str(boon_id or "").casefold()
    for boon in boon_definitions():
        if str(boon.get("id", "")).casefold() == wanted:
            return boon
        if str(boon.get("name", "")).casefold() == wanted:
            return boon
    return None


def _build_enemy(spec):
    if not isinstance(spec, dict) or not spec.get("monster_type"):
        return None
    from entities.enemy import Enemy

    enemy = Enemy(
        name=spec.get("name", ""),
        monster_type=spec["monster_type"],
    )
    if spec.get("name"):
        enemy.name = spec["name"]
    return enemy


def _apply_modifier(enemy, modifier):
    if not isinstance(modifier, dict):
        return
    hp_percent = int(modifier.get("enemy_hp_percent", 0) or 0)
    if hp_percent:
        bonus = max(1, int(round(enemy.hp_max * hp_percent / 100)))
        enemy.hp_max += bonus
        enemy.hp = min(enemy.hp_max, enemy.hp + bonus)

    damage_bonus = int(modifier.get("enemy_damage_bonus", 0) or 0)
    if damage_bonus:
        enemy.damage_bonus = int(
            getattr(enemy, "damage_bonus", 0) or 0
        ) + damage_bonus

    ac_bonus = int(modifier.get("enemy_ac_bonus", 0) or 0)
    if ac_bonus:
        enemy.armor_class_value = int(enemy.armor_class) + ac_bonus


def build_trial_wave(number):
    """Builds one live wave encounter, including its modifier."""
    wave = wave_definition(number)
    if wave is None:
        return None

    modifier = modifier_definition(wave.get("modifier"))
    enemies = []
    for spec in wave.get("enemies", []) or []:
        enemy = _build_enemy(spec)
        if enemy is None:
            continue
        _apply_modifier(enemy, modifier)
        enemies.append(enemy)

    if not enemies:
        return None

    reward = wave.get("reward", {})
    return {
        "id": f"rune_trial_{int(number)}",
        "title": wave.get("title", f"Rune Trial {number}"),
        "description": wave.get("description", ""),
        "difficulty": "hard",
        "reward": dict(reward) if isinstance(reward, dict) else {},
        "enemies": enemies,
        "source": "rune_trials",
        "wave": int(number),
        "rune_shards": max(0, int(wave.get("rune_shards", 0) or 0)),
        "modifier": modifier,
    }


def apply_boon(player, boon, game=None):
    """Applies one between-wave boon and returns a short result message."""
    if not isinstance(boon, dict):
        return None
    effect = boon.get("effect", {})
    if not isinstance(effect, dict):
        return None

    kind = effect.get("type")
    if kind == "heal":
        amount = max(0, int(effect.get("amount", 0) or 0))
        before = int(getattr(player, "hp", 0) or 0)
        hp_max = int(getattr(player, "hp_max", before) or before)
        player.hp = min(hp_max, before + amount)
        message = f"{boon.get('name', 'Boon')}: recovered {player.hp - before} HP."
    elif kind == "mana":
        amount = max(0, int(effect.get("amount", 0) or 0))
        before = int(getattr(player, "mana", 0) or 0)
        mana_max = int(getattr(player, "mana_max", before) or before)
        player.mana = min(mana_max, before + amount)
        message = (
            f"{boon.get('name', 'Boon')}: recovered "
            f"{player.mana - before} mana."
        )
    elif kind == "clear_conditions":
        conditions = getattr(player, "conditions", None)
        if isinstance(conditions, dict):
            conditions.clear()
        message = f"{boon.get('name', 'Boon')}: conditions cleared."
    else:
        return None

    if game:
        game.io.show_message(message)
    return message
