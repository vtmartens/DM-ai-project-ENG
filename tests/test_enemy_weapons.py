"""Data-driven enemy attack profiles."""

from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


def _combat(recording_io, enemy):
    player = Player("Target", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    return player, game, combat


def test_enemy_attack_profiles_are_data_driven():
    goblin = Enemy("Goblin", monster_type="goblin")
    orc = Enemy("Orc", monster_type="orc")
    chief = Enemy("Chief", monster_type="bandit_chief")

    assert goblin.attack_ability() == "dexterity"
    assert goblin.attack_damage_modifier == goblin.dexterity + 1
    assert goblin.attack_bonus == goblin.dexterity + goblin.proficiency_bonus

    assert orc.attack_ability() == "strength"
    assert orc.attack_damage_modifier == orc.strength + 1

    assert chief.attack_ability() == "strength"
    assert chief.attack_damage_modifier == chief.strength + 2


def test_enemy_basic_attack_uses_its_attack_stat(recording_io):
    enemy = Enemy("Goblin", monster_type="goblin")
    player, game, combat = _combat(recording_io, enemy)
    combat.ability_cooldowns["0"] = {"poison_arrow": 2}
    combat.dice_d20.roll = lambda: 10
    before = player.hp

    combat._attack_enemy(player, game, enemy, index=0)

    assert player.hp == before - enemy.attack_damage_modifier
    assert "(DEX)" in recording_io.text


def test_enemy_attack_profile_survives_round_trip():
    enemy = Enemy("Custom", hp=20, strength_base=12)
    enemy.attack_stat = "dexterity"
    enemy.damage_bonus = 3
    enemy.armor_class_value = 14

    restored = Enemy.from_dict(enemy.to_dict())

    assert restored.attack_stat == "dexterity"
    assert restored.damage_bonus == 3
    assert restored.attack_ability() == "dexterity"
    assert restored.attack_damage_modifier == restored.dexterity + 3
