"""The Underroad chapter beneath the Broken Waystation."""

from core.encounters import build_encounter
from core.game import Game
from core.quests import record_enemy_defeat, start_quest
from entities.npc import NPC
from entities.player import Player
from states.combat import CombatState
from states.dialogue import DialogueState
from states.underroad import UnderroadState
from states.waystation import WaystationState


def _game(recording_io, underroad_cleared=False):
    player = Player("Underroad Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("underroad")
    player.set_position("underroad", 2, 7)
    if underroad_cleared:
        player.cleared_areas = ["underroad"]
    state = UnderroadState(game)
    game.push_state(state)
    return player, game, state


def test_underroad_map_and_encounter_data():
    player = Player("Map Tester", "fighter")
    game = Game(player, None, None, temporary=True)
    underroad = game.map_manager.get_map("underroad")
    encounter = build_encounter("underroad_boss")

    assert underroad is not None
    assert underroad.doors[(1, 7)] == ("waystation", 5, 7)
    assert underroad.player_start_position == (2, 7)
    assert encounter is not None
    assert [enemy.name for enemy in encounter["enemies"]] == [
        "Smuggler Lord",
        "Underroad Runner A",
        "Underroad Runner B",
    ]
    assert encounter["clears_area"] == "underroad"


def test_waystation_descend_requires_clear_and_opens_underroad(recording_io):
    player = Player("Descender", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("waystation")
    state = WaystationState(game)
    game.push_state(state)

    assert state._descend(game) is False
    assert isinstance(game.current_state(), WaystationState)

    player.cleared_areas = ["waystation"]
    assert state._descend(game) is True
    assert isinstance(game.current_state(), UnderroadState)
    assert player.current_map == "underroad"
    assert (player.x, player.y) == (2, 7)


def test_underroad_boss_victory_clears_area_and_readies_quest(recording_io):
    player, game, state = _game(recording_io)
    state._ensure_quest(game)
    assert player.active_quests[0]["id"] == "underroad_chapter"

    assert state._confront(game) is True
    combat = game.current_state()
    assert isinstance(combat, CombatState)
    for enemy in combat.enemies:
        enemy.hp = 0

    assert combat._check_end_combat(game) is True

    assert "underroad" in player.cleared_areas
    assert player.active_quests[0]["status"] == "ready"
    assert isinstance(game.current_state(), UnderroadState)
    assert "underroad_delver" in player.achievements


def test_underroad_cache_grants_the_unique_reward_once(recording_io):
    player, game, state = _game(recording_io, underroad_cleared=True)
    player.gold = 100

    assert state._open_cache(game) is True
    assert "Underroad Signet" in [item.name for item in player.inventory]
    assert player.gold == 175
    assert "underroad_cache" in player.claimed_rewards

    assert state._open_cache(game) is False
    assert player.gold == 175
    assert [item.name for item in player.inventory].count(
        "Underroad Signet"
    ) == 1


def test_underroad_leave_returns_to_the_waystation(recording_io):
    player, game, state = _game(recording_io)

    state._leave(game)

    assert isinstance(game.current_state(), WaystationState)
    assert player.current_map == "waystation"
    assert (player.x, player.y) == (5, 7)


def test_underroad_quest_is_turned_in_through_mirt_dialogue(recording_io):
    player = Player("Quest Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    start_quest(player, "underroad_chapter", game)
    record_enemy_defeat(player, "Smuggler Lord", game)
    dialogue = DialogueState(NPC("Mirt"))

    options = [text for text, _ in dialogue.visible_options(game)]

    assert "The Underroad is clear." in options


def test_waystation_strongbox_starts_the_underroad_quest(recording_io):
    player = Player("Ledger Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("waystation")
    player.cleared_areas = ["waystation"]
    state = WaystationState(game)
    game.push_state(state)

    assert state._open_strongbox(game) is True

    assert "Bandit Ledger" in [item.name for item in player.inventory]
    assert any(
        quest.get("id") == "underroad_chapter"
        for quest in player.active_quests
    )
