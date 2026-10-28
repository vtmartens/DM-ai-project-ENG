"""Cycle Omen selection and their combat, economy and reward effects."""

from ai.context import build_context
from core.black_market import black_market_state
from core.crafting import add_rune_shards
from core.factions import shop_discount
from core.game import Game
from core.game_state import GameState
from core.omens import omen_catalogue, omen_entries
from core.quests import complete_quest, mark_quest_ready, start_quest
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState
from states.tavern import TavernState
from tests.helpers import RecordingIO


class ScriptedIO(RecordingIO):
    def __init__(self, replies):
        super().__init__()
        self.replies = iter(replies)

    def request_input(self, prompt=""):
        self.last_input = next(self.replies, "")
        self.messages.append({"type": "prompt", "text": prompt})
        return self.last_input


def _game(recording_io, omen=None, level=1):
    player = Player("Omen Tester", "fighter")
    player.level = level
    player.cycle_omen = omen
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    return player, game


def test_omen_catalogue_has_the_expected_options():
    ids = {entry["id"] for entry in omen_entries()}

    assert {"rune_surge", "smugglers_moon", "watch_crackdown", "long_winter"} <= ids
    assert "Rune Surge" in {
        entry["name"] for entry in omen_entries()
    }


def test_player_omen_defaults_to_none_and_survives_a_round_trip(recording_io):
    player = Player("Default Omen", "fighter")
    assert player.cycle_omen is None

    player.cycle_omen = "rune_surge"
    restored = Player.from_dict(player.to_dict())
    assert restored.cycle_omen == "rune_surge"


def test_new_cycle_accepts_an_omen_and_clears_it_when_skipped(recording_io):
    player, game = _game(recording_io)
    player.completed_quests = [
        {"id": "sanctum_chapter", "title": "The Sealed Sanctum"},
        {"id": "runeheart_gate", "title": "The Runeheart Gate"},
    ]

    assert game.start_new_cycle("rune_surge") is True
    assert player.cycle == 2
    assert player.cycle_omen == "rune_surge"

    assert game.start_new_cycle() is True
    assert player.cycle == 3
    assert player.cycle_omen is None


def test_rune_surge_and_long_winter_modify_enemy_scaling(recording_io):
    surge, _ = _game(recording_io, omen="rune_surge")
    enemy = Enemy("Dummy", hp=20)
    enemy.armor_class_value = 12
    combat = CombatState(enemy=enemy)
    combat._apply_cycle_scaling(surge)
    assert enemy.armor_class == 13

    winter, _ = _game(recording_io, omen="long_winter")
    enemy = Enemy("Dummy", hp=20)
    enemy.armor_class_value = 12
    combat = CombatState(enemy=enemy)
    combat._apply_cycle_scaling(winter)
    assert enemy.hp_max == 22


def test_omen_rewards_multiply_quest_gold_and_xp(recording_io):
    player, game = _game(recording_io, omen="long_winter", level=10)
    player.gold = 0
    start_quest(player, "silent_partner", game)
    mark_quest_ready(player, "silent_partner", game)

    complete_quest(player, "silent_partner", game)

    assert player.gold == 144
    assert player.experience == 264


def test_omen_rewards_multiply_encounter_rewards(recording_io):
    player, game = _game(
        recording_io, omen="smugglers_moon", level=10
    )
    player.gold = 0
    combat = CombatState(
        enemy=Enemy("Dummy", hp=10),
        encounter={"title": "Omen Test", "reward": {"gold": 100, "experience": 100}},
    )

    assert combat._grant_encounter_reward(game) is True
    assert player.gold == 110
    assert player.experience == 110


def test_rune_surge_increases_rune_shards(recording_io):
    player, game = _game(recording_io, omen="rune_surge")

    assert add_rune_shards(player, 10, game) == 15


def test_long_winter_and_watch_crackdown_modify_economy(recording_io):
    winter, _ = _game(recording_io, omen="long_winter")
    assert TavernState._rest_cost(winter) == 15

    watch, _ = _game(recording_io, omen="watch_crackdown")
    watch.reputation = {"mirt_network": 12}
    assert shop_discount(watch) == 15


def test_smugglers_moon_discounts_the_black_market(recording_io):
    player, _ = _game(recording_io, omen="smugglers_moon")
    player.completed_quests = [
        {"id": "quiet_cargo", "title": "The Quiet Cargo"}
    ]
    player.reputation = {"underroad_smugglers": 8}
    player.gold = 100

    state = black_market_state(player)
    smoke = next(
        entry for entry in state["items"] if entry["name"] == "Smoke Bomb"
    )

    assert state["discount"] == 20
    assert smoke["price"] == 12


def test_omen_is_exposed_in_campaign_state_and_ai_context(recording_io):
    player, game = _game(recording_io, omen="rune_surge")
    session = GameState(player, None)
    session.game = game

    campaign = session.get_campaign_state()
    context = build_context(game)

    assert campaign["cycle_omen"]["id"] == "rune_surge"
    assert campaign["cycle_omen"]["name"] == "Rune Surge"
    assert context["campaign"]["cycle_omen"] == "Rune Surge"


def test_tavern_offers_omen_selection_before_starting_a_cycle(recording_io):
    io = ScriptedIO(["1"])
    player = Player("Omen Flow", "fighter")
    game = Game(player, None, io, temporary=True)
    game.set_initial_map("tavern")
    player.completed_quests = [
        {"id": "sanctum_chapter", "title": "The Sealed Sanctum"},
        {"id": "runeheart_gate", "title": "The Runeheart Gate"},
    ]
    state = TavernState(game)
    game.push_state(state)
    state.phase = "choose_omen"

    state._choose_omen(game)

    assert player.cycle == 2
    assert player.cycle_omen == "rune_surge"
    assert isinstance(game.current_state(), TavernState)


def test_tavern_can_start_a_cycle_without_an_omen(recording_io):
    entries = omen_entries()
    io = ScriptedIO([str(len(entries) + 1)])
    player = Player("No Omen", "fighter")
    game = Game(player, None, io, temporary=True)
    game.set_initial_map("tavern")
    player.completed_quests = [
        {"id": "sanctum_chapter", "title": "The Sealed Sanctum"},
        {"id": "runeheart_gate", "title": "The Runeheart Gate"},
    ]
    state = TavernState(game)
    game.push_state(state)
    state.phase = "choose_omen"

    state._choose_omen(game)

    assert player.cycle == 2
    assert player.cycle_omen is None


def test_omen_catalogue_is_well_formed():
    for omen_id, definition in omen_catalogue().items():
        assert definition.get("name"), omen_id
        assert definition.get("description"), omen_id
        enemy = definition.get("enemy", {})
        assert isinstance(enemy, dict), omen_id
        assert int(definition.get("reward_percent", 0)) >= 0, omen_id
        assert int(definition.get("rune_shards_percent", 0)) >= 0, omen_id
        assert int(definition.get("rest_cost_bonus", 0)) >= 0, omen_id
