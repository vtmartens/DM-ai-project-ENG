"""d20 attack rolls, armor class and critical hits."""

import pytest

from core.game import Game
from entities.enemy import Enemy
from entities.entity import Entity
from entities.npc import NPC
from entities.player import Player
from states.combat import CombatState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _combat(recording_io, enemy=None, char_class="fighter"):
    player = Player("Attack Tester", char_class)
    enemy = enemy or Enemy("Training Dummy", hp=50, defense=0)
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    return player, enemy, game, combat


def test_armor_class_combines_dexterity_and_defense():
    entity = Entity("Target", defense=4, dexterity_base=14)

    assert entity.armor_class == 16
    assert entity.ac == 16


def test_player_attack_rolls_against_enemy_armor_class(recording_io):
    player, enemy, game, combat = _combat(recording_io)
    combat.dice_d20.roll = lambda: 10
    before = enemy.hp

    combat._manage_attack(player, game)

    assert enemy.hp == before - player.strength
    assert (
        f"vs {enemy.name}'s AC {enemy.armor_class}: hit."
        in recording_io.text
    )


def test_player_attack_misses_below_armor_class(recording_io):
    enemy = Enemy("Armored Dummy", hp=50, defense=0)
    enemy.armor_class_value = 20
    player, enemy, game, combat = _combat(recording_io, enemy=enemy)
    combat.dice_d20.roll = lambda: 2
    before = enemy.hp

    combat._manage_attack(player, game)

    assert enemy.hp == before
    assert "vs Armored Dummy's AC 20: miss." in recording_io.text
    assert "Your attack misses." in recording_io.text


def test_natural_twenty_is_a_critical_hit(recording_io):
    player, enemy, game, combat = _combat(recording_io)
    combat.dice_d20.roll = lambda: 20
    before = enemy.hp

    combat._manage_attack(player, game)

    assert enemy.hp == before - player.strength * 2
    assert "critical hit (natural 20)" in recording_io.text
    assert "CRITICAL HIT!" in recording_io.text


def test_natural_one_always_misses(recording_io):
    enemy = Enemy("Paper Dummy", hp=50, defense=0)
    enemy.armor_class_value = 1
    player, enemy, game, combat = _combat(recording_io, enemy=enemy)
    combat.dice_d20.roll = lambda: 1
    before = enemy.hp

    combat._manage_attack(player, game)

    assert enemy.hp == before
    assert "miss (natural 1)" in recording_io.text


def test_attack_uses_advantage_from_conditions(recording_io):
    enemy = Enemy("Armored Dummy", hp=50, defense=0)
    enemy.armor_class_value = 18
    player, enemy, game, combat = _combat(recording_io, enemy=enemy)
    player.conditions["advantage"] = True
    rolls = iter([3, 15])
    combat.dice_d20.roll = lambda: next(rolls)
    before = enemy.hp

    combat._manage_attack(player, game)

    assert enemy.hp == before - player.strength
    assert "3 / 15 (advantage)" in recording_io.text


def test_enemy_attack_rolls_against_player_armor_class(recording_io):
    player = Player("Target", "fighter")
    player.defense = 0
    player.armor_class_value = 15
    enemy = Enemy("Brute", hp=30, strength_base=16)
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    combat.dice_d20.roll = lambda: 10
    before = player.hp

    combat._attack_enemy(player, game)

    assert player.hp == before - enemy.strength
    assert "vs your AC 15: hit." in recording_io.text


def test_enemy_attack_can_miss(recording_io):
    player = Player("Target", "fighter")
    player.defense = 0
    player.armor_class_value = 15
    enemy = Enemy("Brute", hp=30, strength_base=16)
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    combat.dice_d20.roll = lambda: 9
    before = player.hp

    combat._attack_enemy(player, game)

    assert player.hp == before
    assert "vs your AC 15: miss." in recording_io.text


def test_enemy_ability_without_a_save_rolls_to_hit(recording_io):
    player = Player("Target", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    enemy = NPC("Specter")
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    combat.dice_d20.roll = lambda: 1
    before = player.hp

    combat._attack_enemy(player, game)

    assert "Spectral Touch" in recording_io.text
    assert player.hp == before
    assert "miss (natural 1)" in recording_io.text


def test_api_exposes_armor_class_attack_bonus_and_enemy_ac(client):
    import server

    started = client.post(
        "/start", json={"name": "AC Tester", "char_class": "fighter"}
    ).get_json()
    session_id = started["session_id"]
    player = server.active_sessions[session_id].game.player

    assert started["player"]["ac"] == player.armor_class
    assert started["player"]["attack_bonus"] == player.attack_bonus
    state = client.get(
        "/state", query_string={"session_id": session_id}
    ).get_json()
    assert state["stats"]["ac"] == player.armor_class
    assert state["stats"]["attack_bonus"] == player.attack_bonus

    client.post("/command", json={"session_id": session_id, "command": "4"})
    client.post("/command", json={"session_id": session_id, "command": "7"})
    combat = client.get(
        "/combat", query_string={"session_id": session_id}
    ).get_json()

    assert combat["in_combat"] is True
    assert combat["enemies"][0]["ac"] == 13
