import pytest

from core.game import Game
from entities.player import Player
from items.item import Item
from states.map_selection_state import MapSelectionState
from states.tavern import TavernState


def _new_game(io, state=None, char_class="wizard"):
    game = Game(Player("Aria", char_class), state, io)
    game.set_initial_map("tavern")
    return game


def test_save_and_load_restore_the_player_and_state(recording_io, tmp_path):
    game = _new_game(recording_io, TavernState())
    game.player.hp = 3
    save_path = tmp_path / "round-trip.json"

    assert game.save(str(save_path)) is True
    assert save_path.exists()

    loaded = Game(None, None, recording_io, temporary=True)
    assert loaded.load(str(save_path)) is True

    assert loaded.player.name == "Aria"
    assert loaded.player.char_class == "wizard"
    assert loaded.player.hp == 3
    assert loaded.player.current_map == "tavern"
    assert type(loaded.current_state()).__name__ == "TavernState"


def test_map_selection_state_survives_a_save_load(recording_io, tmp_path):
    """Regression: MapSelectionState was missing from Game.load's state map."""
    game = _new_game(recording_io, TavernState())
    game.push_state(MapSelectionState())
    save_path = tmp_path / "map-selection.json"

    assert game.save(str(save_path)) is True

    loaded = Game(None, None, recording_io, temporary=True)
    assert loaded.load(str(save_path)) is True
    assert type(loaded.current_state()).__name__ == "MapSelectionState"


def test_save_and_load_restore_mana(recording_io, tmp_path):
    game = _new_game(recording_io, TavernState())
    game.player.mana = 7
    save_path = tmp_path / "mana.json"

    assert game.save(str(save_path)) is True

    loaded = Game(None, None, recording_io, temporary=True)
    assert loaded.load(str(save_path)) is True
    assert loaded.player.mana == 7
    assert loaded.player.mana_max == 20


def test_loading_a_missing_save_returns_false(recording_io, tmp_path):
    game = Game(None, None, recording_io, temporary=True)

    assert game.load(str(tmp_path / "does-not-exist.json")) is False


@pytest.mark.parametrize("char_class", ["fighter", "wizard", "rogue", "cleric"])
def test_save_load_preserves_equipment_level_and_condition_stats(
    recording_io, tmp_path, char_class
):
    game = _new_game(recording_io, TavernState(), char_class=char_class)
    player = game.player
    player.gain_experience(100, game)

    boots = Item("Boots of Speed", "accessory", {"initiative": 2}, 10)
    player.add_item(boots)
    boots.equip(player, game)
    player.conditions["poison"] = {"damage": 2, "turns": 2}
    player.allies.append("Violet")
    player.defeats = 2

    expected = {
        "strength": player.strength,
        "dexterity": player.dexterity,
        "ac": player.armor_class,
        "defense": player.defense,
        "defense_base": player.defense_base,
        "initiative": player.initiative,
        "initiative_base": player.initiative_base,
        "level": player.level,
        "hp_max": player.hp_max,
        "mana_max": player.mana_max,
        "weapon": player.weapon.name if player.weapon else None,
        "armor": player.armor.name if player.armor else None,
        "accessories": [item.name for item in player.accessories],
    }
    save_path = tmp_path / f"{char_class}-stats.json"

    assert game.save(str(save_path)) is True

    first = Game(None, None, recording_io, temporary=True)
    assert first.load(str(save_path)) is True
    loaded = first.player

    assert loaded.strength == expected["strength"]
    assert loaded.dexterity == expected["dexterity"]
    assert loaded.armor_class == expected["ac"]
    assert loaded.defense == expected["defense"]
    assert loaded.defense_base == expected["defense_base"]
    assert loaded.initiative == expected["initiative"]
    assert loaded.initiative_base == expected["initiative_base"]
    assert loaded.level == expected["level"]
    assert loaded.hp_max == expected["hp_max"]
    assert loaded.mana_max == expected["mana_max"]
    assert (loaded.weapon.name if loaded.weapon else None) == expected["weapon"]
    assert (loaded.armor.name if loaded.armor else None) == expected["armor"]
    assert [item.name for item in loaded.accessories] == expected["accessories"]
    assert loaded.conditions == {"poison": {"damage": 2, "turns": 2}}
    assert loaded.allies == ["Violet"]
    assert loaded.defeats == 2

    # A second round trip must not stack the equipment bonuses again.
    second_path = tmp_path / f"{char_class}-stats-round2.json"
    assert first.save(str(second_path)) is True
    second = Game(None, None, recording_io, temporary=True)
    assert second.load(str(second_path)) is True

    assert second.player.strength == expected["strength"]
    assert second.player.armor_class == expected["ac"]
    assert second.player.defense == expected["defense"]
    assert second.player.initiative == expected["initiative"]
