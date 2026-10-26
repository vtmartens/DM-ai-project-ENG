from __future__ import annotations

from typing import Any


def _names(objects) -> list[str]:
    return [getattr(obj, "name", str(obj)) for obj in objects.values()]


def build_context(game) -> dict[str, Any]:
    """Builds the small, serializable snapshot sent to the narrator.

    Deliberately excludes inventory, full stats and map contents to keep each
    narration request small and cheap.
    """
    if game is None:
        return {}

    player = getattr(game, "player", None)
    if player is None:
        return {}

    context: dict[str, Any] = {
        "player": {
            "name": getattr(player, "name", "Adventurer"),
            "class": getattr(player, "char_class", ""),
            "hp": getattr(player, "hp", 0),
            "hp_max": getattr(player, "hp_max", 0),
        }
    }

    current_map = getattr(player, "current_map", None)
    if current_map:
        context["map"] = current_map
        context["position"] = [getattr(player, "x", 0), getattr(player, "y", 0)]

    state = game.current_state() if hasattr(game, "current_state") else None
    if state is not None:
        context["state"] = type(state).__name__

    position = game.get_player_position() if hasattr(game, "get_player_position") else None
    if isinstance(position, dict):
        nearby = {}
        if position.get("nearby_items"):
            nearby["items"] = _names(position["nearby_items"])
        if position.get("nearby_npcs"):
            nearby["npcs"] = _names(position["nearby_npcs"])
        if nearby:
            context["nearby"] = nearby

    return context
