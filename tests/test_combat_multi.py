from types import SimpleNamespace

import pytest

from core.game import Game
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _start(client, name="Multi Tester", char_class="fighter"):
    response = client.post("/start", json={"name": name, "char_class": char_class})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["session_id"]


def test_multiple_enemies_support_targeting_and_save_round_trip(recording_io):
    player = Player("Multi", "fighter")
    enemies = [Enemy("Goblin A", hp=10), Enemy("Goblin B", hp=10)]
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemies=enemies)
    game.push_state(combat)

    assert [enemy.name for enemy in combat.enemies] == ["Goblin A", "Goblin B"]
    assert combat.opponent.name == "Goblin A"
    assert combat.select_target("Goblin B") is True
    assert combat.opponent.name == "Goblin B"

    restored = CombatState.from_dict(combat.to_dict())

    assert [enemy.name for enemy in restored.enemies] == [
        "Goblin A",
        "Goblin B",
    ]
    assert restored.opponent.name == "Goblin B"
    assert [enemy.hp for enemy in restored.enemies] == [10, 10]


def test_ally_attacks_a_living_enemy(recording_io):
    player = Player("Ally Tester", "fighter")
    enemy = Enemy("Dummy", hp=20, strength_base=10)
    ally = SimpleNamespace(name="Ally", hp=10, hp_max=10, strength=4)
    game = Game(player, None, recording_io, temporary=True)
    combat = CombatState(enemies=[enemy], allies=[ally])
    game.push_state(combat)

    combat._allies_attack(player, game)

    assert enemy.hp == 16
    assert "Ally attacks Dummy" in recording_io.text


def test_group_goblin_encounter_supports_target_selection(client):
    session_id = _start(client)
    client.post("/command", json={"session_id": session_id, "command": "4"})
    encounter = client.post(
        "/command", json={"session_id": session_id, "command": "7"}
    ).get_json()
    combat = encounter["state"]["combat"]

    assert encounter["state"]["state"] == "CombatState"
    assert [enemy["name"] for enemy in combat["enemies"]] == [
        "Goblin A",
        "Goblin B",
    ]
    assert combat["target"] == "Goblin A"

    menu = client.post(
        "/command", json={"session_id": session_id, "command": "6"}
    ).get_json()
    assert any("Choose a target" in message["text"] for message in menu["output"])

    chosen = client.post(
        "/command", json={"session_id": session_id, "command": "2"}
    ).get_json()
    assert chosen["state"]["combat"]["target"] == "Goblin B"

    action = client.post(
        "/combat_action",
        json={
            "session_id": session_id,
            "action": "attack",
            "target": "Goblin B",
        },
    ).get_json()
    hp_by_name = {
        enemy["name"]: enemy["hp"] for enemy in action["combat"]["enemies"]
    }
    assert hp_by_name["Goblin B"] < hp_by_name["Goblin A"]
