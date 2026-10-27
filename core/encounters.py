"""Data-driven encounter groups built from monsters and NPCs."""

from __future__ import annotations

from util.data_manager import get_data_manager


def encounter_catalogue() -> dict:
    data = get_data_manager().load_data("monsters", "encounters.json")
    return data if isinstance(data, dict) else {}


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
    return {
        "id": encounter_id,
        "title": data.get("title", encounter_id),
        "description": data.get("description", ""),
        "difficulty": data.get("difficulty", "medium"),
        "reward": dict(reward) if isinstance(reward, dict) else {},
        "enemies": enemies,
    }
