"""Matching keys to the locks they open."""

from __future__ import annotations


def _normalize(value) -> str:
    return (
        str(value or "")
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .casefold()
    )


def key_opens(key, object_name) -> bool:
    """True when ``key`` can open the named object."""
    if getattr(key, "type", None) != "key":
        return False

    effect = getattr(key, "effect", {}) or {}
    opens = effect.get("opens", [])
    if isinstance(opens, str):
        opens = [opens]

    wanted = _normalize(object_name)
    for target in opens:
        target_name = _normalize(target)
        if target_name == "*":
            return True
        if target_name and (
            target_name == wanted
            or target_name in wanted
            or wanted in target_name
        ):
            return True
    return False


def find_matching_key(player, object_name):
    """Returns the first inventory key that opens ``object_name``, or None."""
    for item in getattr(player, "inventory", []):
        if key_opens(item, object_name):
            return item
    return None
