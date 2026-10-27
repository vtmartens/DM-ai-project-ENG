"""Blinded, restrained and charmed conditions and their counterplay."""

import core.checks
import util.dice as dice_module
from core.conditions import (
    apply_condition,
    condition_blocks_attack,
    condition_blocks_escape,
    condition_escape_action,
    condition_incoming_roll_flags,
)
from core.enemy_abilities import load_abilities
from core.game import Game
from core.game_state import GameState
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


def _game(recording_io):
    player = Player("Condition Tester", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def _combat(recording_io, enemies):
    player, game = _game(recording_io)
    combat = CombatState(enemies=list(enemies))
    game.push_state(combat)
    return player, game, combat


def test_blinded_penalises_attacks_both_ways(recording_io):
    player, game = _game(recording_io)

    apply_condition(player, "blinded", turns=2, game=game)

    assert player.roll_flags("attack") == (False, True)
    assert player.roll_flags("check") == (False, True)
    assert condition_incoming_roll_flags(player, "attack") == (True, False)


def test_blinded_trap_uses_the_new_condition(recording_io, monkeypatch):
    game = Game(
        Player("Trap Tester", "fighter"),
        None,
        recording_io,
        temporary=True,
    )
    game.set_initial_map("underroad")
    game.player.set_position("underroad", 11, 2)
    game.player.hp = 50
    trap = game.map_manager.get_map("underroad").get_item_at(12, 2)
    trap.hidden = False
    trap.detected = True
    monkeypatch.setattr(
        Player, "saving_throw", lambda self, *args, **kwargs: False
    )

    trap.trigger(game.player, game)

    assert game.player.conditions["blinded"]["turns"] == 2
    assert "You are blinded!" in recording_io.text


def test_restrained_blocks_fleeing_and_offers_break_free(recording_io):
    enemy = Enemy("Web Spinner", hp=30)
    player, game, combat = _combat(recording_io, [enemy])

    apply_condition(player, "restrained", turns=3, game=game)
    action = condition_escape_action(player)

    assert condition_blocks_escape(player) == "restrained"
    assert action is not None
    assert action[0] == "restrained"
    assert action[1]["label"] == "Break Free"
    assert action[1]["skill"] == "athletics"

    combat.dice_d20.roll = lambda: (_ for _ in ()).throw(
        AssertionError("fleeing should not roll while restrained")
    )
    combat._attempt_escape(game)

    assert game.current_state() is combat
    assert "You are restrained and cannot flee." in recording_io.text


def test_break_free_clears_restrained_and_costs_the_turn(
    recording_io, monkeypatch
):
    enemy = Enemy("Web Spinner", hp=30)
    player, game, combat = _combat(recording_io, [enemy])
    apply_condition(player, "restrained", turns=3, game=game)
    _, action = condition_escape_action(player)
    monkeypatch.setattr(
        core.checks, "roll_d20", lambda *args, **kwargs: (20, [])
    )

    combat._manage_escape(player, game, "restrained", action)

    assert "restrained" not in player.conditions
    assert "You tear free of the bonds." in recording_io.text
    assert combat.phase == "enemy_attack"


def test_failed_break_free_leaves_restrained_and_costs_the_turn(
    recording_io, monkeypatch
):
    enemy = Enemy("Web Spinner", hp=30)
    player, game, combat = _combat(recording_io, [enemy])
    apply_condition(player, "restrained", turns=3, game=game)
    _, action = condition_escape_action(player)
    monkeypatch.setattr(
        core.checks, "roll_d20", lambda *args, **kwargs: (1, [])
    )

    combat._manage_escape(player, game, "restrained", action)

    assert player.conditions["restrained"]["turns"] == 3
    assert "the bonds still hold" in recording_io.text
    assert combat.phase == "enemy_attack"


def test_break_free_is_advertised_and_playable(recording_io, monkeypatch):
    enemy = Enemy("Web Spinner", hp=30)
    player, game, combat = _combat(recording_io, [enemy])
    apply_condition(player, "restrained", turns=3, game=game)
    session = GameState(player, None)
    session.game.push_state(combat)
    monkeypatch.setattr(
        core.checks, "roll_d20", lambda *args, **kwargs: (20, [])
    )

    snapshot = session.get_combat_state()
    assert "break free" in snapshot["available_actions"]

    output = session.process_command("break free")

    assert "You tear free of the bonds." in output
    assert "restrained" not in player.conditions


def test_charmed_blocks_attacks_against_its_source_only(recording_io):
    charmer = Enemy("Smuggler Lord", hp=30)
    runner = Enemy("Underroad Runner", hp=30)
    player, game, combat = _combat(recording_io, [charmer, runner])

    apply_condition(
        player,
        "charmed",
        turns=2,
        game=game,
        source=charmer.name,
    )

    assert condition_blocks_attack(player, charmer) == "charmed"
    assert condition_blocks_attack(player, runner) is None

    combat.dice_d20.roll = lambda: 20
    combat._target_index = 0
    before = charmer.hp
    combat._manage_attack(player, game)

    assert charmer.hp == before
    assert "cannot attack Smuggler Lord" in recording_io.text
    assert combat.phase == "selection"

    combat._target_index = 1
    combat._manage_attack(player, game)

    assert runner.hp < before


def test_charmed_blocks_damaging_abilities_against_the_charmer(recording_io):
    charmer = Enemy("Smuggler Lord", hp=30)
    player, game, combat = _combat(recording_io, [charmer])
    apply_condition(
        player,
        "charmed",
        turns=2,
        game=game,
        source=charmer.name,
    )
    before = charmer.hp

    combat._manage_ability(player, game, "Powerful Blow")

    assert charmer.hp == before
    assert combat.last_ability_used is False
    assert "charm prevents you from turning hostile magic" in recording_io.text
    assert combat.phase == "selection"


def test_resist_the_charm_uses_a_wisdom_save(recording_io, monkeypatch):
    charmer = Enemy("Smuggler Lord", hp=30)
    player, game, combat = _combat(recording_io, [charmer])
    apply_condition(
        player,
        "charmed",
        turns=2,
        game=game,
        source=charmer.name,
    )
    _, action = condition_escape_action(player)
    monkeypatch.setattr(
        Player, "saving_throw", lambda self, *args, **kwargs: True
    )

    combat._manage_escape(player, game, "charmed", action)

    assert "charmed" not in player.conditions
    assert "You shake off the charming voice." in recording_io.text
    assert combat.phase == "enemy_attack"


def test_silver_tongue_records_the_charmer_as_its_source(
    recording_io, monkeypatch
):
    charmer = Enemy("Smuggler Lord", monster_type="smuggler_lord")
    player, game, combat = _combat(recording_io, [charmer])
    ability = load_abilities(["silver_tongue"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)

    combat._use_enemy_ability(player, game, charmer, ability, 0)

    assert player.conditions["charmed"]["turns"] == 2
    assert player.conditions["charmed"]["source"] == "Smuggler Lord"
    assert condition_blocks_attack(player, charmer) == "charmed"


def test_charmed_source_survives_a_player_round_trip(recording_io):
    charmer = Enemy("Smuggler Lord", hp=30)
    player, game = _game(recording_io)
    apply_condition(
        player,
        "charmed",
        turns=2,
        game=game,
        source=charmer.name,
    )

    restored = Player.from_dict(player.to_dict())

    assert restored.conditions["charmed"]["source"] == "Smuggler Lord"
    assert condition_blocks_attack(restored, charmer) == "charmed"


def test_spider_web_restrains_and_bandit_powder_blinds(
    recording_io, monkeypatch
):
    spider = Enemy("Giant Spider", monster_type="giant_spider")
    player, game, combat = _combat(recording_io, [spider])
    ability = load_abilities(["web_shot"])[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)

    combat._use_enemy_ability(player, game, spider, ability, 0)

    assert player.conditions["restrained"]["turns"] == 2

    bandit = Enemy("Waystation Bandit", monster_type="bandit")
    powder = load_abilities(["blinding_powder"])[0]
    combat._use_enemy_ability(player, game, bandit, powder, 0)

    assert player.conditions["blinded"]["turns"] == 2
