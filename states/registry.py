"""Single source of truth for state classes restored from saves."""

from __future__ import annotations

import importlib

STATE_MODULES = {
    "TavernState": "states.tavern",
    "DialogueState": "states.dialogue",
    "CombatState": "states.combat",
    "MarketState": "states.market",
    "WaystationState": "states.waystation",
    "UnderroadState": "states.underroad",
    "SanctumState": "states.sanctum",
    "RuneheartGateState": "states.runeheart_gate",
    "RuneTrialsState": "states.rune_trials",
    "ForgeState": "states.forge",
    "BlackMarketState": "states.black_market",
    "BountyBoardState": "states.bounty_board",
    "RunePillarState": "states.rune_pillar",
    "RoadEventState": "states.road_event",
    "InventoryManagementState": "states.inventory_management",
    "AbilityCheckState": "states.ability_check",
    "MapState": "states.map_state",
    "MapSelectionState": "states.map_selection_state",
    "MenuState": "states.menu",
}


def load_state_class(state_name):
    """Imports and returns a registered state class, or None."""
    module_name = STATE_MODULES.get(str(state_name or ""))
    if module_name is None:
        return None
    module = importlib.import_module(module_name)
    return getattr(module, state_name, None)
