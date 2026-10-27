from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from items.interactive_object import Chest, Door
from items.item import Item
from items.keys import key_opens
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


def test_poison_damages_the_opponent_over_time(recording_io):
    player, enemy, game, combat = _combat_game(recording_io, enemy_hp=50)
    poison = Item("Spider Poison", "poison", {"damage": 5, "duration": 3})
    player.add_item(poison)
    before = enemy.hp

    assert poison.use(player, game) is True
    assert "Spider Poison" not in _names(player)
    assert enemy.hp == before
    assert combat.effects["poison"] == {"damage": 5, "turns": 3}

    combat._phase_end_turn(player, game)

    assert enemy.hp == before - 5
    assert combat.effects["poison"]["turns"] == 2


def test_poison_expires_after_its_duration(recording_io):
    player, enemy, game, combat = _combat_game(recording_io, enemy_hp=50)
    poison = Item("Spider Poison", "poison", {"damage": 5, "duration": 3})
    player.add_item(poison)
    before = enemy.hp

    poison.use(player, game)
    for _ in range(3):
        combat._phase_end_turn(player, game)

    assert enemy.hp == before - 15
    assert "poison" not in combat.effects


def test_keys_only_open_declared_locks():
    rusty = Item("Rusty Key", "key", {"opens": ["Treasure Chest"]})
    skeleton = Item("Skeleton Key", "key", {"opens": ["*"]})

    assert key_opens(rusty, "Treasure Chest") is True
    assert key_opens(rusty, "Cellar Door") is False
    assert key_opens(skeleton, "Any Lock") is True


def test_locked_chest_requires_a_matching_key_and_adds_contents(recording_io):
    player = _player()
    game = Game(player, None, recording_io, temporary=True)
    chest = Chest(
        "Treasure Chest",
        requires_key=True,
        content=[Item("Golden Ring", "accessory", {"charisma": 1}, 30)],
    )
    player.add_item(Item("Common Key", "key", {}, 1))

    chest.interact(player, game)

    assert chest.state == "closed"
    assert "Golden Ring" not in _names(player)

    player.add_item(Item("Rusty Key", "key", {"opens": ["Treasure Chest"]}, 5))
    chest.interact(player, game)

    assert chest.state == "open"
    assert "Golden Ring" in _names(player)
    assert chest.content == []


def test_locked_door_requires_a_matching_key(recording_io):
    player = _player()
    game = Game(player, None, recording_io, temporary=True)
    door = Door("Cellar Door", requires_key=True, destination_position="cellar")
    player.add_item(Item("Rusty Key", "key", {"opens": ["Treasure Chest"]}, 5))

    door.interact(player, game)
    assert door.state == "closed"

    player.add_item(Item("Cellar Key", "key", {"opens": ["Cellar Door"]}, 10))
    door.interact(player, game)

    assert door.state == "open"


def test_using_a_key_unlocks_an_adjacent_lock(recording_io):
    player = _player()
    game = Game(player, None, recording_io, temporary=True)
    game.player.set_position("tavern", 5, 5)
    chest = Chest("Treasure Chest", requires_key=True, content=[])
    game.map_manager.get_map("tavern").add_item(chest, 5, 6)
    key = Item("Rusty Key", "key", {"opens": ["Treasure Chest"]}, 5)
    player.add_item(key)

    assert key.use(player, game) is True
    assert chest.state == "open"


def test_antidote_heals_and_clears_poison(recording_io):
    player = _player()
    player.hp = 1
    player.conditions["poison"] = {"turns": 3}
    antidote = Item("Antidote", "heal", {"heal": 5, "remove_poison": True})
    player.add_item(antidote)
    game = Game(player, None, recording_io, temporary=True)

    assert antidote.use(player, game) is True

    assert player.hp == 6
    assert "poison" not in player.conditions
    assert "neutralizes the poison" in recording_io.text


def test_spider_poison_ticks_on_the_player_and_antidote_clears_it(recording_io):
    player = _player()
    enemy = Enemy("Giant Spider", monster_type="giant_spider")
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)

    combat.dice_d20.roll = lambda: 15  # hit, no critical
    combat._attack_enemy(player, game)

    assert "poison" in player.conditions
    before = player.hp
    combat._tick_player_poison(player, game)
    assert player.hp == before - 2

    antidote = Item("Antidote", "heal", {"heal": 5, "remove_poison": True})
    player.add_item(antidote)
    assert antidote.use(player, game) is True

    assert "poison" not in player.conditions


def test_initiative_accessory_changes_the_player_total():
    player = _player()
    base = player.initiative
    boots = Item("Boots of Speed", "accessory", {"initiative": 2})
    player.add_item(boots)

    boots.equip(player, None)
    assert player.initiative == base + 2

    boots.remove(player, None)
    assert player.initiative == base


def test_faster_enemy_acts_first(recording_io):
    player = _player()
    enemy = Enemy("Swift Enemy", hp=10, strength_base=10)
    enemy.dexterity_base = 30
    enemy.modifier_dexterity = enemy.calculate_modifier(30)
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)

    combat.run(game)

    assert combat.phase == "enemy_attack"
    assert "seizes the initiative" in recording_io.text


def test_smoke_bomb_can_escape_combat(recording_io):
    player, _, game, combat = _combat_game(recording_io)
    bomb = Item("Smoke Bomb", "bomb", {"escape": True})
    player.add_item(bomb)
    # A d20 roll of 5 plus the bomb's +5 bonus reaches the DC 10 escape check.
    combat.dice_d20.roll = lambda: 5

    assert bomb.use(player, game) is True

    assert game.current_state() is None
    assert "Smoke Bomb" not in _names(player)
