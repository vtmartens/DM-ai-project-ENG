"""Market stock, purchases and sales for the equipment economy."""

from __future__ import annotations

from core.item_catalogue import item_catalogue
from items.item import Item
from util.data_manager import get_data_manager

SELLABLE_TYPES = {
    "weapon",
    "armor",
    "accessory",
    "heal",
    "light_heal",
    "grave_heal",
    "buff",
    "poison",
    "bomb",
}

_STAT_LABELS = {
    "strength": "STR",
    "dexterity": "DEX",
    "constitution": "CON",
    "intelligence": "INT",
    "wisdom": "WIS",
    "charisma": "CHA",
    "defense": "AC",
    "initiative": "Initiative",
}


def describe_properties(properties) -> str:
    """Returns a short summary of weapon metadata."""
    if not isinstance(properties, dict) or not properties:
        return ""
    parts = []
    if properties.get("ranged"):
        parts.append("ranged")
    if properties.get("finesse"):
        parts.append("finesse")
    attack_stat = properties.get("attack_stat")
    if attack_stat:
        parts.append(f"{str(attack_stat)[:3].upper()} attack")
    damage_bonus = int(properties.get("damage_bonus", 0) or 0)
    if damage_bonus:
        parts.append(f"{damage_bonus:+d} damage")
    return ", ".join(parts)


def describe_effect(effect) -> str:
    """Returns a short human-readable summary of an item effect."""
    if not isinstance(effect, dict) or not effect:
        return ""
    parts = []
    for key, value in effect.items():
        if key in ("heal", "light_heal", "grave_heal"):
            parts.append(f"restores {value} HP")
        elif key == "remove_poison":
            parts.append("cures poison")
        elif key == "damage":
            turns = effect.get("duration")
            parts.append(
                f"poison {value} damage"
                + (f" for {turns} turns" if turns else "")
            )
        elif key == "duration":
            continue
        elif key == "escape":
            parts.append("escape aid")
        elif key in _STAT_LABELS:
            parts.append(f"{_STAT_LABELS[key]} {int(value):+d}")
        else:
            parts.append(f"{key} {value}")
    return ", ".join(parts)


def _fallback_stock(catalogue: dict[str, dict]) -> list[dict]:
    category_for_type = {
        "weapon": "Weapons",
        "armor": "Armor",
        "accessory": "Accessories",
    }
    stock = []
    for entry in catalogue.values():
        if entry.get("rarity", "common") != "common":
            continue
        item_type = entry.get("type")
        category = category_for_type.get(item_type, "Potions")
        stock.append({"category": category, "definition": entry})
    return stock


def _stock_definitions() -> list[dict]:
    catalogue = item_catalogue()
    config = get_data_manager().load_data("items", "shop_stock.json")
    if not isinstance(config, dict) or not config:
        return _fallback_stock(catalogue)

    stock = []
    for category, names in config.items():
        if not isinstance(names, list):
            continue
        for name in names:
            entry = catalogue.get(str(name).casefold())
            if entry is not None:
                stock.append({"category": str(category), "definition": entry})
    return stock or _fallback_stock(catalogue)


def _price(definition: dict, sale=False) -> int:
    value = max(1, int(definition.get("value", 0) or 0))
    return max(1, value // 2) if sale else value


def item_summary(definition: dict, category: str, sale=False) -> dict:
    return {
        "name": definition.get("name", "Unknown item"),
        "type": definition.get("type", "misc"),
        "category": category,
        "price": _price(definition, sale=sale),
        "sell_price": _price(definition, sale=True),
        "description": definition.get("description", ""),
        "effect": dict(definition.get("effect", {}) or {}),
        "effect_text": describe_effect(definition.get("effect", {})),
        "properties": dict(definition.get("properties", {}) or {}),
        "properties_text": describe_properties(
            definition.get("properties", {})
        ),
        "rarity": definition.get("rarity", "common"),
    }


def shop_stock() -> list[dict]:
    """Returns the purchasable stock with prices and effect details."""
    return [
        item_summary(entry["definition"], entry["category"])
        for entry in _stock_definitions()
    ]


def _stock_entry(item_name: str) -> dict | None:
    wanted = str(item_name or "").strip().casefold()
    if not wanted:
        return None

    stock = _stock_definitions()
    for entry in stock:
        definition = entry["definition"]
        if str(definition.get("name", "")).casefold() == wanted:
            return entry

    matches = [
        entry
        for entry in stock
        if wanted in str(entry["definition"].get("name", "")).casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _equipped_items(player) -> list:
    equipped = [getattr(player, "armor", None)]
    if getattr(player, "weapon", None):
        equipped.append(player.weapon)
    equipped.extend(getattr(player, "accessories", []) or [])
    return [item for item in equipped if item is not None]


def _is_sellable(item) -> bool:
    return isinstance(item, Item) and item.type in SELLABLE_TYPES


def sellable_items(player) -> list[dict]:
    """Returns non-equipped inventory items with their sale prices."""
    equipped = _equipped_items(player)
    result = []
    for item in getattr(player, "inventory", []) or []:
        if not _is_sellable(item):
            continue
        if any(item is equipped_item for equipped_item in equipped):
            continue
        result.append(
            {
                "name": item.name,
                "type": item.type,
                "category": "Inventory",
                "price": max(1, int(getattr(item, "value", 0) or 0) // 2),
                "description": getattr(item, "description", ""),
                "effect": dict(getattr(item, "effect", {}) or {}),
                "effect_text": describe_effect(
                    getattr(item, "effect", {})
                ),
                "properties": dict(
                    getattr(item, "properties", {}) or {}
                ),
                "properties_text": describe_properties(
                    getattr(item, "properties", {})
                ),
                "rarity": getattr(item, "rarity", "common"),
                "equipped": False,
            }
        )
    return result


def buy_item(player, item_name, game=None) -> dict:
    """Buys one stock item and returns a JSON-safe result."""
    entry = _stock_entry(item_name)
    if entry is None:
        message = f"The shop does not stock {item_name}."
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message, "gold": player.gold}

    definition = entry["definition"]
    price = _price(definition)
    name = definition.get("name", item_name)
    if int(getattr(player, "gold", 0) or 0) < price:
        message = (
            f"You need {price} gold for {name}, but you only have "
            f"{player.gold}."
        )
        if game:
            game.io.show_message(message)
        return {
            "success": False,
            "message": message,
            "gold": player.gold,
        }

    player.gold -= price
    item = Item.from_dict(definition)
    player.add_item(item)
    from core.achievements import record_event

    record_event(player, "item_bought", game=game, item_type=item.type)
    message = f"You buy {name} for {price} gold."
    if game:
        game.io.show_message(message)
    return {
        "success": True,
        "message": message,
        "item": item_summary(definition, entry["category"]),
        "price": price,
        "gold": player.gold,
    }


def sell_item(player, item_name, game=None) -> dict:
    """Sells a non-equipped inventory item for half its value."""
    wanted = str(item_name or "").strip().casefold()
    if not wanted:
        message = "Choose an item to sell."
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message, "gold": player.gold}

    equipped = _equipped_items(player)
    match = None
    for item in getattr(player, "inventory", []) or []:
        if not _is_sellable(item):
            continue
        if str(item.name).casefold() != wanted:
            continue
        if any(item is equipped_item for equipped_item in equipped):
            continue
        match = item
        break

    if match is None:
        equipped_match = next(
            (
                item
                for item in equipped
                if str(getattr(item, "name", "")).casefold() == wanted
            ),
            None,
        )
        message = (
            f"Unequip {equipped_match.name} before selling it."
            if equipped_match is not None
            else f"You have no {item_name} to sell."
        )
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message, "gold": player.gold}

    sale_price = max(1, int(getattr(match, "value", 0) or 0) // 2)
    player.inventory.remove(match)
    player.gold += sale_price
    from core.achievements import record_event

    record_event(player, "gold_changed", game=game)
    message = f"You sell {match.name} for {sale_price} gold."
    if game:
        game.io.show_message(message)
    return {
        "success": True,
        "message": message,
        "item": {
            "name": match.name,
            "type": match.type,
            "category": "Inventory",
            "price": sale_price,
            "description": getattr(match, "description", ""),
            "effect": dict(getattr(match, "effect", {}) or {}),
            "effect_text": describe_effect(getattr(match, "effect", {})),
            "properties": dict(getattr(match, "properties", {}) or {}),
            "properties_text": describe_properties(
                getattr(match, "properties", {})
            ),
            "rarity": getattr(match, "rarity", "common"),
        },
        "price": sale_price,
        "gold": player.gold,
    }
