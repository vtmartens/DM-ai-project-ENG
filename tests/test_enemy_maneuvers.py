"""Enemy-initiated maneuvers and the player's counterplay."""

import core.checks
from core.conditions import (
    apply_condition,
    condition_blocks_abilities,
    condition_stand_up,
)
from core.game import Game
from core.game_state import GameState
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


def _combat(recording_io, enemy):
    player = Player("Counterplay Tester", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    return player, game, combat


def _rolls(monkeypatch, *values):
    rolls = iter(values)
    monkeypatch.setattr(
        core.checks,
        "roll_d20",
        lambda *args, **kwargs: (next(rolls), []),
    )


def test_wolf_trip_knocks_the_player_prone(recording_io, monkeypatch):
    wolf = Enemy("Wolf", monster_type="wolf")
    player, game, combat = _combat(recording_io, wolf)
    combat.dice_d100.roll = lambda: 1
    _rolls(monkeypatch, 20, 1)

    combat._attack_enemy(player, game, wolf)

    assert player.conditions["prone"]["turns"] == 2
    assert "Wolf tries to trip you!" in recording_io.text
    assert "Trip succeeds" in recording_io.text
    assert condition_stand_up(player) == "prone"
    assert combat.ability_cooldowns["0"]["maneuver:trip"] == 2


def test_bandit_shove_staggers_the_player(recording_io, monkeypatch):
    bandit = Enemy("Bandit", monster_type="bandit")
    player, game, combat = _combat(recording_io, bandit)
    combat.dice_d100.roll = lambda: 1
    _rolls(monkeypatch, 20, 1)

    combat._attack_enemy(player, game, bandit)

    assert player.conditions["staggered"]["turns"] == 1
    assert condition_blocks_abilities(player) is True
    assert "Shove succeeds" in recording_io.text


def test_enemy_trip_failure_does_not_apply_prone(recording_io, monkeypatch):
    wolf = Enemy("Wolf", monster_type="wolf")
    player, game, combat = _combat(recording_io, wolf)
    combat.dice_d100.roll = lambda: 1
    _rolls(monkeypatch, 1, 20)

    combat._attack_enemy(player, game, wolf)

    assert "prone" not in player.conditions
    assert "Trip fails" in recording_io.text


def test_enemy_maneuver_is_skipped_while_the_condition_is_active(
    recording_io, monkeypatch
):
    wolf = Enemy("Wolf", monster_type="wolf")
    player, game, combat = _combat(recording_io, wolf)
    apply_condition(player, "prone", turns=2, game=game)
    combat.dice_d100.roll = lambda: 1

    assert combat._choose_enemy_maneuver(wolf, player, 0) is None


def test_stand_up_uses_the_turn_and_clears_prone(recording_io):
    enemy = Enemy("Brute", hp=20)
    player, game, combat = _combat(recording_io, enemy)
    apply_condition(player, "prone", turns=2, game=game)

    combat._manage_stand(player, game)

    assert "prone" not in player.conditions
    assert "You climb back to your feet." in recording_io.text
    assert combat.phase == "enemy_attack"


def test_staggered_blocks_player_abilities(recording_io):
    enemy = Enemy("Brute", hp=20)
    player, game, combat = _combat(recording_io, enemy)
    apply_condition(player, "staggered", turns=1, game=game)

    combat._manage_ability(player, game, "Powerful Blow")

    assert combat.last_ability_used is False
    assert combat.phase == "selection"
    assert "cannot use special abilities" in recording_io.text


def test_stand_up_is_advertised_only_while_prone(recording_io):
    enemy = Enemy("Brute", hp=20)
    player, game, combat = _combat(recording_io, enemy)
    session = GameState(player, None)
    session.game = game

    assert "stand up" not in session.get_combat_state()["available_actions"]

    apply_condition(player, "prone", turns=2, game=game)
    assert "stand up" in session.get_combat_state()["available_actions"]


def test_enemy_maneuvers_survive_an_enemy_round_trip(recording_io):
    wolf = Enemy("Wolf", monster_type="wolf")

    restored = Enemy.from_dict(wolf.to_dict())

    assert restored.maneuvers == ["trip"]
    assert restored.maneuver_chance == 45
