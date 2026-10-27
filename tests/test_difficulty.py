"""Story / Standard / Hard difficulty scaling and selection."""

import pytest

from ai.context import build_context
from core.difficulty import (
    defeat_gold_loss,
    difficulty_catalogue,
    difficulty_entries,
    enemy_scaling,
    rest_cost,
    reward_multiplier,
)
from core.game import Game
from core.game_state import GameState
from core.quests import complete_quest, mark_quest_ready, start_quest
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState
from states.tavern import TavernState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io, difficulty="standard", level=1):
    player = Player("Difficulty Tester", "fighter", difficulty=difficulty)
    player.level = level
    game = Game(player, None, recording_io, temporary=True)
    return player, game


def test_catalogue_has_story_standard_and_hard():
    assert {"story", "standard", "hard"} <= set(difficulty_catalogue())
    entries = {entry["id"]: entry for entry in difficulty_entries()}

    assert entries["standard"]["default"] is True
    assert entries["story"]["enemy"]["hp_percent"] < 0
    assert entries["hard"]["enemy"]["hp_percent"] > 0
    assert entries["story"]["rest_cost"] < entries["hard"]["rest_cost"]


def test_player_defaults_to_standard_and_persists_difficulty(recording_io):
    default_player = Player("Default", "fighter")
    assert default_player.difficulty == "standard"

    player, _ = _game(recording_io, difficulty="hard")
    restored = Player.from_dict(player.to_dict())
    assert restored.difficulty == "hard"

    legacy = Player.from_dict({"name": "Legacy", "char_class": "fighter"})
    assert legacy.difficulty == "standard"


def test_difficulty_modifies_combat_scaling_and_cycle_stacks(recording_io):
    story, _ = _game(recording_io, difficulty="story")
    enemy = Enemy("Training Brute", hp=20, strength_base=14)
    enemy.armor_class_value = 12
    story_combat = CombatState(enemy=enemy)
    story_combat._apply_cycle_scaling(story)

    assert enemy.hp_max == 16
    assert enemy.armor_class == 11

    hard, _ = _game(recording_io, difficulty="hard")
    hard.cycle = 2
    enemy = Enemy("Training Brute", hp=20, strength_base=14)
    enemy.armor_class_value = 12
    hard_combat = CombatState(enemy=enemy)
    hard_combat._apply_cycle_scaling(hard)

    assert enemy.hp_max == 29
    assert enemy.armor_class == 14
    assert enemy.damage_bonus == 2


def test_difficulty_scales_quest_rewards(recording_io):
    hard, game = _game(recording_io, difficulty="hard", level=10)
    hard.gold = 0
    start_quest(hard, "silent_partner", game)
    mark_quest_ready(hard, "silent_partner", game)

    complete_quest(hard, "silent_partner", game)

    assert hard.gold == 150
    assert hard.experience == 275

    story, game = _game(recording_io, difficulty="story", level=10)
    story.gold = 0
    start_quest(story, "silent_partner", game)
    mark_quest_ready(story, "silent_partner", game)

    complete_quest(story, "silent_partner", game)

    assert story.gold == 90
    assert story.experience == 165


def test_difficulty_scales_encounter_rewards(recording_io):
    player, game = _game(recording_io, difficulty="hard", level=10)
    player.gold = 0
    combat = CombatState(
        enemy=Enemy("Dummy", hp=10),
        encounter={"title": "Test", "reward": {"gold": 100, "experience": 100}},
    )

    assert combat._grant_encounter_reward(game) is True

    assert player.gold == 125
    assert player.experience == 125


def test_rest_and_defeat_costs_follow_difficulty(recording_io):
    story, _ = _game(recording_io, difficulty="story")
    hard, _ = _game(recording_io, difficulty="hard")

    assert rest_cost(story) == 5
    assert TavernState._rest_cost(story) == 5
    assert defeat_gold_loss(story) == 10
    assert rest_cost(hard) == 15
    assert defeat_gold_loss(hard) == 30
    assert enemy_scaling(hard)["damage_bonus"] == 1
    assert reward_multiplier(hard) == 1.25


def test_difficulty_is_exposed_in_context_and_campaign(recording_io):
    player, game = _game(recording_io, difficulty="hard")
    context = build_context(game)
    assert context["difficulty"] == {"id": "hard", "name": "Hard"}

    session = GameState(player, None)
    campaign = session.get_campaign_state()
    assert campaign["difficulty"]["id"] == "hard"
    assert campaign["difficulty"]["name"] == "Hard"


def test_start_endpoint_accepts_and_reports_difficulty(client):
    result = client.post(
        "/start",
        json={
            "name": "Hard Run",
            "char_class": "fighter",
            "difficulty": "hard",
        },
    ).get_json()

    assert result["player"]["difficulty"] == "hard"
    assert result["state"]["difficulty"] == "hard"
    assert result["state"]["campaign"]["difficulty"]["name"] == "Hard"

    import server

    session = server.active_sessions[result["session_id"]]
    assert session.game.player.difficulty == "hard"


def test_start_rejects_unknown_difficulty(client):
    response = client.post(
        "/start",
        json={
            "name": "Bad Run",
            "char_class": "fighter",
            "difficulty": "nightmare",
        },
    )

    assert response.status_code == 400


def test_difficulties_endpoint_lists_the_presets(client):
    data = client.get("/difficulties").get_json()

    ids = {entry["id"] for entry in data["difficulties"]}
    assert {"story", "standard", "hard"} <= ids
    assert data["default"] == "standard"
