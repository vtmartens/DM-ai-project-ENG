"""Recruited ally stances and party summaries."""

from __future__ import annotations

from core.factions import reputation_tier, reputation_value, tier_label
from util.data_manager import get_data_manager

STANCES = {
    "attack": "Attack",
    "guard": "Guard",
    "support": "Support",
}

ALLY_FACTIONS = {
    "Violet": "violet_watch",
}


def ally_ability_catalogue() -> dict:
    data = get_data_manager().load_data("party", "ally_abilities.json")
    return data if isinstance(data, dict) else {}


def load_ally_abilities(ability_ids) -> list[dict]:
    catalogue = ally_ability_catalogue()
    abilities = []
    for ability_id in ability_ids or []:
        definition = catalogue.get(str(ability_id))
        if isinstance(definition, dict):
            ability = dict(definition)
            ability.setdefault("id", ability_id)
            abilities.append(ability)
    return abilities


def get_ally_ability(ability_ids, identifier) -> dict | None:
    wanted = str(identifier or "").strip().casefold()
    for ability in load_ally_abilities(ability_ids):
        if wanted in {
            str(ability.get("id", "")).casefold(),
            str(ability.get("name", "")).casefold(),
        }:
            return ability
    return None


def normalize_stance(stance) -> str:
    value = str(stance or "").strip().casefold()
    return value if value in STANCES else "attack"


def ally_faction(ally_name):
    return ALLY_FACTIONS.get(str(ally_name))


def ally_loyalty(player, ally_name) -> str:
    faction = ally_faction(ally_name)
    if faction is None:
        return "neutral"
    return reputation_tier(reputation_value(player, faction))


def ally_loyalty_label(player, ally_name) -> str:
    return tier_label(ally_loyalty(player, ally_name))


def ally_will_act(player, ally_name) -> bool:
    return ally_loyalty(player, ally_name) != "hostile"


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
        stance = ally_stance(player, name)
        loyalty = ally_loyalty(player, name)
        entries.append(
            {
                "name": name,
                "hp": getattr(npc, "hp", 0),
                "hp_max": getattr(npc, "hp_max", 0),
                "stance": stance,
                "stance_label": STANCES[stance],
                "loyalty": loyalty,
                "loyalty_label": tier_label(loyalty),
                "will_act": loyalty != "hostile",
                "faction": ally_faction(name),
                "description": getattr(npc, "description", ""),
                "abilities": load_ally_abilities(
                    getattr(npc, "ally_ability_ids", [])
                ),
            }
        )
    return entries


def support_heal_amount(player, ally_name, base=8) -> int:
    amount = max(1, int(base or 8))
    if ally_faction(str(ally_name)) == "violet_watch":
        amount += min(6, max(0, reputation_value(player, "violet_watch") // 10))
    return amount
