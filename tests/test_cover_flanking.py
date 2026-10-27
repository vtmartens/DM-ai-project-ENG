"""Cover and flanking combat actions."""

from types import SimpleNamespace

from core.game import Game
from core.game_state import GameState
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


def _combat(recording_io, enemy, allies=None):
    player = Player("Formation Tester", "fighter")
    player.hp = 50
    player.hp_max = 50
    player.defense = 0
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    player.set_position("tavern", 1, 1)
    combat = CombatState(enemy=enemy, allies=allies or [])
    game.push_state(combat)
    return player, game, combat


def _ally(name="Ally"):
    return SimpleNamespace(
        name=name,
        hp=10,
        hp_max=10,
        strength=2,
        attack_bonus=1,
        armor_class=10,
        dexterity=0,
    )


def test_take_cover_raises_ac_and_expires(recording_io):
    enemy = Enemy("Brute", hp=30, strength_base=16)
    player, game, combat = _combat(recording_io, enemy)
    player.armor_class_value = 15

    combat._manage_cover(player, game)
    assert combat.effects["cover"] is True
    combat.dice_d20.roll = lambda: 10

    combat._attack_enemy(player, game, enemy)

    assert player.hp == 50
    assert "vs your AC 17 (in cover): miss." in recording_io.text

    combat._phase_end_turn(player, game)
    assert "cover" not in combat.effects


def test_take_cover_requires_nearby_cover(recording_io):
    enemy = Enemy("Brute", hp=30)
    player, game, combat = _combat(recording_io, enemy)
    player.set_position("tavern", 5, 5)

    assert combat.cover_available(game) is False

    combat._manage_cover(player, game)

    assert "cover" not in combat.effects
    assert "no wall or sturdy object nearby" in recording_io.text


def test_cover_grants_advantage_on_dexterity_saves(recording_io, monkeypatch):
    enemy = Enemy("Cultist", hp=20)
    player, game, combat = _combat(recording_io, enemy)
    seen = {}

    def fake_save(
        self,
        ability,
        difficulty,
        game=None,
        advantage=None,
        disadvantage=None,
    ):
        seen["ability"] = ability
        seen["advantage"] = advantage
        return False

    monkeypatch.setattr(Player, "saving_throw", fake_save)
    ability = {
        "name": "Bone Volley",
        "save": {"ability": "dexterity", "dc": 12, "success": "half"},
        "effect": {"type": "attack", "damage": 6},
    }

    combat._use_enemy_ability(player, game, enemy, ability, 0)
    assert seen == {"ability": "dexterity", "advantage": None}

    combat.effects["cover"] = True
    combat._use_enemy_ability(player, game, enemy, ability, 0)
    assert seen == {"ability": "dexterity", "advantage": True}


def test_flanking_grants_two_to_player_attacks(recording_io):
    enemy = Enemy("Dummy", hp=50)
    player, game, combat = _combat(recording_io, enemy, allies=[_ally()])
    enemy.armor_class_value = player.attack_bonus + 11
    combat.dice_d20.roll = lambda: 10
    before = enemy.hp

    combat._manage_attack(player, game)

    assert enemy.hp < before


def test_without_an_ally_the_same_attack_misses(recording_io):
    enemy = Enemy("Dummy", hp=50)
    player, game, combat = _combat(recording_io, enemy)
    enemy.armor_class_value = player.attack_bonus + 11
    combat.dice_d20.roll = lambda: 10
    before = enemy.hp

    combat._manage_attack(player, game)

    assert enemy.hp == before


def test_cover_and_flanking_are_exposed_in_the_combat_snapshot(recording_io):
    enemy = Enemy("Dummy", hp=50)
    player, game, combat = _combat(recording_io, enemy, allies=[_ally()])
    combat.effects["cover"] = True
    session = GameState(player, None)
    session.game = game

    snapshot = session.get_combat_state()

    assert snapshot["effects"]["covering"] is True
    assert snapshot["effects"]["flanking"] is True
    assert "take cover" in snapshot["available_actions"]
