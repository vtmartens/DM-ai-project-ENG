"""Locked doors, keys and the routes they gate."""

from core.abilities import use_ability
from core.game import Game
from core.quests import start_quest
from entities.npc import NPC
from entities.player import Player
from items.item import Item
from states.dialogue import DialogueState


def _game(recording_io, char_class="fighter"):
    game = Game(
        Player("Lock Tester", char_class),
        None,
        recording_io,
        temporary=True,
    )
    game.set_initial_map("tavern")
    return game


def test_locked_cellar_door_blocks_movement(recording_io):
    game = _game(recording_io)
    player = game.player
    player.set_position("tavern", 21, 9)

    result = player.move(1, 0, game.map_manager)

    assert result["success"] is False
    assert "locked" in result["message"].lower()
    assert player.current_map == "tavern"
    assert (player.x, player.y) == (21, 9)


def test_cellar_key_opens_the_door_and_enters_the_cellar(recording_io):
    game = _game(recording_io)
    player = game.player
    player.set_position("tavern", 21, 9)
    key = Item("Cellar Key", "key", {"opens": ["Cellar Door"]}, 10)
    player.add_item(key)

    key.use(player, game)

    door = game.map_manager.get_map("tavern").items[(22, 9)]
    assert door.state == "open"

    result = player.move(1, 0, game.map_manager)

    assert result["success"] is True
    assert result["change_map"] is True
    assert player.current_map == "cellar"
    assert (player.x, player.y) == (18, 8)


def test_knock_opens_the_cellar_door(recording_io):
    game = _game(recording_io, "wizard")
    player = game.player
    player.set_position("tavern", 21, 9)

    assert use_ability(game, "Knock") is True

    door = game.map_manager.get_map("tavern").items[(22, 9)]
    assert door.state == "open"

    result = player.move(1, 0, game.map_manager)

    assert result["success"] is True
    assert result["change_map"] is True


def test_direct_travel_to_the_warehouse_is_locked(recording_io):
    game = _game(recording_io)

    result = game.change_map("warehouse")

    assert result["success"] is False
    assert "locked" in result["message"].lower()
    assert game.player.current_map == "tavern"


def test_warehouse_key_unlocks_direct_travel(recording_io):
    game = _game(recording_io)
    player = game.player
    player.add_item(
        Item("Warehouse Key", "key", {"opens": ["Warehouse Door"]}, 25)
    )

    result = game.change_map("warehouse")

    assert result["success"] is True
    assert player.current_map == "warehouse"
    assert game.map_manager.get_map("market").items[(20, 7)].state == "open"
    assert "unlock" in recording_io.text.lower()


def test_violets_quest_hands_over_the_warehouse_key(recording_io):
    game = _game(recording_io)
    violet = NPC("Violet")
    state = DialogueState(violet)

    state._manage_effect({"type": "add_item", "item": "Warehouse Key"}, game)

    player_items = {
        getattr(item, "name", item) for item in game.player.inventory
    }
    npc_items = {
        getattr(item, "name", item) for item in violet.inventory
    }
    assert "Warehouse Key" in player_items
    assert "Warehouse Key" not in npc_items


def test_open_door_state_survives_save_and_load(recording_io, tmp_path):
    game = _game(recording_io)
    door = game.map_manager.get_map("tavern").items[(22, 9)]
    door.state = "open"
    save_path = tmp_path / "locks.json"

    assert game.save(str(save_path)) is True

    loaded = Game(None, None, recording_io, temporary=True)
    assert loaded.load(str(save_path)) is True

    loaded_door = loaded.map_manager.get_map("tavern").items[(22, 9)]
    assert loaded_door.state == "open"
    assert loaded_door.requires_key is True
    assert callable(getattr(loaded_door, "force_open", None))


def test_rusty_key_opens_the_tavern_treasure_chest(recording_io):
    game = _game(recording_io)
    player = game.player
    player.set_position("tavern", 2, 3)
    key = Item("Rusty Key", "key", {"opens": ["Treasure Chest"]}, 2)
    player.add_item(key)
    chest = game.map_manager.get_map("tavern").items[(2, 2)]

    key.use(player, game)

    assert chest.state == "open"
    assert "Golden Ring" in {
        getattr(item, "name", item) for item in player.inventory
    }


def test_loading_a_quest_save_restores_the_warehouse_key(recording_io, tmp_path):
    game = _game(recording_io)
    start_quest(game.player, "shadows_of_the_market", game)
    assert "Warehouse Key" not in {
        getattr(item, "name", item) for item in game.player.inventory
    }
    save_path = tmp_path / "old-quest.json"

    assert game.save(str(save_path)) is True

    loaded = Game(None, None, recording_io, temporary=True)
    assert loaded.load(str(save_path)) is True

    assert "Warehouse Key" in {
        getattr(item, "name", item) for item in loaded.player.inventory
    }
