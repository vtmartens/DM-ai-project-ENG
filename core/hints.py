"""Deterministic Dungeon Master hints derived from the current game state.

Hints never change state and never decide for the player. They point at the
most actionable fact available: a fight, a dialogue, a ready quest, a locked
door, low health, or a nearby character/object.
"""

from __future__ import annotations

from items.interactive_object import Chest, Door, Trap
from items.keys import find_matching_key

HEALING_TYPES = {"heal", "light_heal", "grave_heal"}


def _label(obj) -> str:
    label = str(getattr(obj, "name", "object")).replace("_", " ").strip()
    return label[:1].upper() + label[1:] if label else "Object"


def _current_map(game, player):
    manager = getattr(game, "map_manager", None)
    map_name = getattr(player, "current_map", None)
    if manager is None or not map_name:
        return None
    return manager.get_map(map_name)


def _distance(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _is_locked_object(obj) -> bool:
    return (
        isinstance(obj, (Chest, Door))
        and bool(getattr(obj, "requires_key", False))
        and getattr(obj, "state", "closed") not in {"open", "unlocked"}
    )


def _ready_quest_hint(player):
    for quest in getattr(player, "active_quests", []):
        if not isinstance(quest, dict) or quest.get("status") != "ready":
            continue
        title = quest.get("title", "Your quest")
        turn_in = quest.get("turn_in")
        if turn_in:
            return f"{title} is ready to turn in. Return to {turn_in} for your reward."
        return f"{title} is ready to complete."
    return None


def _active_quest_hint(player):
    for quest in getattr(player, "active_quests", []):
        if not isinstance(quest, dict):
            continue
        title = quest.get("title", "Your quest")
        objective = quest.get("objective")
        if objective:
            return f"{title}: {objective}"
    return None


def _locked_object_hint(game, player):
    current_map = _current_map(game, player)
    if current_map is None:
        return None

    position = (getattr(player, "x", 0), getattr(player, "y", 0))
    candidates = []
    for cell, obj in current_map.items.items():
        if not _is_locked_object(obj):
            continue
        distance = _distance(position, cell)
        if distance > 2:
            continue
        candidates.append((distance, str(getattr(obj, "name", "")).casefold(), obj))

    if not candidates:
        return None

    _, _, locked = min(candidates, key=lambda entry: (entry[0], entry[1]))
    label = _label(locked)
    key = find_matching_key(player, getattr(locked, "name", ""))
    if key is not None:
        return f"The {label} is locked. Use {key.name} on it."
    return f"The {label} is locked. Find the matching key, or cast Knock if you know it."


def _health_hint(player, suffix: str = "") -> str | None:
    hp = int(getattr(player, "hp", 0) or 0)
    hp_max = int(getattr(player, "hp_max", 0) or 0)
    if not hp_max or hp > max(1, hp_max // 3):
        return None

    inventory = getattr(player, "inventory", []) or []
    potion = next(
        (
            item
            for item in inventory
            if getattr(item, "type", "") in HEALING_TYPES
            and getattr(item, "name", None)
        ),
        None,
    )
    if potion is not None:
        hint = f"You are at {hp}/{hp_max} HP. Use {potion.name} before the next fight."
    else:
        hint = f"You are at {hp}/{hp_max} HP. Retreat or rest before the next fight."
    return hint + suffix


def _combat_hint(game, player, state):
    conditions = getattr(player, "conditions", None)
    if isinstance(conditions, dict):
        if "charmed" in conditions:
            return (
                "You are charmed and cannot attack the charmer. "
                "Use Resist the Charm or target another enemy."
            )
        if "restrained" in conditions:
            return (
                "You are restrained: attacks have disadvantage and you "
                "cannot flee. Use Break Free."
            )
        if "blinded" in conditions:
            return (
                "You are blinded: your attacks have disadvantage and "
                "incoming attacks have advantage. Use your save or an item."
            )
        if "prone" in conditions:
            return "You are prone. Use Stand up before attacking."
        if "staggered" in conditions:
            return "You are staggered. Special abilities are unavailable; use a weapon or item."

    living = [
        enemy
        for enemy in (getattr(state, "enemies", None) or [])
        if getattr(enemy, "hp", 0) > 0
    ]
    if not living:
        return "The fight is nearly over. Finish the last enemy."

    target = getattr(state, "opponent", None)
    if target is None or getattr(target, "hp", 0) <= 0:
        target = living[0]
    name = getattr(target, "name", "the enemy")
    health = _health_hint(player, suffix=f" Then focus on {name}.")
    if health:
        return health
    return (
        f"Focus on {name} ({getattr(target, 'hp', 0)} HP). "
        "Use an ability or a targeted attack."
    )


def _dialogue_hint(state):
    npc = getattr(state, "npc", None)
    if npc is None:
        return None
    return (
        f"Talk to {getattr(npc, 'name', 'the NPC')}; "
        "choose an option in the dialogue card to continue."
    )


def _npc_hint(game, player):
    current_map = _current_map(game, player)
    if current_map is None:
        return None

    position = (getattr(player, "x", 0), getattr(player, "y", 0))
    candidates = []
    for cell, npc in current_map.npc.items():
        if getattr(npc, "hp", 1) <= 0:
            continue
        distance = _distance(position, cell)
        if distance > 2:
            continue
        candidates.append((distance, str(getattr(npc, "name", "")).casefold(), npc))

    if not candidates:
        return None

    _, _, npc = min(candidates, key=lambda entry: (entry[0], entry[1]))
    name = getattr(npc, "name", "Someone")
    if getattr(npc, "friendly", True):
        return f"{name} is nearby. Talk to them."
    return f"{name} is nearby and looks hostile. Prepare for a fight."


def _object_hint(game, player):
    current_map = _current_map(game, player)
    if current_map is None:
        return None

    position = (getattr(player, "x", 0), getattr(player, "y", 0))
    candidates = []
    for cell, obj in current_map.items.items():
        if isinstance(obj, (Door, Trap)):
            continue
        if getattr(obj, "state", "") in {"open", "activated", "broken"}:
            continue
        distance = _distance(position, cell)
        if distance > 2:
            continue
        candidates.append((distance, str(getattr(obj, "name", "")).casefold(), obj))

    if not candidates:
        return None

    _, _, obj = min(candidates, key=lambda entry: (entry[0], entry[1]))
    return f"{_label(obj)} is nearby. Inspect or interact with it."


def build_hint(game) -> str:
    """Returns a short, deterministic hint for the current game state."""
    player = getattr(game, "player", None)
    if player is None:
        return "Choose a class and begin your adventure."

    state = game.current_state() if hasattr(game, "current_state") else None
    state_name = type(state).__name__ if state is not None else ""

    if state_name == "CombatState":
        hint = _combat_hint(game, player, state)
        if hint:
            return hint

    if state_name == "DialogueState":
        hint = _dialogue_hint(state)
        if hint:
            return hint

    hint = _ready_quest_hint(player)
    if hint:
        return hint

    hint = _locked_object_hint(game, player)
    if hint:
        return hint

    hint = _active_quest_hint(player)
    if hint:
        return hint

    hint = _health_hint(player)
    if hint:
        return hint

    hint = _npc_hint(game, player)
    if hint:
        return hint

    hint = _object_hint(game, player)
    if hint:
        return hint

    return "Explore the area, talk to the people nearby, and check your quest log."
