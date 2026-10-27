"""Elite monster variants, encounter flags and their combat abilities."""

import util.dice as dice_module
from core.encounters import build_encounter, encounter_catalogue
from core.game import Game
from core.game_state import GameState
from core.wilderness import _candidates
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


def _combat(recording_io, enemy):
    player = Player("Elite Tester", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    return player, game, combat


def test_elite_monsters_load_and_survive_a_round_trip():
    hexer = Enemy("Goblin Hexer", monster_type="goblin_hexer")
    berserker = Enemy("Orc Berserker", monster_type="orc_berserker")
    champion = Enemy("Risen Champion", monster_type="risen_champion")
    enforcer = Enemy("Smuggler Enforcer", monster_type="smuggler_enforcer")
    goblin = Enemy("Goblin", monster_type="goblin")

    assert hexer.elite is True
    assert berserker.elite is True
    assert champion.elite is True
    assert enforcer.elite is True
    assert goblin.elite is False
    assert Enemy.from_dict(hexer.to_dict()).elite is True


def test_elite_encounters_are_flagged_and_rewarded():
    for encounter_id in (
        "goblin_warband",
        "orc_raiders",
        "restless_dead",
        "underroad_enforcers",
    ):
        encounter = build_encounter(encounter_id)
        assert encounter["elite"] is True, encounter_id
        assert any(enemy.elite for enemy in encounter["enemies"]), encounter_id
        assert encounter["reward"]["gold"] > 0, encounter_id
        assert encounter["reward"]["experience"] > 0, encounter_id


def test_elite_flag_reaches_the_combat_snapshot(recording_io):
    encounter = build_encounter("goblin_warband")
    player = Player("Elite Snapshot", "fighter")
    combat = CombatState(
        enemies=encounter["enemies"], encounter=encounter
    )
    session = GameState(player, None)
    session.game.push_state(combat)

    snapshot = session.get_combat_state()

    assert snapshot["enemies"][0]["elite"] is True
    assert snapshot["enemies"][1]["elite"] is False


def test_hex_bolt_blinds_on_a_failed_save(recording_io, monkeypatch):
    enemy = Enemy("Goblin Hexer", monster_type="goblin_hexer")
    player, game, combat = _combat(recording_io, enemy)
    ability = enemy.abilities[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert "blinded" in player.conditions
    assert player.conditions["blinded"]["turns"] == 2


def test_reckless_cleave_weakens_on_a_failed_save(recording_io, monkeypatch):
    enemy = Enemy("Orc Berserker", monster_type="orc_berserker")
    player, game, combat = _combat(recording_io, enemy)
    ability = enemy.abilities[0]
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert "weakened" in player.conditions
    assert player.conditions["weakened"]["turns"] == 2


def test_grave_guard_frightens_and_raises_a_guard(recording_io, monkeypatch):
    enemy = Enemy("Risen Champion", monster_type="risen_champion")
    player, game, combat = _combat(recording_io, enemy)
    ability = next(
        entry for entry in enemy.abilities if entry["id"] == "grave_guard"
    )
    monkeypatch.setattr(dice_module.Dice, "roll", lambda self: 1)

    combat._use_enemy_ability(player, game, enemy, ability, 0)

    assert "frightened" in player.conditions
    assert combat.enemy_guard["0"] == 5


def test_new_road_encounters_unlock_by_level():
    player = Player("Road Tester", "fighter")
    low = _candidates(player)
    assert "goblin_warband" not in low
    assert "underroad_enforcers" not in low
    assert "orc_raiders" not in low

    player.level = 3
    level_three = _candidates(player)
    assert "goblin_warband" in level_three
    assert "underroad_enforcers" not in level_three
    assert "orc_raiders" not in level_three

    player.level = 4
    level_four = _candidates(player)
    assert "underroad_enforcers" in level_four
    assert "orc_raiders" not in level_four

    player.level = 5
    level_five = _candidates(player)
    assert "orc_raiders" in level_five


def test_elite_encounters_are_in_the_tavern_catalogue():
    catalogue = encounter_catalogue("tavern")

    assert {
        "goblin_warband",
        "orc_raiders",
        "restless_dead",
        "underroad_enforcers",
    } <= set(catalogue)
