"""Data-driven abilities used by hostile enemies and NPCs.

Definitions live in ``data/monsters/abilities.json``; monsters and NPCs only
reference them by id in their ``abilities`` lists. Combat tracks cooldowns per
enemy and picks the first useful off-cooldown ability, falling back to a basic
attack.
"""

from __future__ import annotations

from util.data_manager import get_data_manager


def ability_catalogue() -> dict:
    data = get_data_manager().load_data("monsters", "abilities.json")
    return data if isinstance(data, dict) else {}


def load_abilities(ability_ids) -> list[dict]:
    """Returns the definitions for the given ids, preserving order."""
    catalogue = ability_catalogue()
    definitions = []
    for ability_id in ability_ids or []:
        data = catalogue.get(ability_id)
        if not isinstance(data, dict):
            continue
        definition = dict(data)
        definition.setdefault("id", ability_id)
        definitions.append(definition)
    return definitions


def choose_ability(abilities, cooldowns, enemy):
    """Returns the first off-cooldown ability that is useful, or None."""
    for ability in abilities or []:
        if not isinstance(ability, dict):
            continue
        ability_id = ability.get("id")
        if not ability_id:
            continue
        if int((cooldowns or {}).get(ability_id, 0) or 0) > 0:
            continue

        effect = ability.get("effect", {})
        if (
            effect.get("type") == "heal"
            and getattr(enemy, "hp", 0) >= getattr(enemy, "hp_max", 0)
        ):
            continue
        return ability
    return None
