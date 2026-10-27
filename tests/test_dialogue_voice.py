"""Optional AI colour for deterministic NPC dialogue lines."""

import pytest

from ai.dialogue import generate_dialogue_voice
from core.game import Game
from entities.npc import NPC
from entities.player import Player
from states.dialogue import DialogueState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io):
    player = Player("Voice Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    game.push_state(DialogueState(NPC("Durnan")))
    return player, game


def test_engine_fallback_is_the_exact_dialogue_line(recording_io):
    player, game = _game(recording_io)
    before = player.to_dict()

    result = generate_dialogue_voice(game)

    assert result["source"] == "engine"
    assert result["npc"] == "Durnan"
    assert result["node"] == "start"
    assert "Welcome to the Yawning Portal." in result["voice"]
    assert player.to_dict() == before
    assert game.current_state().current_state == "start"


def test_ai_voice_receives_line_and_dialogue_context(recording_io):
    _, game = _game(recording_io)

    class FakeDialogueNarrator:
        def __init__(self):
            self.calls = []

        def dialogue(self, line, context):
            self.calls.append((line, context))
            return "Durnan wipes the bar and leans in, voice low."

    narrator = FakeDialogueNarrator()
    result = generate_dialogue_voice(
        game,
        narrator=narrator,
        memory=["Earlier: the tavern door opened."],
    )

    assert result["source"] == "ai"
    assert result["voice"].startswith("Durnan wipes the bar")
    line, context = narrator.calls[0]
    assert "Welcome to the Yawning Portal." in line
    assert context["dialogue"]["npc"] == "Durnan"
    assert context["dialogue"]["profession"] == "Innkeeper"
    assert context["dialogue"]["node"] == "start"
    assert context["recent"] == ["Earlier: the tavern door opened."]


def test_ai_voice_falls_back_on_failure_or_decline(recording_io):
    _, game = _game(recording_io)

    class BrokenNarrator:
        def dialogue(self, line, context):
            raise RuntimeError("model unavailable")

    class SilentNarrator:
        def dialogue(self, line, context):
            return None

    broken = generate_dialogue_voice(game, narrator=BrokenNarrator())
    silent = generate_dialogue_voice(game, narrator=SilentNarrator())

    assert broken["source"] == "engine"
    assert silent["source"] == "engine"
    assert "Welcome to the Yawning Portal." in broken["voice"]
    assert "Welcome to the Yawning Portal." in silent["voice"]


def test_a_narrator_without_dialogue_keeps_the_engine_line(recording_io):
    _, game = _game(recording_io)

    result = generate_dialogue_voice(game, narrator=object())

    assert result["source"] == "engine"
    assert "Welcome to the Yawning Portal." in result["voice"]


def test_no_active_dialogue_returns_an_empty_engine_result(recording_io):
    player = Player("No Dialogue", "fighter")
    game = Game(player, None, recording_io, temporary=True)

    result = generate_dialogue_voice(game)

    assert result == {
        "voice": "",
        "source": "engine",
        "npc": None,
        "node": None,
    }


def test_dialogue_voice_endpoint_uses_the_active_node(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Voice API", "char_class": "fighter"}
    ).get_json()["session_id"]
    session = server.active_sessions[session_id]
    session.game.change_state(DialogueState(NPC("Durnan")))

    result = client.post(
        "/dialogue/voice", json={"session_id": session_id}
    ).get_json()

    assert result["session_id"] == session_id
    assert result["source"] == "engine"
    assert result["npc"] == "Durnan"
    assert "Welcome to the Yawning Portal." in result["voice"]
    assert session.game.current_state().current_state == "start"


def test_dialogue_voice_endpoint_is_refused_outside_dialogue(client):
    session_id = client.post(
        "/start", json={"name": "No Voice", "char_class": "fighter"}
    ).get_json()["session_id"]

    response = client.post(
        "/dialogue/voice", json={"session_id": session_id}
    )

    assert response.status_code == 409
