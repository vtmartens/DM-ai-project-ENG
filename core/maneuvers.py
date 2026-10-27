"""Data-driven combat maneuvers shared by the engine and API."""

from __future__ import annotations

from util.data_manager import get_data_manager


def maneuver_catalogue() -> dict:
    data = get_data_manager().load_data("combat", "maneuvers.json")
    return data if isinstance(data, dict) else {}


def maneuver_definitions() -> list[dict]:
    """Returns well-formed maneuver definitions in catalogue order."""
    return [
        dict(maneuver)
        for maneuver in maneuver_catalogue().values()
        if isinstance(maneuver, dict) and maneuver.get("id")
    ]


def maneuver_ids() -> list[str]:
    return [str(maneuver["id"]) for maneuver in maneuver_definitions()]


def get_maneuver(maneuver_id) -> dict | None:
    wanted = str(maneuver_id or "").casefold()
    for maneuver in maneuver_definitions():
        if str(maneuver.get("id", "")).casefold() == wanted:
            return maneuver
        if str(maneuver.get("name", "")).casefold() == wanted:
            return maneuver
    return None


def maneuver_actions() -> list[str]:
    """Labels suitable for API quick actions and command input."""
    return [
        str(maneuver.get("id") or maneuver.get("name"))
        for maneuver in maneuver_definitions()
    ]
