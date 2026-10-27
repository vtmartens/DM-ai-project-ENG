"""Data-driven combat maneuvers: Trip and Shove."""

import core.checks
from core.conditions import apply_condition
from core.game import Game
from core.game_state import GameState
from core.maneuvers import get_maneuver
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


def _combat(recording_io, enemy):
    player = Player("Maneuver Tester", "fighter")
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


def test_trip_knocks_the_enemy_prone_and_costs_its_action(
    recording_io, monkeypatch
):
    enemy = Enemy("Road Bandit", hp=30, strength_base=12)
    enemy.armor_class_value = 13
    player, game, combat = _combat(recording_io, enemy)
    _rolls(monkeypatch, 18, 3)

    combat._manage_maneuver(player, game, get_maneuver("trip"))

    assert enemy.conditions["prone"]["turns"] == 2
    assert "Road Bandit is knocked prone." in recording_io.text
    assert combat.phase == "enemy_attack"

    before = player.hp
    recording_io.clear()
    combat._attack_enemy(player, game, enemy)

    assert player.hp == before
    assert "prone" not in enemy.conditions
    assert "Road Bandit spends its turn standing up." in recording_io.text
    assert "Road Bandit attacks you" not in recording_io.text


def test_failed_trip_does_not_apply_a_condition(recording_io, monkeypatch):
    enemy = Enemy("Road Bandit", hp=30, strength_base=12)
    player, game, combat = _combat(recording_io, enemy)
    _rolls(monkeypatch, 2, 19)

    combat._manage_maneuver(player, game, get_maneuver("trip"))

    assert "prone" not in enemy.conditions
    assert "Trip fails" in recording_io.text


def test_shove_staggers_the_enemy_and_blocks_abilities(
    recording_io, monkeypatch
):
    enemy = Enemy("Road Bandit", hp=30, strength_base=12)
    enemy.abilities = [
        {
            "id": "test_blast",
            "name": "Test Blast",
            "cooldown": 1,
            "effect": {"type": "attack", "damage": 20},
        }
    ]
    player, game, combat = _combat(recording_io, enemy)
    apply_condition(enemy, "staggered", turns=1, game=game)
    combat.dice_d20.roll = lambda: 1
    recording_io.clear()
    before = player.hp

    combat._attack_enemy(player, game, enemy)

    assert player.hp == before
    assert "Test Blast" not in recording_io.text
    assert "cannot use special abilities" in recording_io.text

    combat._phase_end_turn(player, game)

    assert "staggered" not in enemy.conditions
    assert "Staggered fades from Road Bandit." in recording_io.text


def test_prone_target_is_attacked_with_advantage(recording_io):
    enemy = Enemy("Road Bandit", hp=30, strength_base=12)
    enemy.armor_class_value = 15
    player, game, combat = _combat(recording_io, enemy)
    apply_condition(enemy, "prone", turns=2, game=game)
    rolls = iter([4, 16])
    combat.dice_d20.roll = lambda: next(rolls)
    before = enemy.hp

    combat._manage_attack(player, game)

    assert enemy.hp < before
    assert "4 / 16 (advantage)" in recording_io.text


def test_enemy_conditions_survive_a_combat_round_trip(recording_io):
    enemy = Enemy("Road Bandit", hp=30)
    player, game, combat = _combat(recording_io, enemy)
    apply_condition(enemy, "prone", turns=2, game=game)
    apply_condition(enemy, "staggered", turns=1, game=game)

    restored = CombatState.from_dict(combat.to_dict())

    assert restored.enemies[0].conditions["prone"]["turns"] == 2
    assert restored.enemies[0].conditions["staggered"]["turns"] == 1


def test_npc_conditions_survive_a_round_trip(recording_io):
    from entities.npc import NPC

    npc = NPC("Violet")
    player = Player("Maneuver Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    apply_condition(npc, "prone", turns=2, game=game)

    restored = NPC.from_dict(npc.to_dict())

    assert restored.conditions["prone"]["turns"] == 2


def test_combat_snapshot_advertises_maneuvers_and_enemy_conditions(
    recording_io,
):
    enemy = Enemy("Road Bandit", hp=30)
    player, game, combat = _combat(recording_io, enemy)
    apply_condition(enemy, "prone", turns=2, game=game)
    session = GameState(player, None)
    session.game.push_state(combat)

    snapshot = session.get_combat_state()

    assert {"trip", "shove"} <= set(snapshot["available_actions"])
    assert snapshot["enemies"][0]["conditions"]["prone"]["turns"] == 2


def test_trip_can_be_played_from_the_combat_menu(monkeypatch):
    enemy = Enemy("Road Bandit", hp=30, strength_base=12)
    player = Player("Maneuver Tester", "fighter")
    session = GameState(player, None)
    session.game.push_state(CombatState(enemy=enemy))
    _rolls(monkeypatch, 18, 3)

    output = session.process_command("trip")

    assert "Road Bandit is knocked prone." in output
    assert "Road Bandit spends its turn standing up." in output
    assert "prone" not in enemy.conditions

