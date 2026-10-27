"""Level 10 class capstones and their achievement."""

from core.abilities import player_abilities, use_ability
from core.achievements import record_event
from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState

CAPSTONES = {
    "fighter": "Last Stand",
    "wizard": "Meteor Swarm",
    "rogue": "Assassinate",
    "cleric": "Divine Intervention",
}


def _game(recording_io, char_class):
    player = Player("Capstone Tester", char_class)
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def test_each_class_capstone_is_locked_before_level_ten(recording_io):
    for char_class, capstone_name in CAPSTONES.items():
        player, _ = _game(recording_io, char_class)
        player.level = 9
        abilities = {
            ability["name"]: ability
            for ability in player_abilities(player, include_locked=True)
        }
        assert abilities[capstone_name]["required_level"] == 10
        assert abilities[capstone_name]["unlocked"] is False

        player.level = 10
        assert next(
            ability
            for ability in player_abilities(player, include_locked=True)
            if ability["name"] == capstone_name
        )["unlocked"] is True


def test_fighter_capstone_grants_attack_and_defense(recording_io):
    player, game = _game(recording_io, "fighter")
    player.level = 10
    enemy = Enemy("Training Dummy", hp=50)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    name, definition = next(
        (a["name"], a)
        for a in player_abilities(player)
        if a["name"] == "Last Stand"
    )

    assert use_ability(game, name, definition) is True

    assert combat.effects["bless_attack"] == 5
    assert combat.effects["bless_defense"] == 5


def test_wizard_capstone_ignores_defense(recording_io):
    player, game = _game(recording_io, "wizard")
    player.level = 10
    player.mana = 18
    enemy = Enemy("Armored Dummy", hp=50, defense=5)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    name, definition = next(
        (a["name"], a)
        for a in player_abilities(player)
        if a["name"] == "Meteor Swarm"
    )

    assert use_ability(game, name, definition) is True

    assert enemy.hp == 20
    assert player.mana == 0


def test_rogue_capstone_multiplies_weapon_damage(recording_io):
    player, game = _game(recording_io, "rogue")
    player.level = 10
    player.mana = 8
    enemy = Enemy("Training Dummy", hp=100)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    name, definition = next(
        (a["name"], a)
        for a in player_abilities(player)
        if a["name"] == "Assassinate"
    )
    before = enemy.hp

    assert use_ability(game, name, definition) is True

    expected = max(1, player.attack_damage_modifier * 4)
    assert enemy.hp == before - expected
    assert player.mana == 0


def test_cleric_capstone_restores_forty_hp(recording_io):
    player, game = _game(recording_io, "cleric")
    player.level = 10
    player.mana = 12
    player.hp = 10
    player.hp_max = 50
    name, definition = next(
        (a["name"], a)
        for a in player_abilities(player)
        if a["name"] == "Divine Intervention"
    )

    assert use_ability(game, name, definition) is True

    assert player.hp == 50
    assert player.mana == 0


def test_reaching_level_ten_unlocks_the_legend_achievement(recording_io):
    player, game = _game(recording_io, "fighter")
    player.level = 10

    record_event(player, "level_up", game=game)

    assert "legend" in player.achievements
