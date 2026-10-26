"""Deterministic natural-language command parsing and target resolution.

The engine stays authoritative: these helpers only map a command to an
existing state transition, item use, or object interaction, and return False
when the caller should fall back to its normal menu.
"""

from __future__ import annotations

import re

TARGETED_PATTERNS = (
    ("talk", r"^(?:talk|speak|chat|converse)(?:\s+(?:to|with))?\s+(.+)$"),
    ("attack", r"^(?:attack|fight|hit|kill|challenge)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("use", r"^(?:use|drink|quaff|consume)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("equip", r"^(?:equip|wield|wear)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("go", r"^(?:go|travel|walk|head)(?:\s+to)?\s+(?:the\s+)?(.+)$"),
    ("examine", r"^(?:examine|inspect|look\s+at|check)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("interact", r"^(?:interact\s+with|open|pull|push)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
)


def normalize_name(value) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value).casefold())
    text = re.sub(r"\b(?:the|a|an)\b", " ", text)
    return " ".join(text.split())


def parse_targeted_command(command):
    """Returns (action, target) or None for a non-targeted command."""
    for action, pattern in TARGETED_PATTERNS:
        match = re.match(pattern, command.strip(), re.IGNORECASE)
        if not match:
            continue

        target = match.group(1).strip()
        if not target:
            continue

        # "check stats" / "inspect inventory" are menu commands, not targets.
        if action == "examine" and normalize_name(target) in {
            "stats",
            "status",
            "inventory",
            "map",
        }:
            return None

        return action, target

    return None


def match_name(candidates, target):
    """Matches a target against (name, value) pairs: exact, prefix, substring."""
    wanted = normalize_name(target)
    if not wanted:
        return None

    for name, value in candidates:
        if normalize_name(name) == wanted:
            return value

    for name, value in candidates:
        normalized = normalize_name(name)
        if normalized.startswith(wanted) or wanted in normalized:
            return value

    return None


def resolve_npc(game, target, extra_npcs=()):
    candidates = {
        getattr(npc, "name", ""): npc for npc in (extra_npcs or ())
    }
    current_map = (
        game.map_manager.get_map(game.player.current_map)
        if game.player.current_map
        else None
    )
    if current_map:
        for npc in current_map.npc.values():
            candidates.setdefault(getattr(npc, "name", ""), npc)
    return match_name(list(candidates.items()), target)


def resolve_inventory_item(game, target):
    candidates = [
        (getattr(item, "name", str(item)), item)
        for item in game.player.inventory
        if not isinstance(item, str)
    ]
    return match_name(candidates, target)


def resolve_map(game, target):
    return match_name([(name, name) for name in game.map_manager.maps], target)


def resolve_map_object(game, target):
    current_map = (
        game.map_manager.get_map(game.player.current_map)
        if game.player.current_map
        else None
    )
    if not current_map:
        return None

    candidates = [
        (getattr(obj, "name", str(obj)), (pos, obj))
        for pos, obj in current_map.items.items()
    ]
    return match_name(candidates, target)


def handle_targeted_command(game, action, target, extra_npcs=()) -> bool:
    """Executes a targeted command. False means the caller should open its menu."""
    if action == "talk":
        npc = resolve_npc(game, target, extra_npcs)
        if npc is None:
            game.io.show_message(f"You don't see {target} here.")
            return False
        from states.dialogue import DialogueState

        game.push_state(DialogueState(npc))
        return True

    if action == "attack":
        npc = resolve_npc(game, target, extra_npcs)
        if npc is None:
            game.io.show_message(f"You don't see {target} here.")
            return False
        from states.combat import CombatState

        game.push_state(CombatState(hostile_npc=npc))
        return True

    if action in {"use", "equip"}:
        item = resolve_inventory_item(game, target)
        if item is None:
            game.io.show_message(f"You don't have {target}.")
            return False
        if action == "use":
            item.use(game.player, game)
        elif getattr(item, "type", None) in {"weapon", "armor", "accessory"}:
            item.equip(game.player, game)
        else:
            game.io.show_message(f"{item.name} cannot be equipped.")
        return True

    if action == "go":
        destination = resolve_map(game, target)
        if destination is None:
            game.io.show_message(f"There is no place called {target}.")
            return False
        from states.map_selection_state import MapSelectionState

        selector = MapSelectionState(game)
        selector.current_map = game.player.current_map
        selector._change_map(game, destination)
        return True

    if action in {"examine", "interact"}:
        resolved = resolve_map_object(game, target)
        if resolved is None:
            npc = resolve_npc(game, target, extra_npcs)
            if npc is not None:
                if action == "examine":
                    description = getattr(npc, "description", "")
                    game.io.show_message(
                        f"{npc.name}: {description}"
                        if description
                        else npc.show_info()
                    )
                else:
                    from states.dialogue import DialogueState

                    game.push_state(DialogueState(npc))
                return True
            game.io.show_message(f"You don't see {target} here.")
            return False

        (x, y), obj = resolved
        description = getattr(obj, "description", "")
        state_name = getattr(obj, "state", None)
        label = getattr(obj, "name", str(obj))
        if state_name:
            label += f" ({state_name})"
        if description:
            label += f": {description}"
        game.io.show_message(label)

        if action == "examine":
            return True

        distance = abs(game.player.x - x) + abs(game.player.y - y)
        if distance > 1:
            game.io.show_message(f"You need to move closer to {obj.name}.")
            return True
        obj.interact(game.player, game)
        return True

    return False
