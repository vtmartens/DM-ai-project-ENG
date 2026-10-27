"""New Cycle reset, retention, scaling and achievement behavior."""

from core.cycles import enemy_scaling, reward_multiplier
from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from items.item import Item
from states.combat import CombatState
from states.tavern import TavernState


def _game(recording_io):
    player = Player("Cycle Tester", "fighter")
    player.level = 10
    player.hp = 4
    player.mana = 0
    player.gold = 300
    player.reputation = {"mirt_network": 12}
    player.rune_trials_best = 4
    player.rune_trials_runs = 1
    player.rune_shards = 6
    player.achievements = ["first_step"]
    player.achievement_timestamps = {"first_step": 1}
    player.claimed_rewards = [
        "crafted:rune_forged_blade",
        "black_market:smuggler's nightglass",
        "runeheart_mirt",
        "sanctum_vault",
        "underroad_cache",
    ]
    player.active_quests = [{"id": "vargas_debt", "title": "A Debt"}]
    player.completed_quests = [
        {"id": "sanctum_chapter", "title": "The Sealed Sanctum"},
        {"id": "runeheart_gate", "title": "The Runeheart Gate"},
    ]
    player.cleared_areas = ["waystation", "underroad", "sanctum"]
    player.conditions = {"poison": {"damage": 1, "turns": 1}}
    player.stealthed = True
    player.allies = ["Violet"]
    player.defeats = 3
    player.add_item(
        Item("Rune-Forged Blade", "weapon", {"strength": 7}, 500)
    )
    game = Game(player, TavernState(), recording_io, temporary=True)
    game.set_initial_map("tavern")
    return player, game


def test_new_cycle_resets_story_and_preserves_meta_progress(recording_io):
    player, game = _game(recording_io)
    opened_door = game.map_manager.get_map("tavern").items[(22, 9)]
    opened_door.state = "open"
    inventory_names = [item.name for item in player.inventory]

    assert game.start_new_cycle() is True

    assert player.cycle == 2
    assert player.active_quests == []
    assert player.completed_quests == []
    assert player.progress_quests == {}
    assert player.cleared_areas == []
    assert player.claimed_rewards == [
        "crafted:rune_forged_blade",
        "black_market:smuggler's nightglass",
    ]
    assert player.conditions == {}
    assert player.stealthed is False
    assert player.allies == []
    assert player.defeats == 0
    assert player.hp == player.hp_max
    assert player.mana == player.mana_max
    assert player.level == 10
    assert player.reputation == {"mirt_network": 12}
    assert player.rune_trials_best == 4
    assert player.rune_trials_runs == 1
    assert player.rune_shards == 6
    assert "first_step" in player.achievements
    assert inventory_names == [item.name for item in player.inventory]
    assert isinstance(game.current_state(), TavernState)
    assert player.current_map == "tavern"
    assert game.map_manager.get_map("tavern").items[(22, 9)].state == "closed"
    assert "cyclebreaker" in player.achievements


def test_tavern_only_offers_cycle_after_campaign_completion(recording_io):
    player, _ = _game(recording_io)
    player.completed_quests = []

    assert TavernState._campaign_complete(player) is False

    player.completed_quests = [
        {"id": "sanctum_chapter", "title": "The Sealed Sanctum"}
    ]
    assert TavernState._campaign_complete(player) is False

    player.completed_quests.append(
        {"id": "runeheart_gate", "title": "The Runeheart Gate"}
    )
    assert TavernState._campaign_complete(player) is True


def test_cycle_scaling_and_rewards_are_data_driven():
    assert enemy_scaling(1) == {
        "hp_percent": 0,
        "damage_bonus": 0,
        "ac_bonus": 0,
    }
    assert enemy_scaling(2) == {
        "hp_percent": 20,
        "damage_bonus": 1,
        "ac_bonus": 1,
    }
    assert reward_multiplier(1) == 1.0
    assert reward_multiplier(2) == 1.25


def test_combat_scales_enemies_once_for_the_cycle(recording_io):
    player = Player("Scaled", "fighter")
    player.cycle = 2
    game = Game(player, None, recording_io, temporary=True)
    enemy = Enemy("Brute", hp=20, strength_base=14)
    enemy.armor_class_value = 12
    combat = CombatState(enemy=enemy)
    game.push_state(combat)

    combat._apply_cycle_scaling(player)
    combat._apply_cycle_scaling(player)

    assert enemy.hp_max == 24
    assert enemy.hp == 24
    assert enemy.damage_bonus == 1
    assert enemy.armor_class == 13
    assert combat.cycle_scaled is True


def test_cycle_survives_a_player_round_trip(recording_io):
    player, _ = _game(recording_io)
    player.cycle = 3

    assert Player.from_dict(player.to_dict()).cycle == 3
