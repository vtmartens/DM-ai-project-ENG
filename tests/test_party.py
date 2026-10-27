"""Ally stances, party commands and party API."""

from types import SimpleNamespace

import pytest

from core.conditions import apply_condition
from core.game import Game
from core.party import (
    ally_stance,
    get_ally_ability,
    party_entries,
    set_ally_stance,
)
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io, stance="attack"):
    player = Player("Party Tester", "fighter")
    player.allies = ["Violet"]
    player.ally_stances = {"Violet": stance}
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def _combat(player, game, enemy):
    ally = SimpleNamespace(
        name="Violet",
        hp=20,
        hp_max=20,
        strength=3,
        attack_bonus=2,
        armor_class=12,
        dexterity=1,
        ally_ability_ids=[
            "field_dressing",
            "antidote",
            "calming_word",
        ],
    )
    combat = CombatState(enemy=enemy, allies=[ally])
    game.push_state(combat)
    return combat


def test_ally_stance_defaults_and_persists(recording_io):
    player, game = _game(recording_io)
    player.ally_stances = {}

    assert ally_stance(player, "Violet") == "attack"
    assert set_ally_stance(player, "Violet", "guard", game) is True
    assert ally_stance(player, "Violet") == "guard"
    assert Player.from_dict(player.to_dict()).ally_stances == {
        "Violet": "guard"
    }


def test_guard_stance_does_not_attack_and_raises_ac(recording_io):
    player, game = _game(recording_io, stance="guard")
    player.armor_class_value = 15
    enemy = Enemy("Brute", hp=30, strength_base=16)
    combat = _combat(player, game, enemy)
    enemy_before = enemy.hp
    combat.dice_d20.roll = lambda: 10

    combat._allies_attack(player, game)
    combat._attack_enemy(player, game, enemy)

    assert enemy.hp == enemy_before
    assert player.hp == player.hp_max
    assert "vs your AC 16 (guarded): miss." in recording_io.text


def test_support_stance_heals_once_per_fight(recording_io):
    player, game = _game(recording_io, stance="support")
    player.hp = 10
    player.hp_max = 50
    player.reputation["violet_watch"] = 20
    enemy = Enemy("Brute", hp=30)
    combat = _combat(player, game, enemy)
    enemy_before = enemy.hp

    combat._allies_attack(player, game)

    assert player.hp == 20
    assert enemy.hp == enemy_before
    assert "Violet uses Field Dressing and restores 10 HP." in recording_io.text

    combat.dice_d20.roll = lambda: 20
    combat._allies_attack(player, game)
    assert player.hp == 20
    assert enemy.hp < enemy_before


def test_support_clears_a_condition_when_health_is_full(recording_io):
    player, game = _game(recording_io, stance="support")
    player.hp = player.hp_max
    apply_condition(player, "weakened", turns=2, game=game)
    enemy = Enemy("Brute", hp=30)
    combat = _combat(player, game, enemy)

    combat._allies_attack(player, game)

    assert "weakened" not in player.conditions
    assert "clears Weakened" in recording_io.text


def test_support_uses_antidote_for_poison(recording_io):
    player, game = _game(recording_io, stance="support")
    apply_condition(player, "poison", turns=2, game=game)
    player.conditions["poison"] = {"damage": 2, "turns": 2}
    enemy = Enemy("Brute", hp=30)
    combat = _combat(player, game, enemy)

    combat._allies_attack(player, game)

    assert "poison" not in player.conditions
    assert "Violet uses Antidote and clears Poison." in recording_io.text
    assert enemy.hp == enemy.hp_max


def test_support_uses_calming_word_for_fear(recording_io):
    player, game = _game(recording_io, stance="support")
    apply_condition(player, "frightened", turns=2, game=game)
    enemy = Enemy("Brute", hp=30)
    combat = _combat(player, game, enemy)

    combat._allies_attack(player, game)

    assert "frightened" not in player.conditions
    assert "Violet uses Calming Word and clears Frightened." in recording_io.text


def test_explicit_ally_ability_command(recording_io):
    player, game = _game(recording_io, stance="attack")
    player.hp = 10
    enemy = Enemy("Brute", hp=30)
    combat = _combat(player, game, enemy)
    ally = combat.allies[0]
    ability = get_ally_ability(ally.ally_ability_ids, "field_dressing")

    assert combat._parse_ally_command(player, "Violet: antidote") == (
        "Violet",
        "antidote",
    )
    assert combat._use_ally_ability(player, ally, ability, game) is True

    assert player.hp == player.hp_max
    assert "uses Field Dressing" in recording_io.text


def test_hostile_ally_refuses_to_act(recording_io):
    player, game = _game(recording_io)
    player.reputation["violet_watch"] = -10
    enemy = Enemy("Brute", hp=30)
    combat = _combat(player, game, enemy)
    before = enemy.hp

    combat._allies_attack(player, game)

    assert enemy.hp == before
    assert "refuses to follow your orders" in recording_io.text
    assert party_entries(player)[0]["will_act"] is False


def test_ally_ability_cooldown_ticks_down(recording_io):
    player, game = _game(recording_io, stance="attack")
    player.hp = 10
    player.reputation["violet_watch"] = 10
    enemy = Enemy("Brute", hp=30)
    combat = _combat(player, game, enemy)
    ally = combat.allies[0]
    ability = get_ally_ability(ally.ally_ability_ids, "field_dressing")

    combat._use_ally_ability(player, ally, ability, game)

    assert combat.ally_ability_cooldowns["Violet:field_dressing"] == 2

    combat._phase_end_turn(player, game)
    assert combat.ally_ability_cooldowns["Violet:field_dressing"] == 1

    combat._phase_end_turn(player, game)
    assert "Violet:field_dressing" not in combat.ally_ability_cooldowns


def test_ally_commands_parse_and_change_stance(recording_io):
    player, game = _game(recording_io)
    combat = _combat(player, game, Enemy("Dummy", hp=20))

    assert combat._parse_ally_command(player, "Violet: guard") == (
        "Violet",
        "guard",
    )
    assert combat._parse_ally_command(player, "Violet support") == (
        "Violet",
        "support",
    )
    assert combat._parse_ally_command(player, "Violet: dance") is None


def test_party_entries_show_stance_and_faction(recording_io):
    player, _ = _game(recording_io, stance="guard")

    entry = party_entries(player)[0]

    assert entry["name"] == "Violet"
    assert entry["stance"] == "guard"
    assert entry["stance_label"] == "Guard"
    assert entry["faction"] == "violet_watch"
    assert entry["hp_max"] > 0


def test_party_api_lists_and_updates_stances(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Party API", "char_class": "fighter"}
    ).get_json()["session_id"]
    session = server.active_sessions[session_id]
    session.game.player.allies = ["Violet"]

    party = client.get(
        "/party", query_string={"session_id": session_id}
    ).get_json()
    assert party["allies"][0]["name"] == "Violet"
    assert party["allies"][0]["stance"] == "attack"

    changed = client.post(
        "/party/stance",
        json={
            "session_id": session_id,
            "ally": "Violet",
            "stance": "support",
        },
    ).get_json()

    assert changed["changed"] is True
    assert changed["party"]["allies"][0]["stance"] == "support"
    assert session.game.player.ally_stances["Violet"] == "support"


def test_combat_snapshot_exposes_ally_stance(recording_io):
    from core.game_state import GameState

    player, game = _game(recording_io, stance="guard")
    combat = _combat(player, game, Enemy("Dummy", hp=20))
    session = GameState(player, None)
    session.game = game

    snapshot = session.get_combat_state()

    assert snapshot["allies"][0]["stance"] == "guard"
    assert snapshot["allies"][0]["stance_label"] == "Guard"
    assert "Violet: guard" in snapshot["available_actions"]
