"""Data-driven character backgrounds and skill proficiencies."""

from __future__ import annotations

from util.data_manager import get_data_manager

DEFAULT_BACKGROUND = "wanderer"


def background_catalogue() -> dict:
    data = get_data_manager().load_data(
        "backgrounds", "backgrounds.json"
    )
    return data if isinstance(data, dict) else {}


def background_definition(background_id) -> dict | None:
    key = str(background_id or "").strip().casefold()
    definition = background_catalogue().get(key)
    return definition if isinstance(definition, dict) else None


def player_background_id(player) -> str:
    key = str(
        getattr(player, "background", DEFAULT_BACKGROUND)
        or DEFAULT_BACKGROUND
    ).casefold()
    return key if background_definition(key) is not None else DEFAULT_BACKGROUND


def player_background(player) -> dict:
    key = player_background_id(player)
    definition = background_definition(key) or {}
    return {
        "id": key,
        "name": definition.get("name", key.title()),
        "description": definition.get("description", ""),
    }


def background_entries() -> list[dict]:
    entries = []
    for background_id, definition in background_catalogue().items():
        if not isinstance(definition, dict):
            continue
        entries.append(
            {
                "id": background_id,
                "name": definition.get("name", background_id.title()),
                "description": definition.get("description", ""),
                "skills": list(definition.get("skills", []) or []),
                "starting_items": list(
                    definition.get("starting_items", []) or []
                ),
                "default": background_id == DEFAULT_BACKGROUND,
            }
        )
    return entries


def background_skills(background_id) -> list[str]:
    definition = background_definition(background_id) or {}
    skills = definition.get("skills", [])
    return [
        str(skill).casefold()
        for skill in skills or []
        if isinstance(skill, str)
    ]


def background_starting_items(background_id) -> list[str]:
    definition = background_definition(background_id) or {}
    items = definition.get("starting_items", [])
    return [str(item) for item in items or [] if isinstance(item, str)]
