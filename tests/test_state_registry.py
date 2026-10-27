"""The shared state-class registry used by save/load restore paths."""

from states.base_state import BaseState
from states.registry import STATE_MODULES, load_state_class


def test_every_registered_state_imports_and_is_a_state():
    for state_name in STATE_MODULES:
        state_cls = load_state_class(state_name)
        assert state_cls is not None, state_name
        assert isinstance(state_cls, type), state_name
        assert issubclass(state_cls, BaseState), state_name


def test_new_states_are_registered():
    for state_name in (
        "TavernState",
        "MarketState",
        "WaystationState",
        "UnderroadState",
        "SanctumState",
        "RuneTrialsState",
        "BountyBoardState",
        "RunePillarState",
        "MapState",
        "MapSelectionState",
        "CombatState",
    ):
        assert state_name in STATE_MODULES


def test_base_state_from_dict_uses_the_registry():
    state = BaseState.from_dict({"type": "BountyBoardState"})

    assert type(state).__name__ == "BountyBoardState"
