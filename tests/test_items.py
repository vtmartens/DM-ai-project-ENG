from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from items.item import Item
from states.combat import CombatState


def _player():
    return Player("Item Tester", "fighter")


def _names(player):
    return [getattr(item, "name", str(item)) for item in player.inventory]


def _combat_game(io, enemy_hp=30):
    player = _player()
    enemy = Enemy("Training Goblin", hp=enemy_hp, damage=1)
    game = Game(player, None, io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    return player, enemy, game, combat


def test_healing_potion_restores_hp_and_is_consumed():
    player = _player()
    player.hp = 1
    potion = Item("Healing Potion", "heal", {"heal": 10}, 25, "")
    player.add_item(potion)
    inventory_size = len(player.inventory)

    assert potion.use(player, None) is True

    assert player.hp == min(player.hp_max, 11)
    assert len(player.inventory) == inventory_size - 1


def test_buff_potion_changes_the_matching_stat():
    player = _player()
    before = player.strength
    potion = Item("Strength Potion", "buff", {"strength": 2}, 30, "")
    player.add_item(potion)

    assert potion.use(player, None) is True

    assert player.strength == before + 2
    assert "Strength Potion" not in _names(player)


def test_buff_potion_with_no_matching_stat_is_not_consumed():
    player = _player()
    potion = Item("Odd Potion", "buff", {"not_a_stat": 2}, 1, "")
    player.add_item(potion)

    assert potion.use(player, None) is False
    assert "Odd Potion" in _names(player)


def test_poison_is_refused_outside_combat(recording_io):
    player = _player()
    poison = Item("Spider Poison", "poison", {"damage": 5, "duration": 3})
    player.add_item(poison)
    game = Game(player, None, recording_io, temporary=True)

    assert poison.use(player, game) is False
    assert "Spider Poison" in _names(player)


def test_poison_damages_the_opponent_in_combat(recording_io):
    player, enemy, game, _ = _combat_game(recording_io)
    poison = Item("Spider Poison", "poison", {"damage": 5, "duration": 3})
    player.add_item(poison)
    before = enemy.hp

    assert poison.use(player, game) is True

    assert enemy.hp < before
    assert "Spider Poison" not in _names(player)


def test_smoke_bomb_can_escape_combat(recording_io):
    player, _, game, combat = _combat_game(recording_io)
    bomb = Item("Smoke Bomb", "bomb", {"escape": True})
    player.add_item(bomb)
    # A d20 roll of 5 plus the bomb's +5 bonus reaches the DC 10 escape check.
    combat.dice_d20.roll = lambda: 5

    assert bomb.use(player, game) is True

    assert game.current_state() is None
    assert "Smoke Bomb" not in _names(player)
