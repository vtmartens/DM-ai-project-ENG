"""Curated encounters: construction, rewards and the tavern entry point."""

import pytest

from core.encounters import build_encounter, encounter_catalogue
from core.game import Game
from entities.player import Player
from states.combat import CombatState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _start(client):
    response = client.post(
        "/start", json={"name": "Encounter Tester", "char_class": "fighter"}
    )
    return response.get_json()["session_id"]


def test_catalogue_builds_every_encounter():
    catalogue = encounter_catalogue()
    assert catalogue

    for encounter_id in catalogue:
        encounter = build_encounter(encounter_id)
        assert encounter is not None
        assert encounter["id"] == encounter_id
        assert encounter["title"]
        assert encounter["description"]
        assert encounter["difficulty"] in {"easy", "medium", "hard"}
        assert encounter["enemies"]
        assert all(enemy.ability_ids for enemy in encounter["enemies"])


def test_encounter_metadata_excludes_enemy_objects():
    encounter = build_encounter("goblin_scouts")

    combat = CombatState(
        enemies=encounter["enemies"], encounter=encounter
    )

    assert "enemies" not in combat.encounter
    assert combat.encounter["id"] == "goblin_scouts"
    assert combat.encounter_rewarded is False


def test_encounter_reward_is_granted_once_on_victory(recording_io):
    player = Player("Encounter Winner", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    encounter = build_encounter("goblin_scouts")
    combat = CombatState(
        enemies=encounter["enemies"], encounter=encounter
    )
    for enemy in combat.enemies:
        enemy.hp = 0
    game.push_state(combat)
    before_gold = player.gold

    combat.run(game)

    assert combat.encounter_rewarded is True
    assert "Encounter complete: Goblin Scouts" in recording_io.text
    assert player.gold >= before_gold + 10

    gold_after = player.gold
    assert combat._grant_encounter_reward(game) is False
    assert player.gold == gold_after


def test_encounter_reward_is_not_granted_on_defeat(recording_io):
    player = Player("Encounter Loser", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    encounter = build_encounter("goblin_scouts")
    combat = CombatState(
        enemies=encounter["enemies"], encounter=encounter
    )
    game.push_state(combat)
    player.hp = 0

    combat._check_end_combat(game)

    assert combat.encounter_rewarded is False
    assert "Encounter complete" not in recording_io.text


def test_encounter_state_survives_round_trip():
    encounter = build_encounter("orc_patrol")
    combat = CombatState(
        enemies=encounter["enemies"], encounter=encounter
    )
    combat.encounter_rewarded = True
    combat.ability_cooldowns["0"] = {"shield_bash": 2}

    restored = CombatState.from_dict(combat.to_dict())

    assert restored.encounter["id"] == "orc_patrol"
    assert restored.encounter_rewarded is True
    assert restored.ability_cooldowns["0"]["shield_bash"] == 2


def test_curated_encounters_are_balanced():
    for encounter_id in encounter_catalogue():
        encounter = build_encounter(encounter_id)
        enemies = encounter["enemies"]
        total_hp = sum(enemy.hp for enemy in enemies)

        assert 1 <= len(enemies) <= 4, encounter_id
        # The capstone boss is intentionally above the normal encounter band.
        max_hp = 160 if encounter_id == "sanctum_boss" else 100
        assert 15 <= total_hp <= max_hp, (encounter_id, total_hp)
        assert all(enemy.ability_ids for enemy in enemies), encounter_id

        reward = encounter["reward"]
        assert int(reward.get("gold", 0)) >= 0
        assert int(reward.get("experience", 0)) >= 0
        assert reward.get("gold") or reward.get("experience"), encounter_id


def test_tavern_lists_and_starts_a_curated_encounter(client):
    session_id = _start(client)

    client.post("/command", json={"session_id": session_id, "command": "4"})
    listing = client.post(
        "/command", json={"session_id": session_id, "command": "8"}
    ).get_json()
    texts = [message["text"] for message in listing["output"]]
    assert any("Goblin Scouts" in text for text in texts)
    assert any("Orc Patrol" in text for text in texts)

    started = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()

    assert started["state"]["state"] == "CombatState"
    assert [enemy["name"] for enemy in started["state"]["combat"]["enemies"]] == [
        "Goblin Scout A",
        "Goblin Scout B",
    ]
