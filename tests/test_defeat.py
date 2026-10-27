"""Defeat recovery: return to the tavern, costs and restored resources."""

import pytest

from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState
from states.tavern import TavernState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io, char_class="wizard"):
    player = Player("Defeat Tester", char_class)
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("cellar")
    player.set_position("cellar", 5, 5)
    return player, game


def test_defeat_returns_to_the_tavern_and_restores_partial_resources(
    recording_io,
):
    player, game = _game(recording_io)
    player.hp = 0
    player.mana = 0
    player.gold = 100
    player.conditions = {
        "poison": {"damage": 2, "turns": 3},
        "burning": {"turns": 2},
    }
    player.active_quests = ["shadows_of_the_market"]
    combat = CombatState(enemy=Enemy("Brute", hp=20))
    game.push_state(combat)

    assert combat._check_end_combat(game) is True

    assert isinstance(game.current_state(), TavernState)
    assert len(game.state_stack) == 1
    assert player.hp == max(1, player.hp_max // 2)
    assert player.mana == player.mana_max // 2
    assert player.gold == 80
    assert player.conditions == {}
    assert player.active_quests == ["shadows_of_the_market"]
    assert player.current_map == "tavern"
    tavern_map = game.map_manager.get_map("tavern")
    assert (player.x, player.y) == tavern_map.player_start_position
    assert "wake in a bed" in recording_io.text
    assert "20 gold" in recording_io.text


def test_defeat_never_takes_more_gold_than_the_player_has(recording_io):
    player, game = _game(recording_io)
    player.hp = 0
    player.gold = 5
    combat = CombatState(enemy=Enemy("Brute", hp=20))
    game.push_state(combat)

    assert combat._check_end_combat(game) is True

    assert player.gold == 0
    assert "cost you 5 gold" in recording_io.text


def test_defeat_api_returns_the_session_to_the_tavern(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Fallen Tester", "char_class": "fighter"}
    ).get_json()["session_id"]
    client.post(
        "/command", json={"session_id": session_id, "command": "go to cellar"}
    )
    client.post(
        "/command",
        json={"session_id": session_id, "command": "attack the Specter"},
    )
    session = server.active_sessions[session_id]
    player = session.game.player
    player.hp = 0
    player.conditions["poison"] = {"damage": 2, "turns": 2}
    before_gold = player.gold

    result = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()

    assert result["state"]["state"] == "TavernState"
    assert result["state"]["position"]["map"] == "tavern"
    assert result["state"]["hp"] == max(1, player.hp_max // 2)
    assert result["state"]["stats"]["mana"] == player.mana_max // 2
    assert result["state"]["conditions"] == {}
    assert player.gold == before_gold - CombatState.DEFEAT_GOLD_LOSS
    assert player.current_map == "tavern"
    assert any(
        "wake in a bed" in message["text"] for message in result["output"]
    )
    assert not any(
        "Welcome Fallen Tester" in message["text"] for message in result["output"]
    )
