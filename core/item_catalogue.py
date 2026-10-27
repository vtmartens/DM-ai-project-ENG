"""Shared lookup for item definitions across shops and loot tables."""

from __future__ import annotations

from util.data_manager import get_data_manager

CATALOGUE_FILES = (
    "weapons.json",
    "armor.json",
    "accessories.json",
    "potions.json",
)


def item_catalogue() -> dict[str, dict]:
    """Returns item definitions keyed by casefolded name."""
    manager = get_data_manager()
    items = {}
    for file_name in CATALOGUE_FILES:
        entries = manager.load_data("items", file_name)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            items[str(entry["name"]).casefold()] = entry
    return items


def item_definition(name):
    """Returns one item definition by name, or None."""
    return item_catalogue().get(str(name or "").casefold())
