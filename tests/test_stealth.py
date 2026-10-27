"""Stealth checks, nearby Perception and surprise rounds."""

import core.checks
from core.game import Game
from core.game_state import GameState
from core.stealth import attempt_stealth
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState
from states.commands import handle_targeted_command
from states.map_state import MapState


def _tavern_game(recording_io, char_class="rogue"):
    game = Game(
        Player("Stealth Tester", char_class),
        None,
        recording_io,
        temporary=True,
    )
    game.set_initial_map("tavern")
    return game


def _roll(monkeypatch, value):
    monkeypatch.setattr(
        core.checks,
        "roll_d20",
        lambda *args, **kwargs: (value, []),
    )


def _combat(recording_io, enemy, surprised=False):
    player = Player("Stealth Tester", "rogue")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy, surprised=surprised)
    game.push_state(combat)
    return player, game, combat


def test_hide_succeeds_against_nearby_observers(recording_io, monkeypatch):
    game = _tavern_game(recording_io)
    _roll(monkeypatch, 20)

    assert attempt_stealth(game.player, game) is True

    assert game.player.stealthed is True
    assert "Stealth check:" in recording_io.text
    assert "You slip into the shadows." in recording_io.text


def test_hide_fails_when_an_observer_notices(recording_io, monkeypatch):
    game = _tavern_game(recording_io)
    _roll(monkeypatch, 1)

    assert attempt_stealth(game.player, game) is False

    assert game.player.stealthed is False
    assert "notices you." in recording_io.text


def test_sneak_command_runs_from_the_map_menu(monkeypatch):
    player = Player("Stealth Tester", "rogue")
    session = GameState(player, MapState())
    session.game.set_initial_map("tavern")
    _roll(monkeypatch, 20)

    output = session.process_command("sneak")

    assert "Stealth check:" in output
    assert player.stealthed is True


def test_moving_while_hidden_rerolls_stealth(recording_io, monkeypatch):
    game = _tavern_game(recording_io)
    game.player.stealthed = True
    _roll(monkeypatch, 20)
    MapState()._move_player_position(game, "east")

    assert game.player.stealthed is True
    assert "You stay out of sight." in recording_io.text

    _roll(monkeypatch, 1)
    MapState()._move_player_position(game, "west")

    assert game.player.stealthed is False
    assert "notices you." in recording_io.text


def test_attack_from_stealth_starts_a_surprise_round(recording_io):
    game = _tavern_game(recording_io)
    game.player.stealthed = True

    assert handle_targeted_command(game, "attack", "Durnan") is True

    combat = game.current_state()
    assert isinstance(combat, CombatState)
    assert combat.surprised is True
    assert combat.effects["surprise_attack"] is True
    assert game.player.stealthed is False
    assert "You break cover as you strike." in recording_io.text


def test_surprise_skips_enemy_initiative_and_actions(recording_io):
    enemy = Enemy("Lookout", hp=20, strength_base=16)
    enemy.dexterity_base = 20
    enemy.modifier_dexterity = 5
    player, game, combat = _combat(recording_io, enemy, surprised=True)
    player.initiative = -5
    before = player.hp

    assert combat._check_initiative(player, game) is False
    combat._phase_attack_enemy(player, game)

    assert player.hp == before
    assert combat.surprised is False
    assert combat.phase == "end_turn"
    assert "caught off guard" in recording_io.text


def test_surprise_attack_grants_advantage_once(recording_io):
    enemy = Enemy("Lookout", hp=20)
    enemy.armor_class_value = 15
    player, game, combat = _combat(recording_io, enemy, surprised=True)
    rolls = iter([2, 16])
    combat.dice_d20.roll = lambda: next(rolls)

    combat._manage_attack(player, game)

    assert "2 / 16 (advantage)" in recording_io.text
    assert "surprise_attack" not in combat.effects


def test_player_stealth_survives_a_round_trip(recording_io):
    player = Player("Stealth Tester", "rogue")
    player.stealthed = True

    restored = Player.from_dict(player.to_dict())

    assert restored.stealthed is True


def test_combat_surprise_survives_a_round_trip(recording_io):
    player, game, combat = _combat(
        recording_io,
        Enemy("Lookout", hp=20),
        surprised=True,
    )

    restored = CombatState.from_dict(combat.to_dict())

    assert restored.surprised is True
    assert restored.effects["surprise_attack"] is True


def test_state_exposes_stealth_and_surprised_enemies(recording_io):
    game = _tavern_game(recording_io)
    game.player.stealthed = True
    session = GameState(game.player, None)
    session.game = game

    state = session.get_current_state()
    assert state["stealthed"] is True

    combat = CombatState(enemy=Enemy("Lookout", hp=20), surprised=True)
    game.push_state(combat)
    snapshot = session.get_combat_state()

    assert snapshot["surprised"] is True
    assert snapshot["enemies"][0]["surprised"] is True
