"""Timed conditions, their modifiers and their ability hooks."""

import util.dice as dice_module
from core.conditions import (
    apply_condition,
    condition_damage_modifier,
    tick_conditions,
)
from core.enemy_abilities import load_abilities
from core.game import Game
from entities.enemy import Enemy
from entities.npc import NPC
from entities.player import Player
from states.combat import CombatState


def _game(recording_io):
    player = Player("Condition Tester", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def test_apply_condition_and_refresh_duration(recording_io):
    player, game = _game(recording_io)

    assert apply_condition(player, "burning", turns=2, game=game) is True
    assert player.conditions["burning"]["turns"] == 2

    assert apply_condition(player, "burning", turns=4, game=game) is True
    assert player.conditions["burning"]["turns"] == 4
    assert "Burning lingers." in recording_io.text


def test_condition_ticks_damage_and_expires(recording_io, monkeypatch):
    player, game = _game(recording_io)
    monkeypatch.setattr(Player, "saving_throw", lambda self, *args, **kwargs: False)
    apply_condition(player, "burning", turns=2, game=game)
    recording_io.clear()

    tick_conditions(player, game)

    assert player.hp == 47
    assert player.conditions["burning"]["turns"] == 1

    tick_conditions(player, game)

    assert player.hp == 44
    assert "burning" not in player.conditions
    assert "Burning fades." in recording_io.text


def test_successful_save_ends_a_condition(recording_io, monkeypatch):
    player, game = _game(recording_io)
    monkeypatch.setattr(Player, "saving_throw", lambda self, *args, **kwargs: True)
    apply_condition(player, "frightened", turns=3, game=game)
    recording_io.clear()

    tick_conditions(player, game)

    assert "frightened" not in player.conditions
    assert "You recover from Frightened." in recording_io.text


def test_frightened_grants_disadvantage_on_checks_and_saves(recording_io):
    player, game = _game(recording_io)
    apply_condition(player, "frightened", game=game)

    assert player.roll_flags("check") == (False, True)
    assert player.roll_flags("save") == (False, True)
    assert player.roll_flags("attack") == (False, False)


def test_weakened_reduces_weapon_damage(recording_io):
    player, game = _game(recording_io)
    enemy = Enemy("Training Dummy", hp=50, defense=0)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    apply_condition(player, "weakened", game=game)
    combat.dice_d20.roll = lambda: 10  # hit, no critical
    before = enemy.hp

    combat._manage_attack(player, game)

    expected = max(1, player.strength - 2)
    assert enemy.hp == before - expected
    assert "weakened state reduces" in recording_io.text
    assert condition_damage_modifier(player) == -2


def test_dark_bolt_frightens_on_a_failed_save(recording_io, monkeypatch):
    player, game = _game(recording_io)
    enemy = NPC("Hooded Cultist A")
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    ability = load_abilities(["dark_bolt"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert player.conditions["frightened"]["turns"] == 3


def test_dark_bolt_successful_save_does_not_frighten(recording_io, monkeypatch):
    player, game = _game(recording_io)
    enemy = NPC("Hooded Cultist A")
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    ability = load_abilities(["dark_bolt"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 20)

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert "frightened" not in player.conditions


def test_shield_bash_applies_weakened_on_a_failed_save(recording_io, monkeypatch):
    player, game = _game(recording_io)
    enemy = NPC("Iron Sentinel")
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    ability = load_abilities(["shield_bash"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert player.conditions["weakened"]["turns"] == 3


def test_flame_breath_applies_burning(recording_io, monkeypatch):
    player, game = _game(recording_io)
    enemy = Enemy("Dragon", monster_type="young_dragon")
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    ability = load_abilities(["flame_breath"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)
    before = player.hp

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert player.hp == before - 12
    assert player.conditions["burning"]["turns"] == 3
    assert "You are burning!" in recording_io.text


def test_end_of_turn_ticks_conditions(recording_io, monkeypatch):
    player, game = _game(recording_io)
    enemy = Enemy("Training Dummy", hp=10)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    apply_condition(player, "burning", turns=2, game=game)
    monkeypatch.setattr(Player, "saving_throw", lambda self, *args, **kwargs: False)
    before = player.hp

    combat._phase_end_turn(player, game)

    assert player.hp == before - 3
    assert player.conditions["burning"]["turns"] == 1
    assert combat.turn == 2


def test_conditions_survive_player_round_trip(recording_io):
    player, game = _game(recording_io)
    apply_condition(player, "burning", turns=2, game=game)
    apply_condition(player, "frightened", turns=3, game=game)

    restored = Player.from_dict(player.to_dict())

    assert restored.conditions["burning"] == {"turns": 2}
    assert restored.conditions["frightened"] == {"turns": 3}


def test_unknown_conditions_are_ignored(recording_io):
    player, game = _game(recording_io)

    assert apply_condition(player, "not_a_condition", game=game) is False
    assert "not_a_condition" not in player.conditions
    assert tick_conditions(player, game) == []
