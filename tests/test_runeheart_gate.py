"""The Runeheart Gate epilogue and its Runeheart-choice branches."""

from core.encounters import build_encounter
from core.game import Game
from core.quests import start_quest
from entities.player import Player
from states.combat import CombatState
from states.runeheart_gate import RuneheartGateState
from states.sanctum import SanctumState


def _game(recording_io, choice="mirt", sanctum_looted=True):
    player = Player("Gate Tester", "fighter")
    player.level = 10
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("sanctum")
    player.cleared_areas = ["underroad", "sanctum"]
    player.claimed_rewards = ["sanctum_ward"]
    if sanctum_looted:
        player.claimed_rewards.append("sanctum_vault")
        player.claimed_rewards.append(f"runeheart_{choice}")
    return player, game


def test_runeheart_gate_map_and_encounters_are_defined(recording_io):
    player = Player("Map Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    gate_map = game.map_manager.get_map("runeheart_gate")
    wardens = build_encounter("runeheart_wardens")
    sovereign = build_encounter("runeheart_sovereign")

    assert gate_map is not None
    assert gate_map.player_start_position == (2, 7)
    assert wardens.get("clears_area") is None
    assert wardens["grants_flag"] == "runeheart_gate_wardens"
    assert sovereign["clears_area"] == "runeheart_gate"
    assert [enemy.name for enemy in sovereign["enemies"]][0] == (
        "Runeheart Sovereign"
    )


def test_sanctum_opens_the_gate_only_after_the_runeheart_is_claimed(
    recording_io,
):
    player, game = _game(recording_io, sanctum_looted=False)
    state = SanctumState(game)
    game.push_state(state)

    assert state._enter_runeheart_gate(game) is False
    assert "gate" not in state.available_actions(game)

    player.claimed_rewards.append("sanctum_vault")
    assert "gate" in state.available_actions(game)
    assert state._enter_runeheart_gate(game) is True
    assert isinstance(game.current_state(), RuneheartGateState)


def test_entering_the_gate_starts_the_epilogue_quest(recording_io):
    player, game = _game(recording_io)
    state = RuneheartGateState(game)
    game.push_state(state)

    state._ensure_map(game)
    state._ensure_quest(game)

    assert any(
        quest.get("id") == "runeheart_gate"
        for quest in player.active_quests
    )
    assert player.current_map == "runeheart_gate"


def test_mirt_branch_adds_his_factor_to_the_boss_fight(recording_io):
    player, game = _game(recording_io, choice="mirt")
    state = RuneheartGateState(game)
    game.push_state(state)

    assert state._confront_sovereign(game, "mirt") is True
    combat = game.current_state()
    assert isinstance(combat, CombatState)
    assert "Mirt's Factor" in [ally.name for ally in combat.allies]
    assert any(
        enemy.name == "Runeheart Sovereign" for enemy in combat.enemies
    )


def test_violet_branch_heals_and_adds_a_watch_medic(recording_io):
    player, game = _game(recording_io, choice="violet")
    player.hp = 2
    player.conditions["poison"] = {"damage": 2, "turns": 2}
    state = RuneheartGateState(game)
    game.push_state(state)

    assert state._confront_sovereign(game, "violet") is True
    combat = game.current_state()

    assert player.hp == player.hp_max
    assert player.conditions == {}
    assert "Watch Medic" in [ally.name for ally in combat.allies]


def test_kept_branch_adds_a_third_echo(recording_io):
    player, game = _game(recording_io, choice="kept")
    state = RuneheartGateState(game)
    game.push_state(state)

    assert state._confront_sovereign(game, "kept") is True
    combat = game.current_state()

    assert len(combat.enemies) == 4
    assert [enemy.name for enemy in combat.enemies].count(
        "Runeheart Echo C"
    ) == 1


def test_warden_victory_sets_the_gate_progress_flag(recording_io):
    player, game = _game(recording_io)
    state = RuneheartGateState(game)
    game.push_state(state)
    encounter = build_encounter("runeheart_wardens")
    combat = CombatState(
        enemies=encounter["enemies"], encounter=encounter
    )

    assert combat._grant_encounter_reward(game) is True

    assert "runeheart_gate_wardens" in player.claimed_rewards
    assert state._wardens_cleared(player) is True


def test_sovereign_victory_completes_the_epilogue(recording_io):
    player, game = _game(recording_io, choice="mirt")
    player.claimed_rewards.append("runeheart_gate_wardens")
    player.gold = 0
    state = RuneheartGateState(game)
    game.push_state(state)
    state._ensure_quest(game)
    state._confront_sovereign(game, "mirt")
    combat = game.current_state()
    for enemy in combat.enemies:
        enemy.hp = 0

    assert combat._check_end_combat(game) is True

    assert "runeheart_gate" in player.cleared_areas
    assert any(
        quest.get("id") == "runeheart_gate"
        for quest in player.completed_quests
    )
    assert "Heartseal" in [item.name for item in player.inventory]
    assert player.gold >= 300
    assert "heart_of_the_gate" in player.achievements
    assert game.current_state() is state or isinstance(
        game.current_state(), RuneheartGateState
    )


def test_gate_leave_returns_to_the_sanctum(recording_io):
    player, game = _game(recording_io)
    state = RuneheartGateState(game)
    game.push_state(state)

    state._leave(game)

    assert isinstance(game.current_state(), SanctumState)
    assert player.current_map == "sanctum"
    assert (player.x, player.y) == (2, 7)
