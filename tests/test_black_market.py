"""Nessa's tiered Underroad black market and its API."""

import pytest

from core.black_market import (
    black_market_entries,
    black_market_state,
    black_market_unlocked,
    buy_black_market_item,
)
from core.game import Game
from entities.player import Player
from states.black_market import BlackMarketState
from states.underroad import UnderroadState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _player(recording_io, reputation=8, gold=500, completed=True):
    player = Player("Cache Tester", "fighter")
    player.reputation = {"underroad_smugglers": reputation}
    player.gold = gold
    if completed:
        player.completed_quests = [
            {
                "id": "quiet_cargo",
                "title": "The Quiet Cargo",
                "status": "completed",
            }
        ]
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def test_cache_requires_the_side_quest_and_positive_standing(recording_io):
    player, _ = _player(recording_io, completed=False)
    assert black_market_unlocked(player) is False

    player, _ = _player(recording_io, reputation=0)
    assert black_market_unlocked(player) is False

    player, _ = _player(recording_io, reputation=8)
    assert black_market_unlocked(player) is True


def test_standing_controls_stock_tiers(recording_io):
    runner, _ = _player(recording_io, reputation=8)
    runner_names = {
        entry["name"]
        for entry in black_market_entries(runner)
        if entry["available"]
    }
    assert {"Smoke Bomb", "Antidote", "Spider Poison"} <= runner_names
    assert "Greater Healing Potion" not in runner_names
    assert "Smuggler's Nightglass" not in runner_names

    friendly, _ = _player(recording_io, reputation=16)
    friendly_names = {
        entry["name"]
        for entry in black_market_entries(friendly)
        if entry["available"]
    }
    assert "Greater Healing Potion" in friendly_names
    assert "Thief's Gloves" in friendly_names
    assert "Boots of Speed" not in friendly_names

    trusted, _ = _player(recording_io, reputation=30)
    trusted_entries = {
        entry["name"]: entry for entry in black_market_entries(trusted)
    }
    assert "Boots of Speed" in trusted_entries
    assert "Smuggler's Nightglass" in trusted_entries
    assert trusted_entries["Smuggler's Nightglass"]["unique"] is True
    assert black_market_state(trusted)["discount"] == 5

    allied, _ = _player(recording_io, reputation=45)
    allied_entries = {
        entry["name"]: entry for entry in black_market_entries(allied)
    }
    assert "Rune Draught" in allied_entries
    assert allied_entries["Rune Draught"]["price"] == 81
    assert black_market_state(allied)["discount"] == 10


def test_buy_charges_gold_and_adds_the_item(recording_io):
    player, game = _player(recording_io, reputation=8, gold=100)

    result = buy_black_market_item(player, "Smoke Bomb", game)

    assert result["success"] is True
    assert result["price"] == 15
    assert player.gold == 85
    assert "Smoke Bomb" in [item.name for item in player.inventory]
    assert "You buy Smoke Bomb from Nessa's cache for 15 gold." in (
        recording_io.text
    )


def test_locked_and_unaffordable_items_are_refused(recording_io):
    player, game = _player(recording_io, reputation=8, gold=5)

    locked = buy_black_market_item(player, "Greater Healing Potion", game)
    assert locked["success"] is False
    assert player.gold == 5

    poor = buy_black_market_item(player, "Smoke Bomb", game)
    assert poor["success"] is False
    assert "only have 5" in poor["message"]
    assert "Smoke Bomb" not in [item.name for item in player.inventory]


def test_unique_stock_can_only_be_bought_once(recording_io):
    player, game = _player(recording_io, reputation=30, gold=1000)

    assert (
        buy_black_market_item(player, "Smuggler's Nightglass", game)[
            "success"
        ]
        is True
    )
    assert (
        buy_black_market_item(player, "Smuggler's Nightglass", game)[
            "success"
        ]
        is False
    )

    assert [item.name for item in player.inventory].count(
        "Smuggler's Nightglass"
    ) == 1
    assert "black_market:smuggler's nightglass" in player.claimed_rewards
    restored = Player.from_dict(player.to_dict())
    nightglass = next(
        entry
        for entry in black_market_entries(restored)
        if entry["name"] == "Smuggler's Nightglass"
    )
    assert nightglass["purchased"] is True


def test_cleared_underroad_opens_the_cache_menu(recording_io):
    player, game = _player(recording_io, reputation=8)
    player.cleared_areas = ["underroad"]
    state = UnderroadState(game)
    game.push_state(state)

    assert "Nessa's cache" in state.available_actions(game)

    assert state._open_black_market(game) is True
    assert isinstance(game.current_state(), BlackMarketState)


def test_cache_menu_is_hidden_without_the_side_quest(recording_io):
    player, game = _player(recording_io, reputation=8, completed=False)
    player.cleared_areas = ["underroad"]
    state = UnderroadState(game)
    game.push_state(state)

    assert "Nessa's cache" not in state.available_actions(game)
    assert state._open_black_market(game) is False


def test_black_market_api_lists_and_buys(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Cache API", "char_class": "fighter"}
    ).get_json()["session_id"]
    session = server.active_sessions[session_id]
    player = session.game.player
    player.completed_quests = [
        {"id": "quiet_cargo", "title": "The Quiet Cargo"}
    ]
    player.reputation = {"underroad_smugglers": 8}
    player.gold = 100
    session.game.change_state(BlackMarketState(session.game))

    listing = client.get(
        "/black_market", query_string={"session_id": session_id}
    ).get_json()
    assert listing["tier"] == "runner"
    assert listing["unlocked"] is True
    assert listing["gold"] == 100
    assert any(entry["name"] == "Smoke Bomb" for entry in listing["items"])

    bought = client.post(
        "/black_market/buy",
        json={"session_id": session_id, "item": "Smoke Bomb"},
    ).get_json()

    assert bought["bought"] is True
    assert bought["black_market"]["gold"] == 85
    assert player.gold == 85
    assert "Smoke Bomb" in [item.name for item in player.inventory]
    assert any(
        "You buy Smoke Bomb from Nessa's cache" in message["text"]
        for message in bought["output"]
    )


def test_black_market_api_is_refused_outside_the_cache(client):
    session_id = client.post(
        "/start", json={"name": "No Cache", "char_class": "fighter"}
    ).get_json()["session_id"]

    assert (
        client.get(
            "/black_market", query_string={"session_id": session_id}
        ).status_code
        == 409
    )
    refused = client.post(
        "/black_market/buy",
        json={"session_id": session_id, "item": "Smoke Bomb"},
    ).get_json()
    assert refused["bought"] is False
    assert "not open" in refused["message"]
