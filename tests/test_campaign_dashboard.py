"""Campaign dashboard API and progression summary."""

import pytest

from core.game import Game
from core.game_state import GameState
from core.quests import start_quest
from entities.player import Player


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _session(recording_io):
    player = Player("Campaign Tester", "fighter")
    player.level = 10
    player.reputation = {"mirt_network": 12}
    player.rune_trials_best = 4
    player.rune_trials_runs = 1
    player.rune_shards = 6
    player.claimed_rewards = ["runeheart_mirt"]
    player.completed_quests = [
        {
            "id": "sanctum_chapter",
            "title": "The Sealed Sanctum",
            "status": "completed",
        },
        {
            "id": "runeheart_gate",
            "title": "The Runeheart Gate",
            "status": "completed",
        },
    ]
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    start_quest(player, "vargas_debt", game)
    session = GameState(player, None)
    session.game = game
    return player, session


def test_campaign_state_summarizes_story_and_endgame(recording_io):
    _, session = _session(recording_io)

    campaign = session.get_campaign_state()

    assert campaign["total_chapters"] == 8
    assert campaign["completed_chapters"] == 2
    assert campaign["campaign_complete"] is True
    assert campaign["runeheart_choice"] == "mirt"
    chapters = {chapter["id"]: chapter for chapter in campaign["chapters"]}
    assert chapters["vargas_debt"]["status"] == "active"
    assert chapters["sanctum_chapter"]["status"] == "completed"
    assert chapters["runeheart_gate"]["status"] == "completed"
    assert chapters["shadows_of_the_market"]["status"] == "not_started"
    assert campaign["rune_trials"] == {"best": 4, "runs": 1}
    assert campaign["rune_shards"] == 6
    assert campaign["cycle"] == 1
    assert campaign["capstone"] == {
        "name": "Last Stand",
        "unlocked": True,
    }
    assert campaign["reputation"]["shop_discount"] == 5
    assert campaign["landmark"]["state"] == "NoneState"


def test_campaign_is_exposed_in_state_and_api(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Campaign API", "char_class": "fighter"}
    ).get_json()["session_id"]
    session = server.active_sessions[session_id]
    session.game.player.rune_shards = 3

    state = client.get(
        "/state", query_string={"session_id": session_id}
    ).get_json()
    campaign = client.get(
        "/campaign", query_string={"session_id": session_id}
    ).get_json()

    assert state["campaign"]["total_chapters"] == 8
    assert campaign["chapters"][0]["status"] == "not_started"
    assert campaign["rune_shards"] == 3
    assert campaign["landmark"]["location"] == "tavern"


def test_campaign_requires_a_session(client):
    assert client.get("/campaign").status_code == 400
    assert (
        client.get("/campaign", query_string={"session_id": "missing"}).status_code
        == 404
    )
