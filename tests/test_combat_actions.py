"""Defend and Aim combat actions."""

import pytest

from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _combat(recording_io, enemy):
    player = Player("Action Tester", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    return player, game, combat


def test_defend_raises_ac_until_the_end_of_the_round(recording_io):
    player = Player("Action Tester", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    player.armor_class_value = 15
    enemy = Enemy("Brute", hp=30, strength_base=16)
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    combat.dice_d20.roll = lambda: 10  # 15 + 5: hits AC 15, misses AC 19
    before = player.hp

    combat._manage_defend(player, game)
    assert combat.effects["defend"] is True
    combat._attack_enemy(player, game)

    assert player.hp == before
    assert "vs your AC 19 (defending): miss." in recording_io.text

    combat._phase_end_turn(player, game)
    assert "defend" not in combat.effects


def test_aim_grants_advantage_and_is_consumed_by_the_next_attack(recording_io):
    enemy = Enemy("Armored Dummy", hp=50, defense=0)
    enemy.armor_class_value = 18
    player, game, combat = _combat(recording_io, enemy)
    rolls = iter([3, 15])
    combat.dice_d20.roll = lambda: next(rolls)
    before = enemy.hp

    combat._manage_aim(player, game)
    assert combat.effects["aim"] is True

    combat._manage_attack(player, game)

    assert "aim" not in combat.effects
    assert enemy.hp == before - player.strength
    assert "3 / 15 (advantage)" in recording_io.text


def test_aim_and_defend_are_advertised_and_aim_is_exposed(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Action API", "char_class": "fighter"}
    ).get_json()["session_id"]
    client.post("/command", json={"session_id": session_id, "command": "4"})
    client.post("/command", json={"session_id": session_id, "command": "7"})
    actions = client.get(
        "/available_actions", query_string={"session_id": session_id}
    ).get_json()["actions"]
    assert {"defend", "aim"} <= set(actions)

    result = client.post(
        "/combat_action",
        json={"session_id": session_id, "action": "aim"},
    ).get_json()

    assert "next attack has advantage" in "\n".join(
        message["text"] for message in result["output"]
    )
    assert result["combat"]["effects"]["aiming"] is True
    session = server.active_sessions[session_id]
    assert session.game.current_state().effects["aim"] is True
