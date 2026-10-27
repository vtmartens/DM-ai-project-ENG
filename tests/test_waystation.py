"""The Broken Waystation: boss, rewards, campfire and quest hook."""

import pytest

from core.encounters import build_encounter, encounter_catalogue
from core.game import Game
from core.quests import start_quest
from entities.npc import NPC
from entities.player import Player
from states.combat import CombatState
from states.dialogue import DialogueState
from states.map_state import MapState
from states.waystation import WaystationState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io, char_class="fighter"):
    player = Player("Waystation Tester", char_class)
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("waystation")
    player.set_position("waystation", 2, 7)
    state = WaystationState()
    game.push_state(state)
    return player, game, state


def test_waystation_map_and_encounter_data():
    player = Player("Route Tester", "fighter")
    game = Game(player, None, None, temporary=True)

    road = game.map_manager.get_map("road")
    waystation = game.map_manager.get_map("waystation")
    encounter = build_encounter("waystation_chief")

    assert road.doors[(21, 7)] == ("waystation", 2, 7)
    assert waystation.doors[(1, 7)] == ("road", 20, 7)
    assert waystation.player_start_position == (2, 7)
    assert encounter is not None
    assert [enemy.name for enemy in encounter["enemies"]] == [
        "Waystation Chief",
        "Bandit A",
        "Bandit B",
    ]
    assert encounter["clears_area"] == "waystation"
    assert "waystation_chief" not in encounter_catalogue("tavern")


def test_boss_victory_clears_the_area_and_readies_the_quest(recording_io):
    player, game, state = _game(recording_io)
    start_quest(player, "waystation_trouble", game)

    assert state._confront_bandits(game) is True
    combat = game.current_state()
    assert isinstance(combat, CombatState)
    assert combat.encounter["clears_area"] == "waystation"

    for enemy in combat.enemies:
        enemy.hp = 0
    assert combat._check_end_combat(game) is True

    assert "waystation" in player.cleared_areas
    assert isinstance(game.current_state(), WaystationState)
    assert player.active_quests[0]["status"] == "ready"
    assert "The Waystation is clear." in recording_io.text
    assert "Objective complete: Trouble on the Trade Road" in recording_io.text


def test_strongbox_gives_the_unique_reward_once(recording_io):
    player, game, state = _game(recording_io)
    player.cleared_areas = ["waystation"]

    assert state._open_strongbox(game) is True
    assert "Wayfarer's Cloak" in [item.name for item in player.inventory]
    assert player.gold == 150
    assert "waystation_chest" in player.claimed_rewards

    start_quest(player, "waystation_trouble", game)
    assert player.active_quests[0]["status"] == "ready"

    assert state._open_strongbox(game) is False
    assert player.gold == 150
    assert [item.name for item in player.inventory].count("Wayfarer's Cloak") == 1
    assert "The strongbox is empty." in recording_io.text


def test_campfire_rest_restores_resources_and_conditions(recording_io):
    player, game, state = _game(recording_io, char_class="wizard")
    player.cleared_areas = ["waystation"]
    player.hp = 1
    player.mana = 0
    player.conditions = {"poison": {"damage": 2, "turns": 2}}

    assert state._rest_at_campfire(game) is True

    assert player.hp == player.hp_max
    assert player.mana == player.mana_max
    assert player.conditions == {}


def test_uncleared_waystation_refuses_rewards_and_rest(recording_io):
    player, game, state = _game(recording_io)
    before_gold = player.gold

    assert state._open_strongbox(game) is False
    assert state._rest_at_campfire(game) is False
    assert player.gold == before_gold
    assert "Wayfarer's Cloak" not in [
        item.name for item in player.inventory
    ]


def test_mirt_offers_and_updates_the_waystation_quest(recording_io):
    player = Player("Quest Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    dialogue = DialogueState(NPC("Mirt"))

    initial = [text for text, _ in dialogue.visible_options(game)]
    assert any("You look worried" in text for text in initial)
    assert not any("About the Broken Waystation" in text for text in initial)

    start_quest(player, "waystation_trouble", game)
    active = [text for text, _ in dialogue.visible_options(game)]
    assert any("About the Broken Waystation" in text for text in active)
    assert not any("You look worried" in text for text in active)


def test_leaving_waystation_returns_to_the_road(recording_io):
    player, game, state = _game(recording_io)

    state._leave(game)

    assert isinstance(game.current_state(), MapState)
    assert player.current_map == "road"
    assert (player.x, player.y) == (20, 7)


def test_cleared_and_claimed_state_survives_a_player_round_trip(recording_io):
    player, game, state = _game(recording_io)
    player.cleared_areas = ["waystation"]
    state._open_strongbox(game)

    restored = Player.from_dict(player.to_dict())

    assert "waystation" in restored.cleared_areas
    assert "waystation_chest" in restored.claimed_rewards


def test_waystation_api_starts_the_boss_fight(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Waystation API", "char_class": "fighter"}
    ).get_json()["session_id"]
    client.post(
        "/command", json={"session_id": session_id, "command": "go to market"}
    )
    client.post(
        "/command", json={"session_id": session_id, "command": "go to road"}
    )
    arrived = client.post(
        "/command",
        json={"session_id": session_id, "command": "go to waystation"},
    ).get_json()
    assert arrived["state"]["state"] == "WaystationState"

    # The boss and guards can act on initiative, so give the test player
    # enough health to observe the combat state rather than a defeat reset.
    session = server.active_sessions[session_id]
    session.game.player.hp = 100
    session.game.player.hp_max = 100

    actions = client.get(
        "/available_actions", query_string={"session_id": session_id}
    ).get_json()
    assert actions["context"] == "WaystationState"
    assert {"confront", "strongbox", "rest", "leave"} <= set(
        actions["actions"]
    )

    fight = client.post(
        "/command", json={"session_id": session_id, "command": "confront"}
    ).get_json()

    assert fight["state"]["state"] == "CombatState"
    assert [enemy["name"] for enemy in fight["state"]["combat"]["enemies"]] == [
        "Waystation Chief",
        "Bandit A",
        "Bandit B",
    ]
