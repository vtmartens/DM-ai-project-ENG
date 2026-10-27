"""Faction standing, shop discounts and dialogue/reward thresholds."""

from __future__ import annotations

from util.data_manager import get_data_manager


def faction_catalogue() -> dict:
    data = get_data_manager().load_data("factions", "factions.json")
    return data if isinstance(data, dict) else {}


def faction_definition(faction_id) -> dict | None:
    definition = faction_catalogue().get(str(faction_id or ""))
    return definition if isinstance(definition, dict) else None


def reputation_value(player, faction_id) -> int:
    reputation = getattr(player, "reputation", None)
    if not isinstance(reputation, dict):
        return 0
    try:
        return int(reputation.get(str(faction_id or ""), 0) or 0)
    except (TypeError, ValueError):
        return 0


def reputation_tier(value) -> str:
    value = int(value or 0)
    if value <= -10:
        return "hostile"
    if value < 10:
        return "neutral"
    if value < 25:
        return "friendly"
    if value < 40:
        return "trusted"
    return "allied"


def tier_label(tier) -> str:
    return {
        "hostile": "Hostile",
        "neutral": "Neutral",
        "friendly": "Friendly",
        "trusted": "Trusted",
        "allied": "Allied",
    }.get(str(tier or ""), "Neutral")


def adjust_reputation(player, faction_id, amount, game=None, reason=None):
    """Adds (or subtracts) standing and returns the new value."""
    definition = faction_definition(faction_id)
    if definition is None:
        return reputation_value(player, faction_id)

    try:
        amount = int(amount or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount == 0:
        return reputation_value(player, faction_id)

    reputation = getattr(player, "reputation", None)
    if not isinstance(reputation, dict):
        reputation = {}
        player.reputation = reputation
    key = str(faction_id)
    current = reputation_value(player, key)
    updated = max(-100, min(100, current + amount))
    reputation[key] = updated

    if game:
        name = definition.get("name", key)
        if amount > 0:
            game.io.show_message(
                f"Your standing with {name} improves (+{amount})."
            )
        else:
            game.io.show_message(
                f"Your standing with {name} worsens ({amount})."
            )
        if reason:
            game.io.show_message(reason)
    return updated


def faction_bonus_percent(player, faction_id, table="quest_bonus") -> int:
    """Returns the standing-tier bonus from a faction's data table."""
    definition = faction_definition(faction_id)
    if definition is None:
        return 0
    bonuses = definition.get(table, {})
    if not isinstance(bonuses, dict):
        return 0
    tier = reputation_tier(reputation_value(player, faction_id))
    try:
        return max(0, int(bonuses.get(tier, 0) or 0))
    except (TypeError, ValueError):
        return 0


def shop_discount(player, faction_id="mirt_network") -> int:
    return faction_bonus_percent(player, faction_id, table="shop_discount")


def reputation_entries(player) -> list[dict]:
    entries = []
    for faction_id, definition in faction_catalogue().items():
        if not isinstance(definition, dict):
            continue
        value = reputation_value(player, faction_id)
        tier = reputation_tier(value)
        entries.append(
            {
                "id": faction_id,
                "name": definition.get("name", faction_id),
                "description": definition.get("description", ""),
                "value": value,
                "tier": tier,
                "tier_label": tier_label(tier),
            }
        )
    return entries
