"""Context-aware landmark summaries and API."""

import pytest

from core.game import Game
from core.game_state import GameState
from entities.player import Player
from states.forge import ForgeState
from states.rune_trials import RuneTrialsState
from states.sanctum import SanctumState
from states.tavern import TavernState
from states.underroad import UnderroadState
from states.waystation import WaystationState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _session(recording_io, state):
    player = Player("Landmark Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.push_state(state)
    session = GameState(player, None)
    session.game = game
    return player, game, session


def test_waystation_landmark_reports_status_and_actions(recording_io):
    _, _, session = _session(recording_io, WaystationState())
    player = session.game.player

    landmark = session.get_landmark_state()
    assert landmark["active"] is True
    assert landmark["id"] == "waystation"
    assert landmark["title"] == "The Broken Waystation"
    assert "occupied" in landmark["status"]
    assert "confront" in landmark["actions"]

    player.cleared_areas = ["waystation"]
    landmark = session.get_landmark_state()
    assert "cleared" in landmark["status"]
    assert "underroad" in landmark["actions"]


def test_underroad_sanctum_trials_and_forge_landmarks(recording_io):
    _, _, session = _session(recording_io, UnderroadState())
    underroad = session.get_landmark_state()
    assert underroad["id"] == "underroad"
    assert "smugglers active" in underroad["status"]
    assert "sanctum" not in underroad["actions"]
    session.game.player.cleared_areas = ["underroad"]
    assert "sanctum" in session.get_landmark_state()["actions"]

    _, _, session = _session(recording_io, SanctumState())
    sanctum = session.get_landmark_state()
    assert sanctum["id"] == "sanctum"
    assert "warded threshold" in sanctum["status"]
    assert "amulet" in sanctum["actions"]

    _, _, session = _session(recording_io, RuneTrialsState())
    trials = session.get_landmark_state()
    assert trials["id"] == "rune_trials"
    assert any("wave 1 / 5" in status for status in trials["status"])
    assert "begin" in trials["actions"]

    _, _, session = _session(recording_io, ForgeState())
    forge = session.get_landmark_state()
    assert forge["id"] == "forge"
    assert any("Rune Shards" in status for status in forge["status"])
    assert "rune_draught" in forge["actions"]


def test_non_landmark_state_is_inactive(recording_io):
    _, _, session = _session(recording_io, TavernState())

    assert session.get_landmark_state() == {
        "active": False,
        "state": "TavernState",
    }


def test_landmark_api_and_state_exposure(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Landmark API", "char_class": "fighter"}
    ).get_json()["session_id"]
    session = server.active_sessions[session_id]
    session.game.change_state(WaystationState(session.game))

    state = client.get(
        "/state", query_string={"session_id": session_id}
    ).get_json()
    landmark = client.get(
        "/landmark", query_string={"session_id": session_id}
    ).get_json()

    assert state["landmark"]["id"] == "waystation"
    assert landmark["active"] is True
    assert landmark["title"] == "The Broken Waystation"
    assert "strongbox" in landmark["actions"]


def test_landmark_requires_a_session(client):
    assert client.get("/landmark").status_code == 400
    assert (
        client.get("/landmark", query_string={"session_id": "missing"}).status_code
        == 404
    )
