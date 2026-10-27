"""Sealed Vault: the warehouse lock chain, guardian and relic loot."""

from core.game import Game
from core.quests import start_quest
from entities.player import Player
from items.item import Item
from states.combat import CombatState


def _game(recording_io, map_name="warehouse"):
    player = Player("Vault Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map(map_name)
    return player, game


def _warehouse_key():
    return Item(
        "Warehouse Key",
        "key",
        {"opens": ["Warehouse Door", "Sealed Strongbox"]},
        25,
    )


def _vault_key():
    return Item("Vault Key", "key", {"opens": ["Vault Door"]}, 40)


def _names(player):
    return {
        getattr(item, "name", item) for item in player.inventory
    }


def test_vault_map_loads_with_its_lock_guardian_and_relic():
    from world.map_manager import MapManager

    manager = MapManager()
    vault = manager.get_map("vault")

    assert vault is not None
    assert [npc.name for npc in vault.npc.values()] == ["Iron Sentinel"]
    assert "Relic Chest" in {
        getattr(obj, "name", "") for obj in vault.items.values()
    }
    assert manager.get_map("warehouse").items[(18, 2)].name == "Vault Door"


def test_vault_door_blocks_movement_without_the_key(recording_io):
    player, game = _game(recording_io)
    player.set_position("warehouse", 17, 2)

    result = player.move(1, 0, game.map_manager)

    assert result["success"] is False
    assert "locked" in result["message"].lower()
    assert player.current_map == "warehouse"


def test_warehouse_key_opens_the_strongbox_and_yields_the_vault_key(recording_io):
    player, game = _game(recording_io)
    player.set_position("warehouse", 16, 8)
    key = _warehouse_key()
    player.add_item(key)
    chest = game.map_manager.get_map("warehouse").items[(16, 9)]

    key.use(player, game)

    assert chest.state == "open"
    assert "Vault Key" in _names(player)


def test_vault_key_opens_the_vault_door_and_enters_the_vault(recording_io):
    player, game = _game(recording_io)
    player.set_position("warehouse", 17, 2)
    key = _vault_key()
    player.add_item(key)

    key.use(player, game)

    door = game.map_manager.get_map("warehouse").items[(18, 2)]
    assert door.state == "open"

    result = player.move(1, 0, game.map_manager)

    assert result["success"] is True
    assert result["change_map"] is True
    assert player.current_map == "vault"
    assert (player.x, player.y) == (2, 8)


def test_direct_travel_to_the_vault_needs_the_vault_key(recording_io):
    player, game = _game(recording_io, "tavern")
    player.add_item(_warehouse_key())

    blocked = game.change_map("vault")

    assert blocked["success"] is False
    assert "locked" in blocked["message"].lower()

    player.add_item(_vault_key())

    allowed = game.change_map("vault")

    assert allowed["success"] is True
    assert player.current_map == "vault"
    assert game.map_manager.get_map("warehouse").items[(18, 2)].state == "open"


def test_the_open_vault_exit_does_not_unlock_the_warehouse_from_the_tavern(recording_io):
    player, game = _game(recording_io, "tavern")

    result = game.change_map("warehouse")

    assert result["success"] is False
    assert "locked" in result["message"].lower()


def test_vault_exit_returns_to_the_warehouse(recording_io):
    player, game = _game(recording_io, "vault")
    player.set_position("vault", 2, 8)

    result = player.move(-1, 0, game.map_manager)

    assert result["success"] is True
    assert result["change_map"] is True
    assert player.current_map == "warehouse"
    assert (player.x, player.y) == (17, 2)


def test_guardian_drops_the_sentinel_key_and_the_relic_chest_yields_loot(recording_io):
    player, game = _game(recording_io, "vault")
    player.set_position("vault", 16, 6)
    start_quest(player, "sentinel_sigil", game)
    vault = game.map_manager.get_map("vault")
    guardian = next(npc for npc in vault.npc.values() if npc.name == "Iron Sentinel")

    combat = CombatState(enemies=[guardian])
    game.push_state(combat)
    guardian.hp = 0
    combat.run(game)

    assert "Sentinel Key" in _names(player)
    chest = game.map_manager.get_map("vault").items[(16, 5)]
    assert chest.state == "closed"

    sentinel_key = next(
        item
        for item in player.inventory
        if getattr(item, "name", None) == "Sentinel Key"
    )
    sentinel_key.use(player, game)

    assert chest.state == "open"
    assert "Sentinel's Edge" in _names(player)
    assert "Greater Healing Potion" in _names(player)
    assert all(npc.name != "Iron Sentinel" for npc in vault.npc.values())
    quest = next(
        quest
        for quest in player.active_quests
        if quest.get("id") == "sentinel_sigil"
    )
    assert quest["status"] == "ready"


def test_vault_door_state_survives_save_and_load(recording_io, tmp_path):
    player, game = _game(recording_io)
    door = game.map_manager.get_map("warehouse").items[(18, 2)]
    door.state = "open"
    save_path = tmp_path / "vault.json"

    assert game.save(str(save_path)) is True

    loaded = Game(None, None, recording_io, temporary=True)
    assert loaded.load(str(save_path)) is True

    loaded_door = loaded.map_manager.get_map("warehouse").items[(18, 2)]
    assert loaded_door.state == "open"
    assert loaded_door.requires_key is True
    assert "vault" in loaded.map_manager.maps
