"""Nessa's tiered Underroad black market."""

from __future__ import annotations

from core.factions import reputation_value
from core.item_catalogue import item_definition
from items.item import Item
from util.data_manager import get_data_manager

DEFAULT_ACCESS_REPUTATION = 5


def black_market_catalogue() -> dict:
    data = get_data_manager().load_data(
        "items", "black_market_stock.json"
    )
    return data if isinstance(data, dict) else {}


def _quiet_cargo_completed(player) -> bool:
    return any(
        isinstance(quest, dict) and quest.get("id") == "quiet_cargo"
        for quest in (getattr(player, "completed_quests", []) or [])
    )


def _reputation(player) -> int:
    return reputation_value(player, "underroad_smugglers")


def _tiers() -> dict:
    tiers = black_market_catalogue().get("tiers", {})
    return tiers if isinstance(tiers, dict) else {}


def _tier_for(player):
    reputation = _reputation(player)
    best_id = None
    best = None
    for tier_id, definition in _tiers().items():
        if not isinstance(definition, dict):
            continue
        minimum = int(definition.get("min", 0) or 0)
        if reputation < minimum:
            continue
        if best is None or minimum >= int(best.get("min", 0) or 0):
            best_id = tier_id
            best = definition
    return best_id, (best or {})


def black_market_unlocked(player) -> bool:
    """The cache opens only after The Quiet Cargo and positive standing."""
    if not _quiet_cargo_completed(player):
        return False
    access = int(
        black_market_catalogue().get(
            "access_reputation", DEFAULT_ACCESS_REPUTATION
        )
        or DEFAULT_ACCESS_REPUTATION
    )
    return _reputation(player) >= access


def _unique_flag(item_name) -> str:
    return "black_market:" + str(item_name or "").casefold()


def _is_purchased(player, item_name) -> bool:
    flag = _unique_flag(item_name)
    return flag in (getattr(player, "claimed_rewards", []) or [])


def _price(definition, tier_definition) -> int:
    value = max(1, int(definition.get("value", 0) or 0))
    discount = max(
        0, min(50, int(tier_definition.get("discount", 0) or 0))
    )
    return max(1, round(value * (100 - discount) / 100))


def black_market_entries(player) -> list[dict]:
    """Returns the stock with tier locks, prices and purchase state."""
    catalogue = black_market_catalogue()
    items = catalogue.get("items", [])
    if not isinstance(items, list):
        return []

    unlocked = black_market_unlocked(player)
    gold = int(getattr(player, "gold", 0) or 0)
    entries = []

    for spec in items:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name", "") or "")
        definition = item_definition(name)
        if definition is None:
            continue
        tier_id = str(spec.get("tier", "") or "")
        tier_definition = _tiers().get(tier_id, {})
        if not isinstance(tier_definition, dict):
            tier_definition = {}
        required = int(tier_definition.get("min", 0) or 0)
        available = unlocked and _reputation(player) >= required
        unique = bool(spec.get("unique", False))
        purchased = unique and _is_purchased(player, name)
        price = _price(definition, tier_definition)

        reasons = []
        if not unlocked:
            reasons.append("Complete The Quiet Cargo first")
        elif not available:
            reasons.append(
                f"Requires {tier_definition.get('label', tier_id)}"
            )
        if purchased:
            reasons.append("Already bought")
        if available and not purchased and gold < price:
            reasons.append(f"Need {price - gold} more gold")

        entries.append(
            {
                "name": definition.get("name", name),
                "type": definition.get("type", "misc"),
                "tier": tier_id,
                "tier_label": tier_definition.get("label", tier_id.title()),
                "required_reputation": required,
                "price": price,
                "base_price": int(definition.get("value", 0) or 0),
                "description": definition.get("description", ""),
                "effect": dict(definition.get("effect", {}) or {}),
                "unique": unique,
                "purchased": purchased,
                "available": available,
                "can_buy": available and not purchased and gold >= price,
                "reasons": reasons,
            }
        )
    return entries


def black_market_state(player) -> dict:
    tier_id, tier_definition = _tier_for(player)
    return {
        "unlocked": black_market_unlocked(player),
        "reputation": _reputation(player),
        "tier": tier_id,
        "tier_label": tier_definition.get("label", "No standing"),
        "discount": int(tier_definition.get("discount", 0) or 0),
        "gold": int(getattr(player, "gold", 0) or 0),
        "items": black_market_entries(player),
    }


def buy_black_market_item(player, item_name, game=None):
    """Buys one item from the cache if its tier and gold requirements hold."""
    wanted = str(item_name or "").strip().casefold()
    entry = next(
        (
            candidate
            for candidate in black_market_entries(player)
            if str(candidate.get("name", "")).casefold() == wanted
        ),
        None,
    )
    if entry is None:
        message = f"Nessa does not stock {item_name}."
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}

    if not entry["available"]:
        message = (
            f"{entry['name']} is not available at your current standing."
        )
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}
    if entry["purchased"]:
        message = f"{entry['name']} has already been sold."
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}

    price = int(entry["price"])
    gold = int(getattr(player, "gold", 0) or 0)
    if gold < price:
        message = (
            f"{entry['name']} costs {price} gold; you only have {gold}."
        )
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}

    definition = item_definition(entry["name"])
    if definition is None:
        message = f"Nessa cannot find {entry['name']} in her crates."
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}

    item = Item.from_dict(definition)
    player.gold = gold - price
    player.add_item(item)

    if entry["unique"]:
        claimed = getattr(player, "claimed_rewards", None)
        if not isinstance(claimed, list):
            claimed = []
            player.claimed_rewards = claimed
        flag = _unique_flag(entry["name"])
        if flag not in claimed:
            claimed.append(flag)

    message = f"You buy {item.name} from Nessa's cache for {price} gold."
    if game:
        game.io.show_message(message)
    return {
        "success": True,
        "message": message,
        "item": item.name,
        "price": price,
        "gold": player.gold,
    }
