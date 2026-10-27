"""Finesse and ranged weapon properties."""

from core.game import Game
from core.item_catalogue import item_definition
from core.shop import shop_stock
from entities.enemy import Enemy
from entities.player import Player
from items.item import Item
from states.combat import CombatState


def _weapon(name):
    definition = item_definition(name)
    assert definition is not None
    return Item.from_dict(definition)


def test_ranged_weapon_uses_dexterity_for_attack_and_damage():
    player = Player("Archer", "fighter")
    bow = _weapon("Short Bow")
    player.add_item(bow)
    bow.equip(player)

    assert bow.properties["ranged"] is True
    assert player.attack_ability() == "dexterity"
    assert player.attack_modifier == player.dexterity
    assert player.attack_damage_modifier == player.dexterity + 4
    assert player.attack_bonus == player.dexterity + player.proficiency_bonus


def test_finesse_weapon_uses_the_better_of_strength_and_dexterity():
    rogue = Player("Rogue", "rogue")
    assert rogue.attack_ability() == "dexterity"
    assert rogue.attack_modifier == rogue.dexterity
    assert rogue.attack_damage_modifier == rogue.dexterity

    fighter = Player("Fighter", "fighter")
    assert fighter.attack_ability() == "strength"
    assert fighter.attack_modifier == fighter.strength


def test_melee_weapon_without_properties_uses_strength():
    player = Player("Swordfighter", "fighter")
    sword = _weapon("Long Sword")
    player.add_item(sword)
    sword.equip(player)

    assert player.attack_ability() == "strength"
    assert player.attack_modifier == player.strength
    assert player.attack_damage_modifier == player.strength


def test_mage_staff_uses_intelligence_and_attack_log_shows_the_stat(
    recording_io,
):
    player = Player("Mage", "wizard")
    enemy = Enemy("Dummy", hp=30, defense=0)
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    combat.dice_d20.roll = lambda: 10
    before = enemy.hp

    assert player.attack_ability() == "intelligence"
    combat._manage_attack(player, game)

    assert enemy.hp == before - player.attack_damage_modifier
    assert "(INT)" in recording_io.text
    assert "vs Dummy's AC" in recording_io.text


def test_weapon_properties_survive_item_and_player_round_trips():
    player = Player("Archer", "fighter")
    bow = _weapon("Short Bow")
    player.add_item(bow)
    bow.equip(player)

    restored_item = Item.from_dict(bow.to_dict())
    restored_player = Player.from_dict(player.to_dict())

    assert restored_item.properties == bow.properties
    assert restored_player.attack_ability() == "dexterity"
    assert restored_player.attack_damage_modifier == player.attack_damage_modifier


def test_shop_stock_exposes_weapon_properties():
    stock = {entry["name"]: entry for entry in shop_stock()}

    bow = stock["Short Bow"]
    assert bow["properties"]["ranged"] is True
    assert bow["properties"]["attack_stat"] == "dexterity"
    assert bow["properties"]["damage_bonus"] == 4
    assert "ranged" in bow["properties_text"]
    assert "DEX attack" in bow["properties_text"]
    assert "+4 damage" in bow["properties_text"]
