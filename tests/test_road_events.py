"""Data-driven non-combat events on the Trade Road."""

from core import road_events, wilderness
from core.game import Game
from entities.player import Player
from states.map_state import MapState
from states.road_event import RoadEventState
from tests.helpers import RecordingIO


class ScriptedIO(RecordingIO):
    def __init__(self, replies):
        super().__init__()
        self.replies = iter(replies)

    def request_input(self, prompt=""):
        self.messages.append({"type": "prompt", "text": prompt})
        return next(self.replies)


def _event_state(event_id, replies, player=None):
    io = ScriptedIO(replies)
    player = player or Player("Road Event Tester", "fighter")
    game = Game(player, None, io, temporary=True)
    game.set_initial_map("road")
    player.set_position("road", 2, 7)
    state = RoadEventState(road_events.get_road_event(event_id), game)
    game.push_state(state)
    return player, game, state, io


def test_road_events_filter_one_time_events_after_claiming():
    player = Player("Event Tester", "fighter")
    available = {
        event["id"] for event in road_events.available_road_events(player)
    }
    assert {"traveling_merchant", "roadside_shrine", "ambush"} <= available

    player.claimed_rewards = ["road_shrine"]
    available = {
        event["id"] for event in road_events.available_road_events(player)
    }
    assert "roadside_shrine" not in available
    assert "traveling_merchant" in available


def test_road_movement_can_start_a_non_combat_event(recording_io, monkeypatch):
    player = Player("Road Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("road")
    player.set_position("road", 2, 7)
    state = MapState()
    game.push_state(state)
    state.encounter_cooldown = 0
    monkeypatch.setattr(
        wilderness, "should_trigger_encounter", lambda rng=None: True
    )
    monkeypatch.setattr(
        road_events,
        "choose_road_event",
        lambda player, chooser=None: road_events.get_road_event(
            "roadside_shrine"
        ),
    )

    state._move_player_position(game, "east")

    assert isinstance(game.current_state(), RoadEventState)
    assert state.encounter_cooldown == wilderness.ROAD_ENCOUNTER_COOLDOWN


def test_merchant_event_sells_road_stock():
    player, game, state, io = _event_state(
        "traveling_merchant", ["1", ""]
    )
    player.gold = 100

    state._merchant_menu(game)

    assert player.gold == 90
    assert "Light Healing Potion" in [
        item.name for item in player.inventory
    ]
    assert "You buy Light Healing Potion for 10 gold." in io.text


def test_shrine_event_heals_clears_conditions_and_is_one_time():
    player = Player("Shrine Tester", "wizard")
    player.hp = 1
    player.conditions = {"poison": {"damage": 2, "turns": 2}}
    player, game, state, io = _event_state(
        "roadside_shrine", ["1", "", "1"], player=player
    )

    state._shrine_menu(game)

    assert player.hp == min(player.hp_max, 11)
    assert player.conditions == {}
    assert "road_shrine" in player.claimed_rewards
    assert "restores" in io.text

    state._shrine_menu(game)
    assert "already been spent" in io.text


def test_wagon_event_skill_check_grants_reward(monkeypatch):
    player, game, state, io = _event_state("stranded_wagon", ["1", ""])
    player.gold = 100
    monkeypatch.setattr(
        "core.checks.roll_d20", lambda *args, **kwargs: (20, [])
    )

    state._wagon_menu(game)

    assert player.gold == 130
    assert "Light Healing Potion" in [
        item.name for item in player.inventory
    ]
    assert "road_wagon" in player.claimed_rewards
    assert "Investigation check:" in io.text


def test_traveler_event_help_grants_reward_and_is_one_time():
    player, game, state, io = _event_state(
        "wounded_traveler", ["1", ""]
    )
    player.gold = 100

    state._traveler_menu(game)

    assert player.gold == 115
    assert player.experience == 25
    assert "road_traveler" in player.claimed_rewards
    assert "reward" in io.text.lower()
