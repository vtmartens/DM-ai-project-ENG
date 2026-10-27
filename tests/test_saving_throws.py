"""Saving throws and the d20 advantage/disadvantage helper."""

import util.dice as dice_module
from core.enemy_abilities import load_abilities
from core.game import Game
from entities.enemy import Enemy
from entities.npc import NPC
from entities.player import Player
from states.ability_check import AbilityCheckState
from states.combat import CombatState
from util.dice import roll_d20


def _game(recording_io):
    player = Player("Save Tester", "fighter")
    player.defense = 0
    player.hp = 50
    player.hp_max = 50
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def test_roll_d20_advantage_keeps_the_higher_die(monkeypatch):
    rolls = iter([3, 17])
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: next(rolls))

    result, dice = roll_d20(advantage=True)

    assert result == 17
    assert dice == [3, 17]


def test_roll_d20_disadvantage_keeps_the_lower_die(monkeypatch):
    rolls = iter([3, 17])
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: next(rolls))

    result, dice = roll_d20(disadvantage=True)

    assert result == 3
    assert dice == [3, 17]


def test_advantage_and_disadvantage_cancel(monkeypatch):
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 11)

    result, dice = roll_d20(advantage=True, disadvantage=True)

    assert result == 11
    assert dice == []


def test_saving_throw_uses_the_modifier_and_reports_the_dc(
    recording_io, monkeypatch
):
    player, game = _game(recording_io)
    # Fighter Constitution 14 gives +2; a roll of 10 is 12 vs DC 12.
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 10)

    assert player.saving_throw("constitution", 12, game) is True
    assert "DC 12: success." in recording_io.text

    recording_io.clear()
    assert player.saving_throw("constitution", 13, game) is False
    assert "DC 13: failure." in recording_io.text


def test_saving_throw_uses_condition_advantage(recording_io, monkeypatch):
    player, game = _game(recording_io)
    player.conditions["advantage"] = True
    rolls = iter([2, 18])
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: next(rolls))

    assert player.saving_throw("dexterity", 15, game) is True

    assert "2 / 18 (advantage)" in recording_io.text
    assert "= 18" in recording_io.text


def test_ability_check_uses_condition_advantage(recording_io, monkeypatch):
    player, game = _game(recording_io)
    player.conditions["advantage"] = True
    rolls = iter([2, 18])
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: next(rolls))

    roll, bonus = AbilityCheckState()._roll_with_guidance(game)

    assert roll == 18
    assert bonus == 0
    assert "Advantage roll: 2 / 18 -> 18." in recording_io.text


def test_poison_arrow_successful_save_halves_damage_and_blocks_poison(
    recording_io, monkeypatch
):
    player, game = _game(recording_io)
    enemy = Enemy("Goblin", monster_type="goblin")
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    ability = load_abilities(["poison_arrow"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 20)
    before = player.hp

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert player.hp == before - 3
    assert "poison" not in player.conditions
    assert "DC 12: success." in recording_io.text
    assert "shrug off the worst" in recording_io.text


def test_poison_arrow_failed_save_applies_full_damage_and_poison(
    recording_io, monkeypatch
):
    player, game = _game(recording_io)
    enemy = Enemy("Goblin", monster_type="goblin")
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    ability = load_abilities(["poison_arrow"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)
    before = player.hp

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert player.hp == before - 6
    assert player.conditions["poison"] == {"damage": 2, "turns": 3}
    assert "DC 12: failure." in recording_io.text


def test_shield_bash_save_halves_damage_and_still_raises_guard(
    recording_io, monkeypatch
):
    player, game = _game(recording_io)
    enemy = NPC("Iron Sentinel")
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    ability = load_abilities(["shield_bash"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 20)
    before = player.hp

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert player.hp == before - 6
    assert combat.enemy_guard["0"] == 5
    assert "raises its guard" in recording_io.text
