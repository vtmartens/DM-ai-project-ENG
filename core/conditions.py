"""Data-driven timed conditions applied by abilities and effects.

Conditions live in ``player.conditions`` as ``{turns: N, ...}`` entries. The
engine applies them, ticks damage/healing and save-to-end checks at the end of
a combat round, and exposes their roll/damage modifiers to the rest of combat.
Poison remains special-cased by ``CombatState`` and is not in this catalogue,
so it is never ticked twice.
"""

from __future__ import annotations

from util.data_manager import get_data_manager


def condition_catalogue() -> dict:
    data = get_data_manager().load_data("conditions", "conditions.json")
    return data if isinstance(data, dict) else {}


def _definition(condition_id):
    data = condition_catalogue().get(condition_id)
    return data if isinstance(data, dict) else None


def apply_condition(
    entity, condition_id, turns=None, game=None, message=None, **params
) -> bool:
    """Applies or refreshes a catalogued condition on an entity."""
    definition = _definition(condition_id)
    if definition is None:
        return False

    conditions = getattr(entity, "conditions", None)
    if not isinstance(conditions, dict):
        conditions = {}
        entity.conditions = conditions

    default_turns = int(definition.get("duration", 1) or 1)
    duration = max(1, int(turns if turns is not None else default_turns))
    name = definition.get("name", condition_id)

    current = conditions.get(condition_id)
    if isinstance(current, dict):
        current["turns"] = max(int(current.get("turns", 0) or 0), duration)
        for key, value in params.items():
            current.setdefault(key, value)
        text = message or f"{name} lingers."
    else:
        entry = {"turns": duration}
        entry.update(params)
        conditions[condition_id] = entry
        text = message or definition.get(
            "message", f"You are affected by {name}."
        )

    if game:
        game.io.show_message(text)
    return True


def remove_condition(entity, condition_id, game=None, message=None) -> bool:
    conditions = getattr(entity, "conditions", None)
    if not isinstance(conditions, dict) or condition_id not in conditions:
        return False
    conditions.pop(condition_id, None)
    if game and message:
        game.io.show_message(message)
    return True


def _is_player(entity, game) -> bool:
    return game is not None and entity is getattr(game, "player", None)


def tick_conditions(entity, game=None) -> list[str]:
    """Ticks active conditions at the end of a round; returns expired ids."""
    conditions = getattr(entity, "conditions", None)
    if not isinstance(conditions, dict):
        return []
    player_subject = _is_player(entity, game)
    entity_name = str(getattr(entity, "name", "the target"))

    catalogue = condition_catalogue()
    expired = []
    for condition_id in list(conditions):
        definition = catalogue.get(condition_id)
        if not isinstance(definition, dict):
            # Poison, Guidance and simple advantage/disadvantage flags are
            # handled by their own systems.
            continue

        entry = conditions.get(condition_id)
        if not isinstance(entry, dict):
            entry = {"turns": int(definition.get("duration", 1) or 1)}
            conditions[condition_id] = entry

        name = definition.get("name", condition_id)
        tick = definition.get("tick", {})
        if isinstance(tick, dict):
            damage = int(tick.get("damage", 0) or 0)
            heal = int(tick.get("heal", 0) or 0)
            if damage > 0:
                entity.hp = max(0, int(getattr(entity, "hp", 0) or 0) - damage)
                if game:
                    recipient = "you" if player_subject else entity_name
                    game.io.show_message(
                        f"{name} deals {damage} damage to {recipient}."
                    )
            if heal > 0:
                hp_max = int(getattr(entity, "hp_max", 0) or 0)
                before = int(getattr(entity, "hp", 0) or 0)
                entity.hp = min(hp_max, before + heal) if hp_max else before + heal
                if game and entity.hp > before:
                    game.io.show_message(
                        f"{name} restores {entity.hp - before} HP."
                    )

        save = definition.get("save")
        if isinstance(save, dict):
            passed = entity.saving_throw(
                str(save.get("ability", "constitution")),
                int(save.get("dc", 10) or 10),
                game,
            )
            if passed:
                conditions.pop(condition_id, None)
                expired.append(condition_id)
                if game:
                    if player_subject:
                        game.io.show_message(f"You recover from {name}.")
                    else:
                        game.io.show_message(
                            f"{entity_name} recovers from {name}."
                        )
                continue

        turns = int(entry.get("turns", 0) or 0) - 1
        if turns <= 0:
            conditions.pop(condition_id, None)
            expired.append(condition_id)
            if game:
                if player_subject:
                    game.io.show_message(f"{name} fades.")
                else:
                    game.io.show_message(
                        f"{name} fades from {entity_name}."
                    )
        else:
            entry["turns"] = turns

    return expired


def _condition_roll_flags(entity, field, kind):
    conditions = getattr(entity, "conditions", None)
    if not isinstance(conditions, dict):
        return False, False

    catalogue = condition_catalogue()
    advantage = False
    disadvantage = False
    for condition_id in conditions:
        definition = catalogue.get(condition_id)
        if not isinstance(definition, dict):
            continue
        rolls = definition.get(field, {})
        if not isinstance(rolls, dict):
            continue

        for mode, flag in (("advantage", True), ("disadvantage", False)):
            targets = rolls.get(mode, [])
            if isinstance(targets, str):
                targets = [targets]
            if kind in targets or "all" in targets:
                if flag:
                    advantage = True
                else:
                    disadvantage = True
    return advantage, disadvantage


def condition_roll_flags(entity, kind="check"):
    """Returns (advantage, disadvantage) for the entity's own rolls."""
    return _condition_roll_flags(entity, "rolls", kind)


def condition_incoming_roll_flags(entity, kind="attack"):
    """Returns flags applied to attacks made against the entity."""
    return _condition_roll_flags(entity, "incoming_rolls", kind)


def condition_blocks_abilities(entity) -> bool:
    """Whether an active condition prevents special abilities."""
    conditions = getattr(entity, "conditions", None)
    if not isinstance(conditions, dict):
        return False
    catalogue = condition_catalogue()
    return any(
        isinstance(catalogue.get(condition_id), dict)
        and bool(catalogue[condition_id].get("blocks_abilities"))
        for condition_id in conditions
    )


def condition_stand_up(entity) -> str | None:
    """Returns the first condition that costs the entity a turn to clear."""
    conditions = getattr(entity, "conditions", None)
    if not isinstance(conditions, dict):
        return None
    catalogue = condition_catalogue()
    for condition_id in conditions:
        definition = catalogue.get(condition_id)
        if isinstance(definition, dict) and definition.get("stand_up"):
            return condition_id
    return None


def condition_damage_modifier(entity) -> int:
    """Sum of damage modifiers from active catalogued conditions."""
    conditions = getattr(entity, "conditions", None)
    if not isinstance(conditions, dict):
        return 0

    catalogue = condition_catalogue()
    total = 0
    for condition_id in conditions:
        definition = catalogue.get(condition_id)
        if isinstance(definition, dict):
            total += int(definition.get("damage_modifier", 0) or 0)
    return total
