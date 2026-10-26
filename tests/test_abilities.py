import pytest

from core.abilities import player_abilities, use_ability
from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


def _combat_game(recording_io, char_class, enemy_hp=30, enemy_strength=30):
    player = Player("Ability Tester", char_class)
    enemy = Enemy(
        "Training Dummy",
        hp=enemy_hp,
        strength_base=enemy_strength,
    )
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    return player, enemy, game, combat


def test_player_abilities_include_costs_and_descriptions():
    details = player_abilities(Player("Aria", "wizard"))

    assert [ability["name"] for ability in details] == [
        "Magic Missile",
        "Mage Shield",
    ]
    assert details[0]["mana_cost"] == 5
    assert details[0]["combat_only"] is True
    assert details[0]["description"]


def test_progression_abilities_stay_locked_until_their_level():
    player = Player("Aria", "wizard")
    all_abilities = {
        ability["name"]: ability
        for ability in player_abilities(player, include_locked=True)
    }

    assert all_abilities["Fireball"]["unlocked"] is False
    assert all_abilities["Fireball"]["required_level"] == 3
    assert "Fireball" not in [a["name"] for a in player_abilities(player)]

    player.level = 3

    assert "Fireball" in [a["name"] for a in player_abilities(player)]


@pytest.mark.parametrize(
    ("char_class", "hp_gain", "mana_gain", "unlocked"),
    [
        ("fighter", 10, 0, "Fierce Attack"),
        ("wizard", 4, 10, "Fireball"),
        ("rogue", 6, 2, "Backstab"),
        ("cleric", 8, 6, "Remove Curse"),
    ],
)
def test_level_up_uses_class_growth_and_unlocks_level_three_ability(
    recording_io, char_class, hp_gain, mana_gain, unlocked
):
    player = Player("Level Tester", char_class)
    game = Game(player, None, recording_io, temporary=True)
    hp_max = player.hp_max
    mana_max = player.mana_max

    player.gain_experience(100, game)

    assert player.level == 2
    assert player.hp_max == hp_max + hp_gain
    assert player.mana_max == mana_max + mana_gain

    recording_io.clear()
    player.gain_experience(200, game)

    assert player.level == 3
    assert unlocked in [ability["name"] for ability in player_abilities(player)]
    assert f"You learned {unlocked}!" in recording_io.text


def test_magic_missile_damages_and_spends_mana(recording_io):
    player, enemy, game, _ = _combat_game(recording_io, "wizard")
    before_hp = enemy.hp
    before_mana = player.mana

    assert use_ability(game, "Magic Missile") is True

    assert enemy.hp == before_hp - 8
    assert player.mana == before_mana - 5
    assert "Magic Missile" in recording_io.text


def test_ability_is_refused_without_mana(recording_io):
    player, enemy, game, _ = _combat_game(recording_io, "wizard")
    player.mana = 0
    before_hp = enemy.hp

    assert use_ability(game, "Magic Missile") is False

    assert enemy.hp == before_hp
    assert player.mana == 0
    assert "need 5 mana" in recording_io.text


def test_combat_only_ability_is_refused_outside_combat(recording_io):
    player = Player("Borin", "fighter")
    game = Game(player, None, recording_io, temporary=True)

    assert use_ability(game, "Powerful Blow") is False

    assert "only be used in combat" in recording_io.text


def test_cure_wounds_heals_outside_combat(recording_io):
    player = Player("Cleric", "cleric")
    player.hp = 1
    game = Game(player, None, recording_io, temporary=True)
    before_mana = player.mana

    assert use_ability(game, "Cure Wounds") is True

    assert player.hp == min(player.hp_max, 9)
    assert player.mana == before_mana - 4


def test_parry_reduces_the_next_incoming_attack(recording_io):
    player, enemy, game, combat = _combat_game(recording_io, "fighter")
    assert use_ability(game, "Parry") is True
    assert combat.effects["guard"] == 5

    expected = max(1, enemy.strength - player.defense)
    expected_after = max(0, expected - 5)
    before_hp = player.hp
    combat._attack_enemy(player, game)

    assert player.hp == before_hp - expected_after
    assert "guard" not in combat.effects
    assert "guard absorbs" in recording_io.text


def test_mage_shield_absorbs_damage(recording_io):
    player, enemy, game, combat = _combat_game(recording_io, "wizard")
    assert use_ability(game, "Mage Shield") is True
    assert combat.effects["shield"] == 6

    expected = max(1, enemy.strength - player.defense)
    expected_after = max(0, expected - 6)
    before_hp = player.hp
    combat._attack_enemy(player, game)

    assert player.hp == before_hp - expected_after
    assert "shield" not in combat.effects
    assert "shield absorbs" in recording_io.text


def test_evade_negates_the_next_attack(recording_io):
    player, _, game, combat = _combat_game(recording_io, "rogue")
    assert use_ability(game, "Evade") is True
    before_hp = player.hp

    combat._attack_enemy(player, game)

    assert player.hp == before_hp
    assert "evade" not in combat.effects
    assert "evade" in recording_io.text.lower()
