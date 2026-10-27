"""Post-campaign Rune Trials: waves, boons, persistence and rewards."""

from types import SimpleNamespace

from core.conditions import apply_condition
from core.game import Game
from core.trials import (
    apply_boon,
    build_trial_wave,
    get_boon,
    max_waves,
    modifier_definition,
    wave_definition,
)
from entities.player import Player
from states.rune_trials import RuneTrialsState
from states.sanctum import SanctumState
from tests.helpers import RecordingIO


class ScriptedIO(RecordingIO):
    def __init__(self, replies):
        super().__init__()
        self.replies = iter(replies)

    def request_input(self, prompt=""):
        self.last_input = next(self.replies, "")
        self.messages.append({"type": "prompt", "text": prompt})
        return self.last_input


def _game(recording_io, cleared=True):
    player = Player("Trial Tester", "fighter")
    player.hp = 50
    player.hp_max = 50
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("sanctum")
    if cleared:
        player.cleared_areas = ["sanctum"]
    return player, game


def test_sanctum_unlocks_the_rune_trials(recording_io):
    player, game = _game(recording_io, cleared=False)
    state = SanctumState(game)
    game.push_state(state)

    assert state._enter_trials(game) is False

    player.cleared_areas = ["sanctum"]
    assert state._enter_trials(game) is True
    assert isinstance(game.current_state(), RuneTrialsState)


def test_trial_waves_and_modifiers_are_data_driven():
    assert max_waves() == 5
    first = build_trial_wave(1)
    final = build_trial_wave(5)

    assert first is not None
    assert first["modifier"]["name"] == "Empowered"
    gate_sentinels = [
        enemy for enemy in first["enemies"] if "Sentinel" in enemy.name
    ]
    assert gate_sentinels[0].hp_max == 31
    assert gate_sentinels[0].damage_bonus == 2

    assert final is not None
    assert len(final["enemies"]) == 3
    assert final["enemies"][0].maneuvers == ["trip", "shove"]
    assert wave_definition(6) is None
    assert modifier_definition("warded")["enemy_ac_bonus"] == 1


def test_boons_restore_resources_and_cleanse(recording_io):
    player, game = _game(recording_io)
    player.hp = 10
    player.mana = 0
    player.mana_max = 20
    apply_condition(player, "weakened", turns=3, game=game)

    apply_boon(player, get_boon("mend"), game)
    apply_boon(player, get_boon("focus"), game)
    apply_boon(player, get_boon("cleanse"), game)

    assert player.hp == 35
    assert player.mana == 15
    assert player.conditions == {}
    assert "Mend: recovered 25 HP." in recording_io.text


def test_wave_victory_advances_to_a_boon(recording_io):
    player, game = _game(recording_io)
    state = RuneTrialsState(game)
    game.push_state(state)

    assert state._start_wave(game) is None
    combat = game.current_state()
    for enemy in combat.enemies:
        enemy.hp = 0

    assert combat._check_end_combat(game) is True

    assert combat.outcome == "victory"
    assert isinstance(game.current_state(), RuneTrialsState)
    assert state.phase == "boon"
    assert player.rune_trials_best == 1
    assert player.rune_shards == 2
    assert "Choose a boon" in recording_io.text


def test_boon_choice_advances_the_wave():
    io = ScriptedIO(["1"])
    player = Player("Trial Tester", "fighter")
    player.hp = 10
    player.hp_max = 50
    game = Game(player, None, io, temporary=True)
    game.set_initial_map("sanctum")
    state = RuneTrialsState(game)
    game.push_state(state)
    state.phase = "boon"

    state._boon_menu(game)

    assert state.wave == 2
    assert state.phase == "menu"
    assert state.boons == ["mend"]
    assert player.hp == 35


def test_fleeing_ends_the_run_without_losing_best_depth(recording_io):
    player, game = _game(recording_io)
    state = RuneTrialsState(game)
    game.push_state(state)
    player.rune_trials_best = 2
    state.wave = 3
    state.active_combat = SimpleNamespace(outcome="fled")

    state.resume(game)

    assert state.wave == 1
    assert state.boons == []
    assert state.phase == "menu"
    assert player.rune_trials_best == 2
    assert "run is over" in recording_io.text


def test_completing_all_waves_grants_rewards_and_achievements(recording_io):
    player, game = _game(recording_io)
    state = RuneTrialsState(game)
    game.push_state(state)
    state.wave = max_waves()
    before_gold = player.gold

    state._complete_wave(game)

    assert state.wave == max_waves() + 1
    assert player.rune_trials_best == max_waves()
    assert player.rune_trials_runs == 1
    assert player.gold == before_gold + 250
    assert player.rune_shards == 10
    assert "rune_trials_adept" in player.achievements
    assert "rune_trials_champion" in player.achievements


def test_trial_state_and_best_depth_survive_round_trips(recording_io):
    player, game = _game(recording_io)
    state = RuneTrialsState(game)
    state.wave = 3
    state.boons = ["mend", "focus"]
    state.phase = "boon"
    player.rune_trials_best = 4

    restored_state = RuneTrialsState.from_dict(state.to_dict(), game)
    restored_player = Player.from_dict(player.to_dict())

    assert restored_state.wave == 3
    assert restored_state.boons == ["mend", "focus"]
    assert restored_state.phase == "boon"
    assert restored_player.rune_trials_best == 4


def test_trial_quick_actions_follow_the_phase(recording_io):
    player, game = _game(recording_io)
    state = RuneTrialsState(game)

    assert {"begin", "leave"} <= set(state.available_actions(game))

    state.phase = "boon"
    actions = set(state.available_actions(game))
    assert {"mend", "focus", "cleanse", "leave"} <= actions

    state.phase = "menu"
    state.wave = max_waves() + 1
    assert {"restart", "leave"} <= set(state.available_actions(game))
