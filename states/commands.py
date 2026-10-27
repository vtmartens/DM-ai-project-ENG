"""Deterministic natural-language command parsing and target resolution.

The engine stays authoritative: these helpers only map a command to an
existing state transition, item use, or object interaction, and return False
when the caller should fall back to its normal menu.
"""

from __future__ import annotations

import re
from collections import deque

GENERIC_EXIT_TARGETS = {"exit", "door", "way out", "leave", ""}

TARGETED_PATTERNS = (
    ("talk", r"^(?:talk|speak|chat|converse)(?:\s+(?:to|with))?\s+(.+)$"),
    ("attack", r"^(?:attack|fight|hit|kill|challenge)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("ability", r"^(?:use\s+ability|cast(?:\s+spell)?)\s+(.+)$"),
    ("use", r"^(?:use|drink|quaff|consume)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("equip", r"^(?:equip|wield|wear)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("go", r"^(?:go|travel|walk|head|move|approach)(?:\s+to)?\s+(?:the\s+)?(.+)$"),
    ("examine", r"^(?:examine|inspect|look\s+at|check)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("interact", r"^(?:interact\s+with|open|pull|push)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
    ("disarm", r"^(?:disarm|disable|defuse|deactivate)\s+(?:the\s+|a\s+|an\s+)?(.+)$"),
)


def normalize_name(value) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value).casefold())
    text = re.sub(r"\b(?:the|a|an)\b", " ", text)
    return " ".join(text.split())


def parse_targeted_command(command):
    """Returns (action, target) or None for a non-targeted command."""
    text = command.strip().casefold()
    if text in {
        "leave",
        "leave tavern",
        "leave the tavern",
        "leave market",
        "leave the market",
        "leave cellar",
        "leave the cellar",
        "leave warehouse",
        "leave the warehouse",
    }:
        return "go", "exit"

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


def find_npc_position(game, npc):
    """Finds an NPC's cell on the player's current map."""
    current_map = (
        game.map_manager.get_map(game.player.current_map)
        if game.player.current_map
        else None
    )
    if not current_map:
        return None

    wanted = normalize_name(getattr(npc, "name", ""))
    for position, candidate in current_map.npc.items():
        if candidate is npc or normalize_name(
            getattr(candidate, "name", "")
        ) == wanted:
            return position
    return None


def _find_path_to_adjacent(game, target_position):
    """BFS from the player to any free cell next to ``target_position``."""
    current_map = (
        game.map_manager.get_map(game.player.current_map)
        if game.player.current_map
        else None
    )
    if not current_map:
        return None

    start = (game.player.x, game.player.y)
    target_x, target_y = target_position
    blocked = set(current_map.npc) | set(current_map.items) | set(current_map.doors)

    goals = set()
    for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
        cell = (target_x + dx, target_y + dy)
        if cell == start:
            goals.add(cell)
        elif cell not in blocked and current_map.is_valid_position(*cell):
            goals.add(cell)

    if not goals:
        return None
    if start in goals:
        return [start]

    queue = deque([start])
    parents = {start: None}

    while queue:
        current = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor in parents or neighbor in blocked:
                continue
            if not current_map.is_valid_position(*neighbor):
                continue

            parents[neighbor] = current
            if neighbor in goals:
                path = [neighbor]
                while parents[path[-1]] is not None:
                    path.append(parents[path[-1]])
                path.reverse()
                return path

            queue.append(neighbor)

    return None


def walk_to_target(game, target_position, label) -> bool:
    """Moves the player next to ``target_position`` if a path exists."""
    path = _find_path_to_adjacent(game, target_position)
    if path is None:
        return False

    steps = len(path) - 1
    if steps == 0:
        game.io.show_message(f"You are already next to {label}.")
        return True

    game.player.set_position(path[-1][0], path[-1][1])
    suffix = "step" if steps == 1 else "steps"
    game.io.show_message(f"You move to {label} ({steps} {suffix}).")
    if getattr(game.player, "stealthed", False):
        from core.stealth import maintain_stealth

        maintain_stealth(game.player, game)
    return True


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
        if not current_map.object_is_hidden(obj)
    ]
    return match_name(candidates, target)


def resolve_map_door(game, target):
    """Finds a map exit: (position, destination, label) or None."""
    current_map = (
        game.map_manager.get_map(game.player.current_map)
        if game.player.current_map
        else None
    )
    if not current_map or not current_map.doors:
        return None

    wanted = normalize_name(target)
    generic = wanted in GENERIC_EXIT_TARGETS

    if not generic:
        for position, destination in current_map.doors.items():
            destination_name = destination[0]
            label = f"exit to {destination_name}"
            if (
                normalize_name(destination_name) in wanted
                or wanted in normalize_name(label)
                or wanted in normalize_name(destination_name)
            ):
                return position, destination_name, label
        return None

    player = game.player
    position, destination = min(
        current_map.doors.items(),
        key=lambda item: abs(item[0][0] - player.x)
        + abs(item[0][1] - player.y),
    )
    return position, destination[0], f"exit to {destination[0]}"


def _enter_destination_state(game, destination):
    if destination == "market":
        from states.market import MarketState

        game.change_state(MarketState(game))
    elif destination == "tavern":
        from states.tavern import TavernState

        game.change_state(TavernState(game))
    elif destination == "waystation":
        from states.waystation import WaystationState

        game.change_state(WaystationState(game))
    elif destination == "underroad":
        from states.underroad import UnderroadState

        game.change_state(UnderroadState(game))
    else:
        from states.map_state import MapState

        game.change_state(MapState(origin_state=game.current_state()))


def leave_through_door(game, door_position, destination, label) -> bool:
    """Walks to a map exit, steps through it, and enters the destination state."""
    player = game.player
    current_map = game.map_manager.get_map(player.current_map)

    if (player.x, player.y) == door_position:
        # An older session can leave the player standing on the exit after a
        # failed transition; step through from the door cell directly.
        door = current_map.doors.get(door_position) if current_map else None
        if not door:
            return False
        _, x_dest, y_dest = door
        result = dict(
            game.map_manager.change_player_map(player, destination, x_dest, y_dest)
        )
        result["change_map"] = result.get("success", False)
    else:
        if not walk_to_target(game, door_position, label):
            return False

        dx = door_position[0] - player.x
        dy = door_position[1] - player.y
        if abs(dx) + abs(dy) != 1:
            return False

        result = player.move(dx, dy, game.map_manager)

    if not result.get("change_map"):
        game.io.show_message(result.get("message") or f"The {label} is blocked.")
        return True

    _enter_destination_state(game, destination)
    game.io.show_message(f"You leave through the {label}.")
    return True


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
        from core.quests import build_ally_party
        from core.stealth import clear_stealth
        from states.combat import CombatState

        current_map = game.map_manager.get_map(game.player.current_map)
        group = getattr(npc, "group", None)
        enemies = [npc]
        if group and current_map:
            grouped = [
                candidate
                for candidate in current_map.npc.values()
                if getattr(candidate, "group", None) == group
            ]
            if grouped:
                enemies = grouped

        surprised = clear_stealth(
            game.player,
            game,
            "You break cover as you strike.",
        )
        game.push_state(
            CombatState(
                enemies=enemies,
                allies=build_ally_party(game.player),
                surprised=surprised,
            )
        )
        return True

    if action == "ability":
        from core.abilities import resolve_ability, use_ability

        name, definition = resolve_ability(game.player, target)
        if not name:
            game.io.show_message(f"You don't know an ability called {target}.")
            return False
        use_ability(game, name, definition)
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
        # A generic exit target always means a map exit, even on maps that also
        # contain an object named "exit_door" (as the cellar does).
        if normalize_name(target) in GENERIC_EXIT_TARGETS:
            door = resolve_map_door(game, target)
            if door is not None:
                position, destination, label = door
                if not leave_through_door(game, position, destination, label):
                    game.io.show_message(
                        f"You cannot find a path to the {label}."
                    )
                return True

        destination = resolve_map(game, target)
        if destination is not None:
            from states.map_selection_state import MapSelectionState

            selector = MapSelectionState(game)
            selector.current_map = game.player.current_map
            selector._change_map(game, destination)
            return True

        npc = resolve_npc(game, target, extra_npcs)
        if npc is not None:
            position = find_npc_position(game, npc)
            if position is None:
                game.io.show_message(f"You don't see {npc.name} on this map.")
            elif not walk_to_target(game, position, npc.name):
                game.io.show_message(f"You cannot find a path to {npc.name}.")
            return True

        resolved = resolve_map_object(game, target)
        if resolved is not None:
            position, obj = resolved
            if not walk_to_target(
                game, position, getattr(obj, "name", str(obj))
            ):
                game.io.show_message(
                    f"You cannot find a path to {getattr(obj, 'name', target)}."
                )
            return True

        door = resolve_map_door(game, target)
        if door is not None:
            position, destination, label = door
            if not leave_through_door(game, position, destination, label):
                game.io.show_message(f"You cannot find a path to the {label}.")
            return True

        game.io.show_message(f"There is no place called {target}.")
        return False

    if action == "disarm":
        resolved = resolve_map_object(game, target)
        if resolved is None:
            game.io.show_message(f"You don't see {target} here.")
            return False
        (x, y), obj = resolved
        label = getattr(obj, "display_name", getattr(obj, "name", target))
        if abs(game.player.x - x) + abs(game.player.y - y) > 1:
            game.io.show_message(f"You need to move closer to {label}.")
            return True
        disarm = getattr(obj, "disarm", None)
        if not callable(disarm):
            game.io.show_message(f"You cannot disarm {label}.")
            return True
        disarm(game.player, game)
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
