"""Hidden traps, searches and disarming."""

import pytest

import core.checks
from core.game import Game
from core.game_state import GameState
from entities.player import Player
from items.interactive_object import Trap
from states.commands import handle_targeted_command, resolve_map_object
from states.map_state import MapState
from world.map import Map


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io, x=9, y=10):
    game = Game(
        Player("Trap Tester", "fighter"),
        None,
        recording_io,
        temporary=True,
    )
    game.set_initial_map("cellar")
    game.player.set_position("cellar", x, y)
    game.player.hp = 50
    game.player.hp_max = 50
    game.player.defense = 0
    return game


def _roll(monkeypatch, value):
    monkeypatch.setattr(
        core.checks,
        "roll_d20",
        lambda *args, **kwargs: (value, []),
    )


def test_hidden_objects_are_absent_from_the_map_and_nearby_list(recording_io):
    game = _game(recording_io)
    cellar = game.map_manager.get_map("cellar")
    chest = cellar.get_item_at(8, 10)

    assert cellar.object_is_hidden(chest)
    assert (8, 10) not in game.player.get_nearby_items(
        game.map_manager, 2
    )
    assert (8, 10) in game.player.get_nearby_items(
        game.map_manager, 2, include_hidden=True
    )
    assert resolve_map_object(game, "hidden chest") is None
    assert cellar.generate_ascii_representation((9, 10)).splitlines()[10][8] == "."


def test_search_reveals_a_hidden_chest(recording_io, monkeypatch):
    game = _game(recording_io)
    cellar = game.map_manager.get_map("cellar")
    chest = cellar.get_item_at(8, 10)
    _roll(monkeypatch, 20)

    MapState()._search_area(game)

    assert chest.hidden is False
    assert chest.detected is True
    assert "You discover Hidden Chest." in recording_io.text
    assert (8, 10) in game.player.get_nearby_items(game.map_manager, 2)
    assert cellar.generate_ascii_representation((9, 10)).splitlines()[10][8] == "C"
    assert "C" in {entry["token"] for entry in cellar.token_legend()}


def test_search_command_runs_from_the_map_menu(monkeypatch):
    player = Player("Trap Tester", "fighter")
    session = GameState(player, MapState())
    session.game.set_initial_map("cellar")
    player.set_position("cellar", 9, 10)
    chest = session.game.map_manager.get_map("cellar").get_item_at(8, 10)
    _roll(monkeypatch, 20)

    output = session.process_command("search")

    assert "Perception check" in output
    assert "You discover Hidden Chest." in output
    assert chest.hidden is False


def test_search_can_fail_and_leaves_the_object_hidden(recording_io, monkeypatch):
    game = _game(recording_io)
    cellar = game.map_manager.get_map("cellar")
    chest = cellar.get_item_at(8, 10)
    _roll(monkeypatch, 1)

    MapState()._search_area(game)

    assert cellar.object_is_hidden(chest)
    assert "find nothing hidden" in recording_io.text


def test_search_reveals_a_hidden_trap(recording_io, monkeypatch):
    game = _game(recording_io, 9, 5)
    cellar = game.map_manager.get_map("cellar")
    trap = cellar.get_item_at(10, 5)
    _roll(monkeypatch, 20)

    MapState()._search_area(game)

    assert trap.hidden is False
    assert trap.detected is True
    assert "You spot Floor Trap before it can trigger." in recording_io.text
    assert cellar.generate_ascii_representation((9, 5)).splitlines()[5][10] == "T"


def test_revealed_trap_can_be_disarmed_with_a_skill_check(
    recording_io, monkeypatch
):
    game = _game(recording_io, 9, 5)
    trap = game.map_manager.get_map("cellar").get_item_at(10, 5)
    trap.hidden = False
    trap.detected = True
    _roll(monkeypatch, 20)

    handled = handle_targeted_command(game, "disarm", "floor trap")

    assert handled is True
    assert trap.state == "deactivated"
    assert "You carefully disarm Floor Trap." in recording_io.text


def test_failed_disarm_triggers_the_trap(recording_io, monkeypatch):
    game = _game(recording_io, 9, 5)
    trap = game.map_manager.get_map("cellar").get_item_at(10, 5)
    trap.hidden = False
    trap.detected = True
    _roll(monkeypatch, 1)
    monkeypatch.setattr(
        Player, "saving_throw", lambda self, *args, **kwargs: False
    )

    assert trap.disarm(game.player, game) is False

    assert trap.state == "triggered"
    assert game.player.hp == 42
    assert "The trap springs!" in recording_io.text


def test_successful_save_avoids_trap_damage(recording_io, monkeypatch):
    game = _game(recording_io, 9, 5)
    trap = game.map_manager.get_map("cellar").get_item_at(10, 5)
    trap.hidden = False
    trap.detected = True
    monkeypatch.setattr(
        Player, "saving_throw", lambda self, *args, **kwargs: True
    )

    assert trap.trigger(game.player, game) is False

    assert trap.state == "triggered"
    assert game.player.hp == 50
    assert "You avoid the trap!" in recording_io.text


def test_a_triggered_trap_does_not_trigger_twice(recording_io):
    game = _game(recording_io, 9, 5)
    trap = game.map_manager.get_map("cellar").get_item_at(10, 5)
    trap.hidden = False
    trap.detected = True
    trap.state = "triggered"

    assert trap.trigger(game.player, game) is False
    assert game.player.hp == 50


def test_discovery_and_trap_state_survive_a_map_round_trip(recording_io):
    game = _game(recording_io, 9, 5)
    cellar = game.map_manager.get_map("cellar")
    trap = cellar.get_item_at(10, 5)
    trap.hidden = False
    trap.detected = True
    trap.state = "deactivated"

    restored = Map.from_dict(cellar.to_dict())
    restored_trap = restored.get_item_at(10, 5)

    assert isinstance(restored_trap, Trap)
    assert restored_trap.hidden is False
    assert restored_trap.detected is True
    assert restored_trap.state == "deactivated"
    assert restored_trap.disarm_dc == trap.disarm_dc
    assert restored_trap.trigger_on_failure is True


def test_map_quick_actions_include_search(client):
    session_id = client.post(
        "/start",
        json={"name": "Trap API", "char_class": "fighter"},
    ).get_json()["session_id"]
    client.post("/command", json={"session_id": session_id, "command": "9"})

    data = client.get(
        "/available_actions", query_string={"session_id": session_id}
    ).get_json()

    assert data["context"] == "MapState"
    assert {"search", "sneak"} <= set(data["actions"])
