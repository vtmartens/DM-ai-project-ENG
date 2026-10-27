"""Rune Shard recipes, the Sanctum Forge and their API."""

import pytest

from core.crafting import (
    add_rune_shards,
    craft_recipe,
    recipe_catalogue,
    recipe_entries,
    rune_shards,
)
from core.game import Game
from core.item_catalogue import item_definition
from entities.player import Player
from states.forge import ForgeState
from states.sanctum import SanctumState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io, shards=0, gold=0):
    player = Player("Forge Tester", "fighter")
    player.rune_shards = shards
    player.gold = gold
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def test_recipe_definitions_reference_real_items():
    recipes = recipe_catalogue()

    assert {"rune_draught", "rune_forged_blade", "rune_ward_plate"} <= set(
        recipes
    )
    for recipe_id, recipe in recipes.items():
        assert recipe.get("id") == recipe_id
        assert recipe.get("name")
        assert recipe.get("description")
        assert int(recipe.get("shards", 0)) >= 1
        assert int(recipe.get("gold", 0)) >= 0
        assert item_definition(recipe.get("result")) is not None


def test_crafting_consumes_shards_and_gold(recording_io):
    player, game = _game(recording_io, shards=3, gold=50)

    result = craft_recipe(player, "rune_draught", game)

    assert result["success"] is True
    assert rune_shards(player) == 1
    assert player.gold == 30
    assert "Rune Draught" in [item.name for item in player.inventory]
    assert "You forge Rune Draught" in recording_io.text


def test_unique_recipe_can_only_be_forged_once(recording_io):
    player, game = _game(recording_io, shards=20, gold=500)

    assert craft_recipe(player, "rune_forged_blade", game)["success"] is True
    assert craft_recipe(player, "rune_forged_blade", game)["success"] is False

    assert [item.name for item in player.inventory].count(
        "Rune-Forged Blade"
    ) == 1
    assert "crafted:rune_forged_blade" in player.claimed_rewards
    assert rune_shards(player) == 10


def test_crafting_reports_missing_resources(recording_io):
    player, game = _game(recording_io, shards=1, gold=5)

    result = craft_recipe(player, "rune_ward_plate", game)

    assert result["success"] is False
    assert "Rune Shards" in result["message"]

    entries = {entry["id"]: entry for entry in recipe_entries(player)}
    assert entries["rune_ward_plate"]["can_craft"] is False
    assert entries["rune_ward_plate"]["reasons"]


def test_add_rune_shards_is_persisted(recording_io):
    player, game = _game(recording_io)

    assert add_rune_shards(player, 4, game) == 4
    assert rune_shards(Player.from_dict(player.to_dict())) == 4
    assert "4 Rune Shards" in recording_io.text


def test_sanctum_opens_the_forge_after_clearing(recording_io):
    player = Player("Forge Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("sanctum")
    state = SanctumState(game)
    game.push_state(state)

    assert state._enter_forge(game) is False

    player.cleared_areas = ["sanctum"]
    assert state._enter_forge(game) is True
    assert isinstance(game.current_state(), ForgeState)


def test_forge_api_lists_and_crafts(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Forge API", "char_class": "fighter"}
    ).get_json()["session_id"]
    session = server.active_sessions[session_id]
    session.game.player.rune_shards = 5
    session.game.player.gold = 50
    session.game.change_state(ForgeState(session.game))

    listing = client.get(
        "/forge", query_string={"session_id": session_id}
    ).get_json()
    assert listing["shards"] == 5
    assert any(recipe["id"] == "rune_draught" for recipe in listing["recipes"])

    crafted = client.post(
        "/forge/craft",
        json={"session_id": session_id, "recipe_id": "rune_draught"},
    ).get_json()

    assert crafted["crafted"] is True
    assert crafted["forge"]["shards"] == 3
    assert crafted["state"]["rune_shards"] == 3
    assert any(
        message["text"].startswith("You forge Rune Draught")
        for message in crafted["output"]
    )


def test_forge_api_is_refused_outside_the_forge(client):
    session_id = client.post(
        "/start", json={"name": "Not Forge", "char_class": "fighter"}
    ).get_json()["session_id"]

    response = client.get(
        "/forge", query_string={"session_id": session_id}
    )

    assert response.status_code == 409
