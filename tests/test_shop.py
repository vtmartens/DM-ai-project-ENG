"""Market stock, purchases, sales and equipment stat changes."""

import pytest

from core.game import Game
from core.shop import buy_item, sell_item, sellable_items, shop_stock
from entities.player import Player
from items.item import Item


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _player(recording_io, char_class="fighter", gold=100):
    player = Player("Shop Tester", char_class)
    player.gold = gold
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def _start_in_market(client, char_class="fighter"):
    import server

    session_id = client.post(
        "/start", json={"name": "Shop Tester", "char_class": char_class}
    ).get_json()["session_id"]
    result = client.post(
        "/command", json={"session_id": session_id, "command": "go to market"}
    ).get_json()
    assert result["state"]["state"] == "MarketState"
    return session_id, server.active_sessions[session_id]


def test_shop_stock_has_each_equipment_category_and_prices():
    stock = shop_stock()
    categories = {entry["category"] for entry in stock}
    names = {entry["name"] for entry in stock}

    assert {"Weapons", "Armor", "Accessories", "Potions"} <= categories
    assert {"Short Sword", "Chainmail", "Ring of Strength", "Healing Potion"} <= names
    assert "Dragonbane" not in names
    assert "Sentinel's Edge" not in names
    chainmail = next(entry for entry in stock if entry["name"] == "Chainmail")
    assert chainmail["price"] == 45
    assert chainmail["sell_price"] == 22
    assert chainmail["effect_text"] == "AC +4"


def test_buy_item_charges_gold_and_adds_the_item_to_inventory(recording_io):
    player, game = _player(recording_io)

    result = buy_item(player, "Chainmail", game)

    assert result["success"] is True
    assert result["price"] == 45
    assert player.gold == 55
    assert "Chainmail" in [item.name for item in player.inventory]
    assert "You buy Chainmail for 45 gold." in recording_io.text


def test_buy_item_refuses_an_unaffordable_purchase(recording_io):
    player, game = _player(recording_io, gold=10)

    result = buy_item(player, "Plate Armor", game)

    assert result["success"] is False
    assert player.gold == 10
    assert "Plate Armor" not in [item.name for item in player.inventory]
    assert "only have 10" in recording_io.text


def test_sell_item_pays_half_value_and_refuses_equipped_gear(recording_io):
    player, game = _player(recording_io)
    blade = Item("Test Blade", "weapon", {"strength": 4}, 40)
    player.add_item(blade)

    result = sell_item(player, "Test Blade", game)

    assert result["success"] is True
    assert player.gold == 120
    assert "Test Blade" not in [item.name for item in player.inventory]
    assert "You sell Test Blade for 20 gold." in recording_io.text

    equipped_name = player.armor.name
    result = sell_item(player, equipped_name, game)

    assert result["success"] is False
    assert "Unequip" in result["message"]
    assert player.armor is not None


def test_equipping_gear_applies_all_effects_and_updates_ac_and_attack(recording_io):
    player, game = _player(recording_io)
    strength_before = player.strength
    dexterity_before = player.dexterity
    ac_before = player.armor_class
    attack_before = player.attack_bonus
    old_armor_dexterity = int(player.armor.effect.get("dexterity", 0) or 0)
    old_armor_defense = int(player.armor.effect.get("defense", 0) or 0)

    armor = Item(
        "Test Armor", "armor", {"defense": 4, "dexterity": 2}, 50
    )
    player.add_item(armor)
    armor.equip(player, game)

    assert (
        player.dexterity
        == dexterity_before - old_armor_dexterity + 2
    )
    assert (
        player.armor_class
        == ac_before
        + (4 - old_armor_defense)
        + (2 - old_armor_dexterity)
    )

    bow = Item(
        "Test Bow", "weapon", {"strength": 5, "dexterity": 1}, 50
    )
    player.add_item(bow)
    bow.equip(player, game)

    assert player.strength == strength_before + 2
    assert (
        player.dexterity
        == dexterity_before - old_armor_dexterity + 3
    )
    assert player.attack_bonus == attack_before + 2
    assert (
        player.armor_class
        == ac_before
        + (4 - old_armor_defense)
        + (3 - old_armor_dexterity)
    )

    bow.remove(player, game)

    assert player.strength == strength_before - 3
    assert (
        player.dexterity
        == dexterity_before - old_armor_dexterity + 2
    )
    assert player.attack_bonus == attack_before - 3
    assert (
        player.armor_class
        == ac_before
        + (4 - old_armor_defense)
        + (2 - old_armor_dexterity)
    )


def test_equipment_stat_effects_survive_a_player_round_trip(recording_io):
    player, _ = _player(recording_io)
    armor = Item(
        "Test Armor", "armor", {"defense": 4, "dexterity": 2}, 50
    )
    player.add_item(armor)
    armor.equip(player)

    restored = Player.from_dict(player.to_dict())

    assert restored.dexterity == player.dexterity
    assert restored.armor_class == player.armor_class
    assert restored.armor is not None
    assert restored.armor.name == "Test Armor"


def test_shop_api_buys_and_sells_equipment_in_the_market(client):
    session_id, session = _start_in_market(client)
    player = session.game.player

    shop = client.get(
        "/shop", query_string={"session_id": session_id}
    ).get_json()
    assert shop["gold"] == 100
    assert any(entry["name"] == "Chainmail" for entry in shop["stock"])
    assert shop["sellable"]

    bought = client.post(
        "/shop/buy",
        json={"session_id": session_id, "item": "Chainmail"},
    ).get_json()
    assert bought["bought"] is True
    assert bought["state"]["state"] == "MarketState"
    assert player.gold == 55
    assert "Chainmail" in [item.name for item in player.inventory]
    assert bought["shop"]["gold"] == 55

    sold = client.post(
        "/shop/sell",
        json={"session_id": session_id, "item": "Healing Potion"},
    ).get_json()
    assert sold["sold"] is True
    assert player.gold == 67
    assert "Healing Potion" not in [
        item.name for item in player.inventory
    ]

    refused = client.post(
        "/shop/sell",
        json={"session_id": session_id, "item": player.armor.name},
    ).get_json()
    assert refused["sold"] is False
    assert "Unequip" in refused["message"]


def test_shop_api_is_only_available_in_the_market(client):
    session_id = client.post(
        "/start", json={"name": "Tavern Shopper", "char_class": "fighter"}
    ).get_json()["session_id"]

    assert (
        client.get(
            "/shop", query_string={"session_id": session_id}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/shop/buy",
            json={"session_id": session_id, "item": "Chainmail"},
        ).status_code
        == 409
    )


def test_terminal_sell_flow_uses_the_shop_service(client):
    session_id, session = _start_in_market(client)

    listing = client.post(
        "/command", json={"session_id": session_id, "command": "sell"}
    ).get_json()
    assert any(
        "Healing Potion" in message["text"] for message in listing["output"]
    )

    client.post("/command", json={"session_id": session_id, "command": "1"})
    result = client.post(
        "/command", json={"session_id": session_id, "command": "y"}
    ).get_json()

    assert session.game.player.gold == 112
    assert "Healing Potion" not in [
        item.name for item in session.game.player.inventory
    ]
    assert any(
        "You sell Healing Potion" in message["text"]
        for message in result["output"]
    )


def test_direct_buy_command_uses_the_shop_stock(client):
    session_id, session = _start_in_market(client)

    result = client.post(
        "/command",
        json={"session_id": session_id, "command": "buy Chainmail"},
    ).get_json()

    assert result["state"]["state"] == "MarketState"
    assert session.game.player.gold == 55
    assert "Chainmail" in [
        item.name for item in session.game.player.inventory
    ]
    assert any(
        "You buy Chainmail" in message["text"] for message in result["output"]
    )
