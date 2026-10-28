"""Rune-shard recipes and the Sanctum Forge."""

from __future__ import annotations

from core.item_catalogue import item_definition
from items.item import Item
from util.data_manager import get_data_manager


def recipe_catalogue() -> dict:
    data = get_data_manager().load_data("crafting", "recipes.json")
    return data if isinstance(data, dict) else {}


def recipes() -> list[dict]:
    return [
        dict(recipe)
        for recipe in recipe_catalogue().values()
        if isinstance(recipe, dict) and recipe.get("id")
    ]


def get_recipe(recipe_id) -> dict | None:
    wanted = str(recipe_id or "").casefold()
    for recipe in recipes():
        if str(recipe.get("id", "")).casefold() == wanted:
            return recipe
        if str(recipe.get("name", "")).casefold() == wanted:
            return recipe
    return None


def rune_shards(player) -> int:
    try:
        return max(0, int(getattr(player, "rune_shards", 0) or 0))
    except (TypeError, ValueError):
        return 0


def add_rune_shards(player, amount, game=None):
    amount = max(0, int(amount or 0))
    if amount:
        from core.omens import rune_shard_multiplier

        amount = max(
            1, int(round(amount * rune_shard_multiplier(player)))
        )
    player.rune_shards = rune_shards(player) + amount
    if game and amount:
        game.io.show_message(
            f"You gain {amount} Rune Shard{'s' if amount != 1 else ''}."
        )
    return player.rune_shards


def _crafted_flag(recipe_id) -> str:
    return f"crafted:{recipe_id}"


def _is_crafted(player, recipe_id) -> bool:
    return _crafted_flag(recipe_id) in (
        getattr(player, "claimed_rewards", []) or []
    )


def recipe_entries(player) -> list[dict]:
    entries = []
    shards = rune_shards(player)
    gold = int(getattr(player, "gold", 0) or 0)
    for recipe in recipes():
        recipe_id = str(recipe["id"])
        shard_cost = max(0, int(recipe.get("shards", 0) or 0))
        gold_cost = max(0, int(recipe.get("gold", 0) or 0))
        crafted = _is_crafted(player, recipe_id)
        reasons = []
        if crafted and recipe.get("unique"):
            reasons.append("Already forged")
        if shards < shard_cost:
            reasons.append(
                f"Need {shard_cost - shards} more Rune Shards"
            )
        if gold < gold_cost:
            reasons.append(f"Need {gold_cost - gold} more gold")
        entries.append(
            {
                "id": recipe_id,
                "name": recipe.get("name", recipe_id),
                "description": recipe.get("description", ""),
                "shards": shard_cost,
                "gold": gold_cost,
                "result": recipe.get("result", ""),
                "unique": bool(recipe.get("unique", False)),
                "crafted": crafted,
                "can_craft": not reasons,
                "reasons": reasons,
            }
        )
    return entries


def craft_recipe(player, recipe_id, game=None):
    """Consumes shards/gold and creates one recipe result."""
    recipe = get_recipe(recipe_id)
    if recipe is None:
        message = f"Unknown recipe: {recipe_id}."
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}

    recipe_id = str(recipe["id"])
    if recipe.get("unique") and _is_crafted(player, recipe_id):
        message = f"{recipe.get('name', recipe_id)} has already been forged."
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}

    definition = item_definition(recipe.get("result"))
    if definition is None:
        message = f"The forge cannot shape {recipe.get('result', 'that item')}."
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}

    shard_cost = max(0, int(recipe.get("shards", 0) or 0))
    gold_cost = max(0, int(recipe.get("gold", 0) or 0))
    if rune_shards(player) < shard_cost:
        message = (
            f"You need {shard_cost} Rune Shards for "
            f"{recipe.get('name', recipe_id)}."
        )
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}
    if int(getattr(player, "gold", 0) or 0) < gold_cost:
        message = (
            f"You need {gold_cost} gold for {recipe.get('name', recipe_id)}."
        )
        if game:
            game.io.show_message(message)
        return {"success": False, "message": message}

    player.rune_shards = rune_shards(player) - shard_cost
    player.gold -= gold_cost
    item = Item.from_dict(definition)
    player.add_item(item)

    if recipe.get("unique"):
        claimed = getattr(player, "claimed_rewards", None)
        if not isinstance(claimed, list):
            claimed = []
            player.claimed_rewards = claimed
        flag = _crafted_flag(recipe_id)
        if flag not in claimed:
            claimed.append(flag)

    message = (
        f"You forge {item.name} for {gold_cost} gold and "
        f"{shard_cost} Rune Shards."
    )
    if game:
        game.io.show_message(message)
    return {
        "success": True,
        "message": message,
        "item": item.name,
        "shards": player.rune_shards,
        "gold": player.gold,
    }
