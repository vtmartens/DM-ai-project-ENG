"""Data-driven class abilities and their deterministic combat effects."""

from __future__ import annotations

import logging

from util.data_manager import get_data_manager

SUPPORTED_EFFECTS = {"damage", "heal", "guard", "shield", "evade", "bless"}


def _normalize(value) -> str:
    return str(value or "").strip().casefold()


def ability_catalogue():
    """Returns the ability definitions from ``data/classes/abilities.json``."""
    data = get_data_manager().load_data("classes", "abilities.json")
    return data if isinstance(data, dict) else {}


def _class_data(player):
    classes = getattr(player, "classes_data", None)
    if not isinstance(classes, dict):
        classes = get_data_manager().get_classes()
    return classes.get(getattr(player, "char_class", ""), {})


def _ability_rows(player):
    """Returns every class ability with its required level and unlock state."""
    class_data = _class_data(player)
    catalogue = ability_catalogue()
    level = int(getattr(player, "level", 1) or 1)

    ability_levels = []
    seen = set()
    for name in class_data.get("special_abilities", []):
        ability_levels.append((name, 1))
        seen.add(name)

    progression = class_data.get("progression", {}).get("abilities_per_level", {})
    for raw_level, name in sorted(progression.items(), key=lambda item: int(item[0])):
        if name in seen:
            continue
        ability_levels.append((name, int(raw_level)))
        seen.add(name)

    details = []
    for name, required_level in ability_levels:
        definition = catalogue.get(name)
        if not isinstance(definition, dict):
            logging.warning("No definition found for class ability %s", name)
            continue
        details.append(
            {
                "id": definition.get("id", _normalize(name).replace(" ", "_")),
                "name": name,
                "class": definition.get("class", getattr(player, "char_class", "")),
                "description": definition.get("description", ""),
                "mana_cost": int(definition.get("mana_cost", 0) or 0),
                "combat_only": bool(definition.get("combat_only", False)),
                "ignore_defense": bool(definition.get("ignore_defense", False)),
                "effect": dict(definition.get("effect", {})),
                "required_level": required_level,
                "unlocked": level >= required_level,
            }
        )
    return details


def player_abilities(player, include_locked=False):
    """Returns serializable details for the player's class abilities.

    Locked progression abilities are included only when ``include_locked`` is
    true; menus and ability execution use the unlocked list by default.
    """
    details = _ability_rows(player)
    if include_locked:
        return details
    return [ability for ability in details if ability["unlocked"]]


def abilities_unlocked_at_level(player, level):
    """Returns the names of abilities newly unlocked at ``level``."""
    return [
        ability["name"]
        for ability in _ability_rows(player)
        if ability["required_level"] == level and ability["unlocked"]
    ]


def resolve_ability(player, identifier):
    """Finds an unlocked ability by name or id. Returns ``(name, definition)``."""
    wanted = _normalize(identifier)
    if not wanted:
        return None, None

    for ability in player_abilities(player):
        if wanted in {_normalize(ability["name"]), _normalize(ability["id"])}:
            return ability["name"], ability
    return None, None


def _combat_state(game):
    from states.combat import CombatState

    current = game.current_state() if hasattr(game, "current_state") else None
    if isinstance(current, CombatState) and getattr(current, "opponent", None) is not None:
        return current
    return None


def _combat_effects(combat):
    effects = getattr(combat, "effects", None)
    if not isinstance(effects, dict):
        effects = {}
        combat.effects = effects
    return effects


def use_ability(game, name, definition=None):
    """Applies an ability. Returns True when it was used and mana was spent."""
    player = game.player
    combat = _combat_state(game)
    if definition is None:
        _, definition = resolve_ability(player, name)
    if not isinstance(definition, dict):
        game.io.show_message(f"You don't know an ability called {name}.")
        return False

    if definition.get("combat_only") and combat is None:
        game.io.show_message(f"{name} can only be used in combat.")
        return False

    cost = int(definition.get("mana_cost", 0) or 0)
    mana = int(getattr(player, "mana", 0) or 0)
    if mana < cost:
        game.io.show_message(f"You need {cost} mana to use {name}.")
        return False

    effect = definition.get("effect", {})
    kind = effect.get("type")
    message = None

    if kind == "damage":
        if combat is None:
            game.io.show_message(f"{name} can only be used in combat.")
            return False
        effects = _combat_effects(combat)
        blessing = int(effects.pop("bless_attack", 0) or 0)
        if "flat" in effect:
            damage = int(effect["flat"])
        elif "multiplier" in effect:
            damage = max(1, int(player.strength) * int(effect["multiplier"]))
        else:
            damage = max(1, int(player.strength) + int(effect.get("bonus", 0)))
        damage += blessing
        defense = (
            0
            if definition.get("ignore_defense")
            else int(getattr(combat.opponent, "defense", 0) or 0)
        )
        dealt = max(1, damage - defense)
        combat.opponent.hp = max(0, combat.opponent.hp - dealt)
        message = f"You use {name} and deal {dealt} damage to {combat.opponent.name}."
        if blessing:
            message = f"Your blessing adds {blessing} damage. " + message

    elif kind == "heal":
        if player.hp >= player.hp_max:
            game.io.show_message("You are already at full health.")
            return False
        amount = int(effect.get("amount", 0))
        before = player.hp
        player.hp = min(player.hp_max, player.hp + amount)
        message = f"You use {name} and recover {player.hp - before} HP."

    elif kind == "guard":
        if combat is None:
            game.io.show_message(f"{name} can only be used in combat.")
            return False
        amount = int(effect.get("amount", 0))
        effects = _combat_effects(combat)
        effects["guard"] = int(effects.get("guard", 0) or 0) + amount
        message = f"You use {name}, reducing the next incoming attack by {amount}."

    elif kind == "shield":
        if combat is None:
            game.io.show_message(f"{name} can only be used in combat.")
            return False
        amount = int(effect.get("amount", 0))
        effects = _combat_effects(combat)
        effects["shield"] = int(effects.get("shield", 0) or 0) + amount
        message = f"You use {name}, raising a shield that absorbs up to {amount} damage."

    elif kind == "evade":
        if combat is None:
            game.io.show_message(f"{name} can only be used in combat.")
            return False
        _combat_effects(combat)["evade"] = True
        message = f"You use {name} and prepare to avoid the next attack."

    elif kind == "bless":
        if combat is None:
            game.io.show_message(f"{name} can only be used in combat.")
            return False
        effects = _combat_effects(combat)
        attack_bonus = int(effect.get("attack", 0) or 0)
        defense_bonus = int(effect.get("defense", 0) or 0)
        effects["bless_attack"] = int(effects.get("bless_attack", 0) or 0) + attack_bonus
        effects["bless_defense"] = int(effects.get("bless_defense", 0) or 0) + defense_bonus
        message = (
            f"You use {name}, adding {attack_bonus} damage to your next attack "
            f"and warding off {defense_bonus} damage."
        )

    else:
        game.io.show_message(f"{name} has no usable effect.")
        return False

    player.mana = mana - cost
    if cost:
        message += f" ({cost} mana spent, {player.mana} left)"
    game.io.show_message(message)
    return True
