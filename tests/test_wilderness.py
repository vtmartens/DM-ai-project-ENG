"""Road travel, wandering encounters and road loot."""

import pytest

from core import wilderness
from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState
from states.map_state import MapState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _road_game(recording_io, level=1):
    player = Player("Road Tester", "fighter")
    player.level = level
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("road")
    player.set_position("road", 2, 7)
    state = MapState()
    game.push_state(state)
    return player, game, state


def test_road_map_connects_to_the_market():
    player = Player("Route Tester", "fighter")
    game = Game(player, None, None, temporary=True)

    road = game.map_manager.get_map("road")
    market = game.map_manager.get_map("market")

    assert road is not None
    assert road.player_start_position == (2, 7)
    assert road.doors[(23, 7)] == ("market", 33, 6)
    assert market.doors[(33, 7)] == ("road", 2, 7)


def test_road_move_can_trigger_a_curated_loot_encounter(
    recording_io, monkeypatch
):
    player, game, state = _road_game(recording_io)
    state.encounter_cooldown = 0
    monkeypatch.setattr(
        wilderness, "should_trigger_encounter", lambda rng=None: True
    )
    monkeypatch.setattr(
        wilderness.random, "choice", lambda values: "goblin_scouts"
    )

    state._move_player_position(game, "east")

    combat = game.current_state()
    assert isinstance(combat, CombatState)
    assert combat.encounter["source"] == "road"
    assert combat.encounter["loot"] is True
    assert [enemy.name for enemy in combat.enemies] == [
        "Goblin Scout A",
        "Goblin Scout B",
    ]
    assert state.encounter_cooldown == wilderness.ROAD_ENCOUNTER_COOLDOWN
    assert "Goblin Scouts" in recording_io.text


def test_road_cooldown_prevents_immediate_encounters(recording_io, monkeypatch):
    player, game, state = _road_game(recording_io)
    state.encounter_cooldown = 2
    monkeypatch.setattr(
        wilderness, "should_trigger_encounter", lambda rng=None: True
    )
    monkeypatch.setattr(
        wilderness.random, "choice", lambda values: "goblin_scouts"
    )

    state._move_player_position(game, "east")
    assert game.current_state() is state
    assert state.encounter_cooldown == 1

    state._move_player_position(game, "east")
    assert game.current_state() is state
    assert state.encounter_cooldown == 0

    state._move_player_position(game, "east")
    assert isinstance(game.current_state(), CombatState)
    assert state.encounter_cooldown == wilderness.ROAD_ENCOUNTER_COOLDOWN
    assert (
        MapState.from_dict(state.to_dict()).encounter_cooldown
        == wilderness.ROAD_ENCOUNTER_COOLDOWN
    )


def test_low_level_road_encounters_exclude_the_orc_patrol():
    player = Player("Level Tester", "fighter")
    seen = []

    def choose(values):
        seen.extend(values)
        return values[0]

    wilderness.choose_road_encounter(player=player, chooser=choose)
    assert "orc_patrol" not in seen

    player.level = 3
    seen.clear()
    wilderness.choose_road_encounter(player=player, chooser=choose)
    assert "orc_patrol" in seen


def test_road_victory_drops_loot(recording_io):
    player = Player("Loot Tester", "wizard")
    enemy = Enemy("Goblin", monster_type="goblin")
    enemy.hp = 0
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(
        enemy=enemy,
        encounter={"loot": True, "source": "road"},
    )
    game.push_state(combat)
    combat.dice_d100.roll = lambda: 1

    combat._process_defeated_enemies(game)

    names = [item.name for item in player.inventory]
    assert "Light Healing Potion" in names
    assert "Short Sword" in names
    assert "You loot Light Healing Potion." in recording_io.text


def test_non_road_combat_does_not_drop_loot(recording_io):
    player = Player("Normal Tester", "wizard")
    enemy = Enemy("Goblin", monster_type="goblin")
    enemy.hp = 0
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemy=enemy)
    game.push_state(combat)
    combat.dice_d100.roll = lambda: 1

    combat._process_defeated_enemies(game)

    assert "Short Sword" not in [item.name for item in player.inventory]


def test_road_is_reachable_from_the_market_api(client):
    session_id = client.post(
        "/start", json={"name": "Road API", "char_class": "fighter"}
    ).get_json()["session_id"]
    client.post(
        "/command", json={"session_id": session_id, "command": "go to market"}
    )

    result = client.post(
        "/command", json={"session_id": session_id, "command": "go to road"}
    ).get_json()

    assert result["state"]["state"] == "MapState"
    assert result["state"]["position"]["map"] == "road"
    assert result["state"]["position"]["x"] == 2
    assert result["state"]["position"]["y"] == 7
