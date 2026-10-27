"""Deterministic session recaps and their optional AI phrasing."""

import pytest

from ai.recap import build_recap, generate_recap
from core.game import Game
from core.quests import start_quest
from entities.player import Player


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io):
    player = Player("Aria", "wizard")
    player.hp = 5
    player.hp_max = 6
    player.mana = 10
    player.mana_max = 20
    player.gold = 42
    player.defeats = 1
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("market")
    player.set_position("market", 5, 5)
    return player, game


def test_build_recap_summarizes_state_quests_conditions_and_recent_events(
    recording_io,
):
    player, game = _game(recording_io)
    start_quest(player, "shadows_of_the_market", game)
    player.conditions["poison"] = {"damage": 2, "turns": 2}
    player.completed_quests = [{"id": "old_quest", "title": "Old Quest"}]
    memory = [
        "You accepted Violet's quest.",
        "Quest started: Shadows in the Market",
        "You entered the warehouse.",
    ]

    recap = build_recap(game, memory=memory)

    assert "Aria the Wizard" in recap
    assert "level 1" in recap
    assert "in the Market" in recap
    assert "5/6 HP" in recap
    assert "10/20 mana" in recap
    assert "42 gold" in recap
    assert "Active quest: Shadows in the Market" in recap
    assert "Defeat Vargas" in recap
    assert "(in progress)" in recap
    assert "Completed quests: 1." in recap
    assert "Affected by: Poisoned." in recap
    assert "defeated 1 time" in recap
    assert "Recently:" in recap
    assert "You entered the warehouse." in recap


def test_generate_recap_uses_the_narrator_and_falls_back_on_failure(recording_io):
    player, game = _game(recording_io)

    class RecapNarrator:
        def __init__(self):
            self.calls = []

        def recap(self, summary, context):
            self.calls.append((summary, context))
            return "Previously, Aria gathered her strength."

    narrator = RecapNarrator()
    result = generate_recap(game, narrator=narrator, memory=["You rested."])

    assert result == {
        "recap": "Previously, Aria gathered her strength.",
        "source": "ai",
    }
    assert "Aria the Wizard" in narrator.calls[0][0]
    assert narrator.calls[0][1]["player"]["name"] == "Aria"

    class ExplodingNarrator:
        def recap(self, summary, context):
            raise RuntimeError("model unavailable")

    fallback = generate_recap(game, narrator=ExplodingNarrator(), memory=[])
    assert fallback["source"] == "engine"
    assert "Nothing notable has happened yet." in fallback["recap"]


def test_build_recap_without_recent_events_has_a_fallback_sentence(recording_io):
    _, game = _game(recording_io)

    recap = build_recap(game, memory=[], events=[])

    assert "Nothing notable has happened yet." in recap


def test_recap_endpoint_returns_the_engine_summary_and_logs_it(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Recap Tester", "char_class": "fighter"}
    ).get_json()["session_id"]
    session = server.active_sessions[session_id]
    player = session.game.player
    before = (player.hp, player.gold, player.current_map, list(player.active_quests))

    result = client.post(
        "/recap", json={"session_id": session_id}
    ).get_json()

    assert result["session_id"] == session_id
    assert result["source"] == "engine"
    assert "Recap Tester the Fighter" in result["recap"]
    assert "Tavern" in result["recap"]
    assert (player.hp, player.gold, player.current_map, list(player.active_quests)) == before

    events = client.get(
        "/log", query_string={"session_id": session_id, "max": 200}
    ).get_json()["events"]
    assert any(
        event["type"] == "recap" and event["text"] == result["recap"]
        for event in events
    )


def test_recap_requires_a_session(client):
    assert client.post("/recap", json={}).status_code == 400
    assert (
        client.post("/recap", json={"session_id": "no-such-session"}).status_code
        == 404
    )
