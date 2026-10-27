"""Recruited ally stances and party summaries."""

from __future__ import annotations

from core.factions import reputation_value

STANCES = {
    "attack": "Attack",
    "guard": "Guard",
    "support": "Support",
}

ALLY_FACTIONS = {
    "Violet": "violet_watch",
}


def normalize_stance(stance) -> str:
    value = str(stance or "").strip().casefold()
    return value if value in STANCES else "attack"


def ally_stance(player, ally_name) -> str:
    stances = getattr(player, "ally_stances", None)
    if not isinstance(stances, dict):
        return "attack"
    return normalize_stance(stances.get(str(ally_name), "attack"))


def set_ally_stance(player, ally_name, stance, game=None) -> bool:
    name = str(ally_name or "").strip()
    if name not in (getattr(player, "allies", []) or []):
        if game:
            game.io.show_message(f"{name or 'That ally'} is not in your party.")
        return False

    normalized = str(stance or "").strip().casefold()
    if normalized not in STANCES:
        if game:
            game.io.show_message(
                "Choose attack, guard or support as the ally stance."
            )
        return False

    if not isinstance(getattr(player, "ally_stances", None), dict):
        player.ally_stances = {}
    player.ally_stances[name] = normalized
    if game:
        game.io.show_message(
            f"{name} takes the {STANCES[normalized].lower()} stance."
        )
    return True


def party_entries(player) -> list[dict]:
    from entities.npc import NPC

    entries = []
    for name in getattr(player, "allies", []) or []:
        if not isinstance(name, str):
            continue
        npc = NPC(name)
        entries.append(
            {
                "name": name,
                "hp": getattr(npc, "hp", 0),
                "hp_max": getattr(npc, "hp_max", 0),
                "stance": ally_stance(player, name),
                "stance_label": STANCES[ally_stance(player, name)],
                "faction": ALLY_FACTIONS.get(name),
                "description": getattr(npc, "description", ""),
            }
        )
    return entries


def support_heal_amount(player, ally_name) -> int:
    amount = 8
    if ALLY_FACTIONS.get(str(ally_name)) == "violet_watch":
        amount += min(6, max(0, reputation_value(player, "violet_watch") // 10))
    return amount
