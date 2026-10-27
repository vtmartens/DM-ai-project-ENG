"""Faction standing, discounts, quest rewards and dialogue gates."""

import pytest

from core.factions import (
    adjust_reputation,
    faction_catalogue,
    reputation_entries,
    reputation_tier,
    shop_discount,
)
from core.game import Game
from core.quests import complete_quest, start_quest
from core.shop import buy_item, shop_stock
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
    player = Player("Faction Tester", "fighter")
    player.gold = 0
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def test_faction_definitions_and_tiers_are_well_formed():
    factions = faction_catalogue()

    assert {"mirt_network", "violet_watch", "underroad_smugglers"} <= set(
        factions
    )
    for faction_id, definition in factions.items():
        assert definition.get("name"), faction_id
        assert definition.get("description"), faction_id
        for key in ("shop_discount", "quest_bonus"):
            table = definition.get(key, {})
            assert isinstance(table, dict), faction_id
            for value in table.values():
                assert isinstance(value, int) and value >= 0, faction_id

    assert reputation_tier(-10) == "hostile"
    assert reputation_tier(0) == "neutral"
    assert reputation_tier(10) == "friendly"
    assert reputation_tier(25) == "trusted"
    assert reputation_tier(40) == "allied"


def test_reputation_adjusts_and_survives_a_player_round_trip(recording_io):
    player, game = _game(recording_io)

    adjust_reputation(player, "mirt_network", 12, game)
    adjust_reputation(player, "mirt_network", -3, game)

    assert player.reputation["mirt_network"] == 9
    assert "Your standing with Mirt's Network improves (+12)." in (
        recording_io.text
    )
    assert "Your standing with Mirt's Network worsens (-3)." in (
        recording_io.text
    )

    restored = Player.from_dict(player.to_dict())
    assert restored.reputation["mirt_network"] == 9


def test_mirt_reputation_applies_a_shop_discount(recording_io):
    player, game = _game(recording_io)
    player.reputation["mirt_network"] = 10
    player.gold = 100

    assert shop_discount(player) == 5

    stock = shop_stock()
    base = next(entry for entry in stock if entry["name"] == "Chainmail")
    discounted = next(
        entry
        for entry in shop_stock(player)
        if entry["name"] == "Chainmail"
    )
    assert base["price"] == 45
    assert discounted["price"] == 43
    assert discounted["reputation_discount"] == 5

    result = buy_item(player, "Chainmail", game)
    assert result["success"] is True
    assert result["price"] == 43
    assert player.gold == 57


def test_reputation_grants_a_quest_gold_bonus(recording_io):
    player, game = _game(recording_io)
    player.reputation["mirt_network"] = 10
    assert start_quest(player, "vargas_debt", game) is True

    assert complete_quest(player, "vargas_debt", game) is True

    assert player.gold == 55
    assert player.reputation["mirt_network"] == 15
    assert "Faction bonus: +5 gold." in recording_io.text


def test_reputation_gates_mirt_and_violet_dialogue(recording_io):
    player, game = _game(recording_io)

    mirt = DialogueState(NPC("Mirt"))
    violet = DialogueState(NPC("Violet"))

    assert "Any work for a trusted friend?" not in [
        text for text, _ in mirt.visible_options(game)
    ]
    assert "The Watch could use someone like you." not in [
        text for text, _ in violet.visible_options(game)
    ]

    player.reputation["mirt_network"] = 10
    player.reputation["violet_watch"] = 10

    assert "Any work for a trusted friend?" in [
        text for text, _ in mirt.visible_options(game)
    ]
    assert "The Watch could use someone like you." in [
        text for text, _ in violet.visible_options(game)
    ]


def test_reputation_is_exposed_in_state_and_api(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Faction API", "char_class": "fighter"}
    ).get_json()["session_id"]
    server.active_sessions[session_id].game.player.reputation = {
        "mirt_network": 12
    }

    state = client.get(
        "/state", query_string={"session_id": session_id}
    ).get_json()
    reputation = client.get(
        "/reputation", query_string={"session_id": session_id}
    ).get_json()

    assert state["reputation"]["shop_discount"] == 5
    assert any(
        entry["id"] == "mirt_network"
        and entry["tier"] == "friendly"
        for entry in reputation["factions"]
    )
    assert reputation["shop_discount"] == 5


def test_reputation_entries_are_complete(recording_io):
    player, _ = _game(recording_io)

    entries = reputation_entries(player)

    assert {entry["id"] for entry in entries} == set(faction_catalogue())
    assert all("tier_label" in entry for entry in entries)
