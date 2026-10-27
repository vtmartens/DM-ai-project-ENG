"""Deterministic scene descriptions and their optional AI colour."""

from pathlib import Path

import pytest

from ai.scene import build_scene, generate_scene, scene_catalogue
from core.game import Game
from entities.player import Player

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io):
    player = Player("Scene Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    player.set_position("tavern", 6, 5)
    return player, game


def test_scene_catalogue_covers_every_map():
    map_names = {
        path.stem for path in (ROOT / "data" / "maps").glob("*.json")
    }

    assert map_names <= set(scene_catalogue())


def test_build_scene_describes_the_location_and_nearby_npcs(recording_io):
    _, game = _game(recording_io)

    scene = build_scene(game)

    assert "Yawning Portal" in scene
    assert "Durnan" in scene
    assert scene == build_scene(game)


def test_build_scene_mentions_cleared_areas_and_stealth(recording_io):
    player, game = _game(recording_io)
    game.set_initial_map("underroad")
    player.set_position("underroad", 2, 7)
    player.cleared_areas = ["underroad"]
    player.stealthed = True

    scene = build_scene(game)

    assert "smugglers' route" in scene
    assert "quiet now" in scene
    assert "shadows" in scene


def test_build_scene_without_a_player_is_a_beginner_prompt():
    assert build_scene(None) == "Choose a class and begin your adventure."


def test_ai_scene_uses_the_narrator_and_context(recording_io):
    _, game = _game(recording_io)

    class FakeSceneNarrator:
        def __init__(self):
            self.calls = []

        def describe(self, scene, context):
            self.calls.append((scene, context))
            return f"The Dungeon Master paints the scene: {scene}"

    narrator = FakeSceneNarrator()

    result = generate_scene(
        game,
        narrator=narrator,
        memory=["Earlier: the tavern door creaked open."],
    )

    assert result["source"] == "ai"
    assert result["description"].startswith("The Dungeon Master paints the scene:")
    scene, context = narrator.calls[0]
    assert "Yawning Portal" in scene
    assert context["map"] == "tavern"
    assert context["recent"] == ["Earlier: the tavern door creaked open."]


def test_ai_scene_falls_back_when_the_narrator_fails(recording_io):
    _, game = _game(recording_io)

    class BrokenNarrator:
        def describe(self, scene, context):
            raise RuntimeError("network down")

    result = generate_scene(game, narrator=BrokenNarrator())

    assert result["source"] == "engine"
    assert "Yawning Portal" in result["description"]


def test_ai_scene_falls_back_when_the_narrator_declines(recording_io):
    _, game = _game(recording_io)

    class SilentNarrator:
        def describe(self, scene, context):
            return None

    result = generate_scene(game, narrator=SilentNarrator())

    assert result["source"] == "engine"


def test_a_narrator_without_describe_keeps_the_engine_scene(recording_io):
    _, game = _game(recording_io)

    result = generate_scene(game, narrator=object())

    assert result["source"] == "engine"
    assert "Yawning Portal" in result["description"]


def test_generate_scene_does_not_change_the_player(recording_io):
    player, game = _game(recording_io)
    before = player.to_dict()

    generate_scene(game)

    assert player.to_dict() == before


def test_describe_endpoint_returns_the_engine_scene_and_logs_it(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Scene API", "char_class": "fighter"}
    ).get_json()["session_id"]
    session = server.active_sessions[session_id]
    player = session.game.player
    before = (player.hp, player.gold, player.current_map, list(player.active_quests))

    result = client.post(
        "/describe", json={"session_id": session_id}
    ).get_json()

    assert result["session_id"] == session_id
    assert result["source"] == "engine"
    assert "Yawning Portal" in result["description"]
    assert (player.hp, player.gold, player.current_map, list(player.active_quests)) == before

    events = client.get(
        "/log", query_string={"session_id": session_id, "max": 200}
    ).get_json()["events"]
    assert any(
        event["type"] == "description"
        and event["text"] == result["description"]
        for event in events
    )


def test_describe_requires_a_session(client):
    assert client.post("/describe", json={}).status_code == 400
    assert (
        client.post(
            "/describe", json={"session_id": "no-such-session"}
        ).status_code
        == 404
    )
