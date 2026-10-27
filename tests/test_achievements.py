"""Achievement tracking: event recording, condition evaluation and persistence."""

import pytest

from core.achievements import (
    SUPPORTED_CONDITIONS,
    record_event,
)
from core.game import Game
from core.game_state import GameState
from core.quests import complete_quest, record_combat, start_quest
from entities.enemy import Enemy
from entities.npc import NPC
from entities.player import Player
from items.item import Item
from states.combat import CombatState
from states.tavern import TavernState
from util.data_manager import get_data_manager


def _game(io):
    player = Player("Achiever", "fighter")
    return player, Game(player, None, io, temporary=True)


def test_movement_unlocks_first_step(recording_io):
    player, game = _game(recording_io)

    assert "first_step" not in player.achievements

    unlocked = record_event(player, "movement", game=game)

    assert unlocked == ["first_step"]
    assert "first_step" in player.achievements
    assert player.achievement_stats["movement"] == 1
    assert "Achievement unlocked: First Step" in recording_io.text


def test_an_achievement_is_only_unlocked_once(recording_io):
    player, game = _game(recording_io)

    record_event(player, "movement", game=game)
    unlocked = record_event(player, "movement", game=game)

    assert unlocked == []
    assert player.achievements.count("first_step") == 1
    assert player.achievement_stats["movement"] == 2


def test_first_blood_and_clean_victory_streak(recording_io):
    player, game = _game(recording_io)

    record_event(player, "combat_victory", game=game, clean=True)

    assert "first_blood" in player.achievements
    assert player.achievement_stats["combat_without_damage"] == 1

    record_event(player, "combat_victory", game=game, clean=False)

    assert player.achievement_stats["combat_victory"] == 2
    assert player.achievement_stats["combat_without_damage"] == 0


def test_ten_clean_victories_unlock_invincible(recording_io):
    player, game = _game(recording_io)

    for _ in range(10):
        record_event(player, "combat_victory", game=game, clean=True)

    assert "invincible" in player.achievements


def test_defeating_the_last_enemy_unlocks_first_blood(recording_io):
    player, game = _game(recording_io)
    enemy = Enemy("Training Dummy", hp=1, damage=1)
    enemy.hp = 0
    combat = CombatState(enemy=enemy)
    game.push_state(combat)

    combat.run(game)

    assert "first_blood" in player.achievements
    assert player.achievement_stats["combat_victory"] == 1


def test_equipping_a_legendary_weapon_unlocks_weapon_master(recording_io):
    player, game = _game(recording_io)
    dragonbane = Item(
        "Dragonbane",
        "weapon",
        {"strength": 8},
        400,
        "A legendary blade",
        rarity="legendary",
    )
    player.add_item(dragonbane)

    dragonbane.equip(player, game)

    assert player.weapon is dragonbane
    assert "weapon_master" in player.achievements


def test_coins_unlock_filthy_rich(recording_io):
    player, game = _game(recording_io)
    player.gold = 1000

    record_event(player, "gold_changed", game=game)

    assert "filthy_rich" in player.achievements


def test_visiting_every_map_unlocks_explorer(recording_io):
    player, game = _game(recording_io)

    for map_name in game.map_manager.maps:
        record_event(player, "area_visited", game=game, map=map_name)

    assert set(player.achievement_stats["areas_visited"]) == set(
        game.map_manager.maps
    )
    assert "explorer" in player.achievements


def test_completing_a_quest_without_fighting_unlocks_diplomacy(recording_io):
    player, game = _game(recording_io)

    assert start_quest(player, "violet_warning", game) is True
    assert complete_quest(player, "violet_warning", game) is True

    assert "diplomacy" in player.achievements


def test_fighting_during_a_quest_prevents_diplomacy(recording_io):
    player, game = _game(recording_io)

    assert start_quest(player, "violet_warning", game) is True
    record_combat(player)
    assert complete_quest(player, "violet_warning", game) is True

    assert "diplomacy" not in player.achievements


def test_achievement_progress_survives_save_and_load(recording_io, tmp_path):
    player, game = _game(recording_io)
    game.set_initial_map("tavern")
    record_event(player, "movement", game=game)
    player.gold = 1100
    record_event(player, "gold_changed", game=game)
    save_path = tmp_path / "achievements.json"

    assert game.save(str(save_path)) is True

    loaded = Game(None, None, recording_io, temporary=True)
    assert loaded.load(str(save_path)) is True

    assert "first_step" in loaded.player.achievements
    assert "filthy_rich" in loaded.player.achievements
    assert loaded.player.achievement_stats["movement"] == 1
    assert loaded.player.achievement_timestamps["first_step"] > 0


def test_get_current_state_exposes_achievements(recording_io):
    player, _ = _game(recording_io)
    session = GameState(player, TavernState())

    state = session.get_current_state()
    assert state["achievements"] == []
    assert state["timestamp_achievements"] == {}

    record_event(player, "movement")

    state = session.get_current_state()
    assert "first_step" in state["achievements"]
    assert state["timestamp_achievements"]["first_step"] > 0


def test_new_progression_achievements_unlock_from_recorded_events(recording_io):
    player, game = _game(recording_io)

    for _ in range(3):
        record_event(player, "bounty_claimed", game=game)
    assert "contractor" in player.achievements

    for _ in range(5):
        record_event(player, "road_victory", game=game)
    assert "roadwarden" in player.achievements

    player.cleared_areas = ["waystation"]
    record_event(player, "area_cleared", game=game, area="waystation")
    assert "waystation_liberator" in player.achievements

    for _ in range(3):
        record_event(
            player, "item_bought", game=game, item_type="weapon"
        )
    assert "well_equipped" in player.achievements
    assert player.achievement_stats["equipment_bought"] == 3
    assert player.achievement_stats["items_bought"] == 3

    player.defeats = 1
    record_event(player, "combat_defeat", game=game)
    assert "back_on_your_feet" in player.achievements

    record_event(
        player, "enemy_defeated", game=game, enemy="Iron Sentinel"
    )
    assert "vaultbreaker" in player.achievements


def test_shop_purchases_count_toward_well_equipped(recording_io):
    from core.shop import buy_item

    player, game = _game(recording_io)
    player.gold = 1000

    for item_name in ("Chainmail", "Short Sword", "Ring of Strength"):
        assert buy_item(player, item_name, game)["success"] is True

    assert player.achievement_stats["items_bought"] == 3
    assert player.achievement_stats["equipment_bought"] == 3
    assert "well_equipped" in player.achievements


def test_road_victory_and_area_clear_hooks(recording_io):
    player, game = _game(recording_io)
    enemy = Enemy("Training Dummy", hp=1)
    combat = CombatState(
        enemy=enemy,
        encounter={
            "title": "Road Fight",
            "source": "road",
            "clears_area": "waystation",
            "reward": {"gold": 0, "experience": 0},
        },
    )
    game.push_state(combat)

    assert combat._grant_encounter_reward(game) is True

    assert player.achievement_stats["road_victories"] == 1
    assert "waystation" in player.cleared_areas
    assert "waystation_liberator" in player.achievements


def test_vaultbreaker_via_enemy_defeat_hook(recording_io):
    from core.quests import record_enemy_defeat

    player, game = _game(recording_io)

    record_enemy_defeat(player, "Iron Sentinel", game)

    assert "Iron Sentinel" in player.achievement_stats["enemies_defeated"]
    assert "vaultbreaker" in player.achievements


def test_every_catalogue_condition_type_is_supported():
    definitions = get_data_manager().get_achievements()
    assert definitions

    unsupported = {
        achievement["condition"]["type"]
        for achievement in definitions
        if achievement["condition"]["type"] not in SUPPORTED_CONDITIONS
    }
    assert not unsupported


def test_npc_inventories_are_not_tracked_as_player_achievements():
    npc = NPC("Durnan")

    npc.add_item(Item("Test Trinket", "common", {}, 1, ""))

    assert not hasattr(npc, "achievements")


def test_vargas_loot_includes_the_legendary_weapon():
    vargas = NPC("Vargas")

    assert vargas.inventory[0].name == "Dragonbane"
    assert vargas.inventory[0].rarity == "legendary"
    assert vargas.inventory[0].effect.get("strength") == 8


def test_violet_warning_quest_is_completable_through_dialogue(recording_io):
    player, game = _game(recording_io)
    mirt = NPC("Mirt")
    start_quest(player, "violet_warning", game)

    conversation = mirt.get_conversation("start")
    option = next(
        option
        for option in conversation["options"]
        if "Violet sent me" in option[0]
    )

    assert option[1] == "violet_warning_turn_in"
    assert option[2] == {
        "quest": "violet_warning",
        "status": "active",
    }


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _command(client, session_id, command):
    return client.post(
        "/command",
        json={"session_id": session_id, "command": command},
    ).get_json()


def _choose_option(client, session_id, response, text_fragment):
    options = response["state"]["dialogue"]["options"]
    option = next(
        option for option in options if text_fragment in option["text"]
    )
    return _command(client, session_id, str(option["index"]))


def test_warning_quest_unlocks_diplomacy_end_to_end(client):
    response = client.post(
        "/start", json={"name": "Diplomat", "char_class": "fighter"}
    )
    session_id = response.get_json()["session_id"]

    _command(client, session_id, "go to market")
    response = _command(client, session_id, "talk to Violet")
    response = _choose_option(
        client, session_id, response, "anything else I can do"
    )
    response = _choose_option(
        client, session_id, response, "carry the warning"
    )
    _choose_option(client, session_id, response, "find him")

    _command(client, session_id, "go to tavern")
    response = _command(client, session_id, "talk to Mirt")
    _choose_option(client, session_id, response, "Violet sent me")

    achievements = client.get(
        "/achievements", query_string={"session_id": session_id}
    ).get_json()
    unlocked = {
        achievement["id"]
        for achievement in achievements["achievements"]
        if achievement["unlocked"]
    }
    missions = client.get(
        "/missions", query_string={"session_id": session_id}
    ).get_json()

    assert "diplomacy" in unlocked
    assert [quest["title"] for quest in missions["completed"]] == [
        "A Word of Warning"
    ]
