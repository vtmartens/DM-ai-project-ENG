"""Enemy and NPC abilities, cooldowns and their combat effects."""

from core.enemy_abilities import choose_ability, load_abilities
from core.game import Game
from entities.enemy import Enemy
from entities.npc import NPC
from entities.player import Player
from states.combat import CombatState


def _combat(recording_io, enemy):
    player = Player("Ability Target", "fighter")
    player.defense = 0
    player.hp = 50
    player.hp_max = 50
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    return player, game, combat


def test_monsters_and_npcs_load_their_abilities():
    assert Enemy("Goblin", monster_type="goblin").ability_ids == ["poison_arrow"]
    assert NPC("Vargas").ability_ids == ["dirty_trick"]
    assert NPC("Iron Sentinel").ability_ids == ["shield_bash", "repair"]


def test_goblin_poison_arrow_damages_poisons_and_starts_cooldown(recording_io):
    enemy = Enemy("Goblin", monster_type="goblin")
    player, game, combat = _combat(recording_io, enemy)
    before = player.hp

    combat._attack_enemy(player, game, enemy, index=0)

    assert "Poison Arrow" in recording_io.text
    assert player.hp == before - 6
    assert player.conditions["poison"] == {"damage": 2, "turns": 3}
    assert combat.ability_cooldowns["0"]["poison_arrow"] == 3


def test_ability_on_cooldown_falls_back_to_a_basic_attack(recording_io):
    enemy = Enemy("Goblin", monster_type="goblin")
    player, game, combat = _combat(recording_io, enemy)
    combat._attack_enemy(player, game, enemy, index=0)
    recording_io.clear()
    before = player.hp

    combat._attack_enemy(player, game, enemy, index=0)

    assert "Poison Arrow" not in recording_io.text
    assert "attacks you" in recording_io.text
    assert player.hp < before


def test_cooldowns_tick_back_to_ready(recording_io):
    enemy = Enemy("Goblin", monster_type="goblin")
    player, game, combat = _combat(recording_io, enemy)
    combat._attack_enemy(player, game, enemy, index=0)

    for _ in range(3):
        combat._tick_enemy_ability_cooldowns()

    recording_io.clear()
    combat._attack_enemy(player, game, enemy, index=0)

    assert "Poison Arrow" in recording_io.text


def test_specter_uses_spectral_touch(recording_io):
    enemy = NPC("Specter")
    player, game, combat = _combat(recording_io, enemy)
    before = player.hp

    combat._attack_enemy(player, game, enemy, index=0)

    assert "Spectral Touch" in recording_io.text
    assert player.hp == before - 7


def test_sentinel_shield_bash_raises_guard_for_the_next_hit(recording_io):
    enemy = NPC("Iron Sentinel")
    player, game, combat = _combat(recording_io, enemy)

    combat._attack_enemy(player, game, enemy, index=0)

    assert "Shield Bash" in recording_io.text
    assert combat.enemy_guard["0"] == 5

    combat.dice_d100.roll = lambda: 100  # no critical
    before_hp = enemy.hp
    combat._manage_attack(player, game)

    assert "guard absorbs" in recording_io.text
    assert "0" not in combat.enemy_guard
    assert enemy.hp < before_hp


def test_sentinel_repairs_when_wounded_but_not_at_full_health(recording_io):
    abilities = load_abilities(["shield_bash", "repair"])
    enemy = NPC("Iron Sentinel")

    assert choose_ability(abilities, {"shield_bash": 2}, enemy) is None

    enemy.hp = 10
    chosen = choose_ability(abilities, {"shield_bash": 2}, enemy)
    assert chosen["id"] == "repair"

    player, game, combat = _combat(recording_io, enemy)
    enemy.hp = 10
    combat.ability_cooldowns["0"] = {"shield_bash": 2}

    combat._attack_enemy(player, game, enemy, index=0)

    assert "Repair" in recording_io.text
    assert enemy.hp == 20
    assert combat.ability_cooldowns["0"]["repair"] == 4


def test_enemy_ability_state_survives_a_round_trip(recording_io):
    enemy = Enemy("Goblin", monster_type="goblin")
    player, game, combat = _combat(recording_io, enemy)
    combat.ability_cooldowns["0"] = {"poison_arrow": 2}
    combat.enemy_guard["0"] = 3

    restored = CombatState.from_dict(combat.to_dict())

    assert restored.ability_cooldowns["0"]["poison_arrow"] == 2
    assert restored.enemy_guard["0"] == 3


def test_an_enemy_without_abilities_uses_a_basic_attack(recording_io):
    enemy = Enemy("Training Dummy", hp=20, strength_base=10)
    player, game, combat = _combat(recording_io, enemy)

    combat._attack_enemy(player, game)

    assert "uses" not in recording_io.text
    assert "attacks you" in recording_io.text
