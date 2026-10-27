"""Data-driven loot rolls for defeated enemies."""

from __future__ import annotations

import random

from core.item_catalogue import item_definition
from items.item import Item
from util.data_manager import get_data_manager


def loot_tables() -> dict:
    data = get_data_manager().load_data("monsters", "loot_tables.json")
    return data if isinstance(data, dict) else {}


def roll_loot(enemy, dice=None) -> list[Item]:
    """Returns the items dropped by an enemy, or an empty list."""
    monster_type = getattr(enemy, "monster_type", None)
    if not monster_type:
        return []

    table = loot_tables().get(monster_type, [])
    if not isinstance(table, list):
        return []

    drops = []
    for entry in table:
        if not isinstance(entry, dict):
            continue
        item_name = entry.get("item")
        try:
            chance = int(entry.get("chance", 0) or 0)
        except (TypeError, ValueError):
            continue
        if not item_name or chance <= 0:
            continue

        roll = dice.roll() if dice is not None else random.randint(1, 100)
        if roll > chance:
            continue

        definition = item_definition(item_name)
        if definition is not None:
            drops.append(Item.from_dict(definition))

    return drops
