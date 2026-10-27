"""Data-driven encounter groups built from monsters and NPCs."""

from __future__ import annotations

from util.data_manager import get_data_manager


def encounter_catalogue(location=None) -> dict:
    data = get_data_manager().load_data("monsters", "encounters.json")
    if not isinstance(data, dict):
        return {}
    if location is None:
        return data
    return {
        encounter_id: entry
        for encounter_id, entry in data.items()
        if isinstance(entry, dict)
        and entry.get("location", "tavern") == location
    }


def _build_enemy(spec):
    if not isinstance(spec, dict):
        return None

    from entities.enemy import Enemy
    from entities.npc import NPC

    if spec.get("monster_type"):
        enemy = Enemy(
            name=spec.get("name", ""),
            monster_type=spec["monster_type"],
        )
        if spec.get("name"):
            enemy.name = spec["name"]
        return enemy

    if spec.get("npc"):
        npc = NPC(spec["npc"])
        if spec.get("name"):
            npc.name = spec["name"]
        return npc

    return None


def build_encounter(encounter_id):
    """Returns an encounter dict with live enemies, or None if invalid."""
    data = encounter_catalogue().get(encounter_id)
    if not isinstance(data, dict):
        return None

    enemies = []
    for spec in data.get("enemies", []) or []:
        enemy = _build_enemy(spec)
        if enemy is not None:
            enemies.append(enemy)

    if not enemies:
        return None

    reward = data.get("reward", {})
    encounter = {
        "id": encounter_id,
        "title": data.get("title", encounter_id),
        "description": data.get("description", ""),
        "difficulty": data.get("difficulty", "medium"),
        "elite": any(
            bool(getattr(enemy, "elite", False)) for enemy in enemies
        ),
        "reward": dict(reward) if isinstance(reward, dict) else {},
        "enemies": enemies,
    }
    for key in (
        "location",
        "clears_area",
        "grants_flag",
        "loot",
        "source",
    ):
        if key in data:
            encounter[key] = data[key]
    return encounter
