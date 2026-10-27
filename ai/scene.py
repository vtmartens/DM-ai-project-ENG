"""Deterministic location descriptions with optional AI colour."""

from __future__ import annotations

import logging

from ai.context import build_context

logger = logging.getLogger("game_rpg.ai")

ENGINE_FALLBACK = "Choose a class and begin your adventure."


def scene_catalogue() -> dict:
    from util.data_manager import get_data_manager

    data = get_data_manager().load_data("scenes", "locations.json")
    return data if isinstance(data, dict) else {}


def _location_label(map_name) -> str:
    label = str(map_name or "").replace("_", " ").strip()
    return label.title() if label else "unknown ground"


def _nearby_names(position, key) -> list[str]:
    values = position.get(key) if isinstance(position, dict) else None
    if not isinstance(values, dict):
        return []

    names = []
    for obj in values.values():
        name = getattr(obj, "display_name", None) or getattr(
            obj, "name", str(obj)
        )
        name = str(name or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _state_line(game) -> str | None:
    state = game.current_state() if hasattr(game, "current_state") else None
    state_name = type(state).__name__ if state is not None else ""
    if state_name == "CombatState":
        return "Weapons are already drawn."
    if state_name == "DialogueState":
        return "A conversation hangs in the air."
    return None


def build_scene(game) -> str:
    """Builds a short, factual description of the player's current location."""
    if game is None:
        return ENGINE_FALLBACK

    player = getattr(game, "player", None)
    if player is None:
        return ENGINE_FALLBACK

    map_name = str(getattr(player, "current_map", "") or "")
    definition = scene_catalogue().get(map_name, {})
    if not isinstance(definition, dict):
        definition = {}

    description = str(definition.get("description", "") or "").strip()
    if not description:
        location = definition.get("title") or _location_label(map_name)
        description = f"You stand in {location}."

    parts = [description]

    position = (
        game.get_player_position()
        if hasattr(game, "get_player_position")
        else None
    )
    npcs = _nearby_names(position, "nearby_npcs")
    objects = _nearby_names(position, "nearby_items")
    if npcs:
        parts.append("Nearby: " + ", ".join(npcs) + ".")
    if objects:
        parts.append("Within reach: " + ", ".join(objects) + ".")

    state_line = _state_line(game)
    if state_line:
        parts.append(state_line)

    cleared = {
        str(area)
        for area in (getattr(player, "cleared_areas", []) or [])
        if isinstance(area, str)
    }
    if map_name in cleared:
        parts.append("The area is quiet now.")

    if bool(getattr(player, "stealthed", False)):
        parts.append("You keep to the shadows.")

    return " ".join(parts)


def generate_scene(game, narrator=None, memory=None) -> dict:
    """Returns ``{"description": str, "source": "engine"|"ai"}``.

    The deterministic scene is always available. When a narrator is configured,
    it is asked to add atmosphere around the same facts; any failure or refusal
    keeps the engine text. Scene descriptions never change game state.
    """
    try:
        engine_scene = build_scene(game)
    except Exception as exc:  # a scene description must never break the session
        logger.warning("Scene generation failed: %s", exc)
        engine_scene = ENGINE_FALLBACK

    if narrator is None or not hasattr(narrator, "describe"):
        return {"description": engine_scene, "source": "engine"}

    try:
        context = build_context(game, memory=memory)
        prose = narrator.describe(engine_scene, context)
    except Exception as exc:
        logger.warning("AI scene description failed: %s", exc)
        prose = None

    prose = prose.strip() if isinstance(prose, str) else ""
    if prose:
        return {"description": prose, "source": "ai"}

    return {"description": engine_scene, "source": "engine"}
