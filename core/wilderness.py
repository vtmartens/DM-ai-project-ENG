"""Road travel and wandering encounters."""

from __future__ import annotations

import random

from core.encounters import build_encounter, encounter_catalogue

ROAD_MAP = "road"
ROAD_ENCOUNTER_CHANCE = 0.30
ROAD_ENCOUNTER_COOLDOWN = 3
ROAD_GRACE_STEPS = 2
ROAD_ENCOUNTER_IDS = (
    "goblin_scouts",
    "wolf_pack",
    "orc_patrol",
    "goblin_warband",
    "underroad_enforcers",
    "orc_raiders",
)

ROAD_ENCOUNTER_MIN_LEVEL = {
    "orc_patrol": 3,
    "goblin_warband": 3,
    "underroad_enforcers": 4,
    "orc_raiders": 5,
}


def _candidates(player=None) -> list[str]:
    catalogue = encounter_catalogue()
    level = int(getattr(player, "level", 1) or 1)
    return [
        entry
        for entry in ROAD_ENCOUNTER_IDS
        if entry in catalogue
        and level >= int(ROAD_ENCOUNTER_MIN_LEVEL.get(entry, 1) or 1)
    ]


def should_trigger_encounter(rng=None) -> bool:
    """Rolls whether a road step attracts an encounter."""
    roll = (rng or random.random)()
    return roll < ROAD_ENCOUNTER_CHANCE


def choose_road_encounter(encounter_id=None, player=None, chooser=None):
    """Builds a road encounter, marking it for loot on victory."""
    candidates = _candidates(player)
    if encounter_id is not None:
        candidates = [encounter_id] if encounter_id in candidates else []
    if not candidates:
        return None

    selected = encounter_id or (chooser or random.choice)(candidates)
    encounter = build_encounter(selected)
    if encounter is None:
        return None

    encounter["loot"] = True
    encounter["source"] = ROAD_MAP
    return encounter


def start_road_encounter(game):
    """Starts a road encounter on top of the current MapState."""
    if game is None or getattr(game, "player", None) is None:
        return None

    encounter = choose_road_encounter(player=game.player)
    if encounter is None:
        return None

    from core.quests import build_ally_party
    from states.combat import CombatState

    game.io.show_message(
        f"\nThe road is not safe. {encounter['title']}: "
        f"{encounter['description']}"
    )
    game.push_state(
        CombatState(
            enemies=encounter["enemies"],
            encounter=encounter,
            allies=build_ally_party(game.player),
        )
    )
    return encounter
