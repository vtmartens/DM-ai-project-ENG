"""The vault Rune Pillar and its Arcana challenge."""

import pytest

from core.game import Game
from entities.player import Player
from items.interactive_object import RunePillar
from states.map_state import MapState
from states.rune_pillar import RunePillarState
from world.map import Map


def _game(recording_io, near_pillar=True):
    player = Player("Rune Tester", "wizard")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("vault")
    if near_pillar:
        player.set_position("vault", 10, 6)
    else:
        player.set_position("vault", 2, 7)
    return player, game


def _pillar_game(recording_io):
    player, game = _game(recording_io)
    pillar = game.map_manager.get_map("vault").items[(10, 5)]
    state = RunePillarState(pillar, game)
    game.push_state(state)
    return player, game, state


def test_rune_pillar_loads_and_survives_map_round_trip(recording_io):
    _, game = _game(recording_io)
    vault = game.map_manager.get_map("vault")
    pillar = vault.items[(10, 5)]

    assert isinstance(pillar, RunePillar)
    assert pillar.type == "rune_pillar"

    restored = Map.from_dict(vault.to_dict())
    assert isinstance(restored.items[(10, 5)], RunePillar)


def test_adjacent_interaction_opens_the_pillar_state(recording_io):
    player, game = _game(recording_io)
    state = MapState()
    game.push_state(state)

    player.interact_with_adjacent_item(game.map_manager, game)

    assert isinstance(game.current_state(), RunePillarState)


def test_successful_arcana_check_grants_the_unique_reward_once(
    recording_io, monkeypatch
):
    player, game, state = _pillar_game(recording_io)
    monkeypatch.setattr(
        "states.rune_pillar.roll_d20", lambda *args, **kwargs: (20, [])
    )

    assert state._study(game) is True

    assert "Rune-Ward Amulet" in [item.name for item in player.inventory]
    assert "vault_rune_pillar" in player.claimed_rewards
    assert "The runes unfold into a pattern" in recording_io.text

    assert state._study(game) is False
    assert [item.name for item in player.inventory].count(
        "Rune-Ward Amulet"
    ) == 1


def test_failed_arcana_check_costs_health_and_can_be_retried(
    recording_io, monkeypatch
):
    player, game, state = _pillar_game(recording_io)
    before = player.hp
    monkeypatch.setattr(
        "states.rune_pillar.roll_d20", lambda *args, **kwargs: (1, [])
    )

    assert state._study(game) is False
    assert player.hp == before - 2
    assert "Rune-Ward Amulet" not in [
        item.name for item in player.inventory
    ]
    assert "sear your mind" in recording_io.text

    monkeypatch.setattr(
        "states.rune_pillar.roll_d20", lambda *args, **kwargs: (20, [])
    )
    assert state._study(game) is True
    assert "Rune-Ward Amulet" in [item.name for item in player.inventory]


def test_guidance_is_consumed_by_the_arcana_check(recording_io, monkeypatch):
    player, game, state = _pillar_game(recording_io)
    player.conditions["guidance"] = {"bonus": 2}
    monkeypatch.setattr(
        "states.rune_pillar.roll_d20", lambda *args, **kwargs: (10, [])
    )

    assert state._study(game) is True
    assert "guidance" not in player.conditions
    assert "Guidance adds 2 to the check." in recording_io.text
    assert "Arcana check:" in recording_io.text
