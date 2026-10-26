from core.game import Game
from entities.player import Player
from states.map_selection_state import MapSelectionState
from states.tavern import TavernState


def _new_game(io, state=None):
    game = Game(Player("Aria", "wizard"), state, io)
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
