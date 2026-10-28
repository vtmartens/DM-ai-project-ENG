"""Character backgrounds, proficiencies and dialogue gating."""

import pytest

from core.backgrounds import (
    background_catalogue,
    background_entries,
    player_background,
)
from core.game import Game
from core.item_catalogue import item_definition
from entities.npc import NPC
from entities.player import Player
from states.dialogue import DialogueState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io, background="wanderer", char_class="fighter"):
    player = Player("Background Tester", char_class, background=background)
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    return player, game


def test_background_catalogue_is_well_formed():
    from entities.entity import ASSOCIATED_SKILLS

    catalogue = background_catalogue()
    assert {"wanderer", "acolyte", "criminal", "soldier", "sage", "outlander"} <= set(
        catalogue
    )

    for background_id, definition in catalogue.items():
        assert definition.get("name"), background_id
        assert definition.get("description"), background_id
        for skill in definition.get("skills", []) or []:
            assert skill in ASSOCIATED_SKILLS, (background_id, skill)
        for item_name in definition.get("starting_items", []) or []:
            assert item_definition(item_name) is not None, (
                background_id,
                item_name,
            )


def test_default_background_and_player_persistence(recording_io):
    default, _ = _game(recording_io)
    assert default.background == "wanderer"
    assert default.skill_proficiencies.get("athletics") is True
    assert default.skill_proficiencies.get("religion") is None

    acolyte, _ = _game(recording_io, background="acolyte")
    restored = Player.from_dict(acolyte.to_dict())
    assert restored.background == "acolyte"
    assert restored.skill_proficiencies.get("religion") is True
    assert restored.skill_proficiencies.get("insight") is True

    legacy = Player.from_dict({"name": "Legacy", "char_class": "fighter"})
    assert legacy.background == "wanderer"


def test_background_items_and_skill_bonus(recording_io):
    player, game = _game(recording_io, background="acolyte")

    assert "Healing Potion" in [item.name for item in player.inventory]
    assert player.ability_modifier("religion", game) == (
        player.modifier_intelligence + player.proficiency_bonus
    )
    assert player.ability_modifier("insight", game) == (
        player.modifier_wisdom + player.proficiency_bonus
    )


def test_background_overlaps_with_class_proficiencies(recording_io):
    soldier, _ = _game(recording_io, background="soldier")

    assert soldier.skill_proficiencies.get("athletics") is True
    assert soldier.skill_proficiencies.get("intimidation") is True


def test_criminal_and_sage_dialogue_options_are_gated(recording_io):
    criminal, game = _game(recording_io, background="criminal")
    dialogue = DialogueState(NPC("Mirt"))
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "I know a fence when I see one." in options
    assert "Those rune-marks are older than the city." not in options

    sage, game = _game(recording_io, background="sage")
    dialogue = DialogueState(NPC("Mirt"))
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "Those rune-marks are older than the city." in options
    assert "I know a fence when I see one." not in options


def test_outlander_and_acolyte_dialogue_options_are_gated(recording_io):
    outlander, game = _game(recording_io, background="outlander")
    dialogue = DialogueState(NPC("Violet"))
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "I have walked the trade road before." in options
    assert "I have tended the sick before." not in options

    acolyte, game = _game(recording_io, background="acolyte")
    dialogue = DialogueState(NPC("Violet"))
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "I have tended the sick before." in options
    assert "I have walked the trade road before." not in options


def test_start_endpoint_accepts_and_reports_background(client):
    result = client.post(
        "/start",
        json={
            "name": "Sage Run",
            "char_class": "fighter",
            "background": "sage",
        },
    ).get_json()

    assert result["player"]["background"] == "sage"
    assert result["player"]["background_name"] == "Sage"
    assert result["state"]["background"] == "sage"
    assert result["state"]["background_name"] == "Sage"

    import server

    session = server.active_sessions[result["session_id"]]
    assert session.game.player.background == "sage"


def test_start_rejects_unknown_background(client):
    response = client.post(
        "/start",
        json={
            "name": "Bad Background",
            "char_class": "fighter",
            "background": "pirate",
        },
    )

    assert response.status_code == 400


def test_backgrounds_endpoint_lists_the_options(client):
    data = client.get("/backgrounds").get_json()

    ids = {entry["id"] for entry in data["backgrounds"]}
    assert {"wanderer", "acolyte", "criminal", "soldier", "sage", "outlander"} <= ids
    assert data["default"] == "wanderer"


def test_player_background_reports_a_friendly_name(recording_io):
    player, _ = _game(recording_io, background="outlander")
    background = player_background(player)

    assert background["id"] == "outlander"
    assert background["name"] == "Outlander"
