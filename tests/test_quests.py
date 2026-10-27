import pytest

from core.game import Game
from core.quests import (
    build_ally_party,
    complete_quest,
    mark_quest_ready,
    recruit_ally,
    record_enemy_defeat,
    start_quest,
)
from entities.player import Player


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _start(client, name="Quest Tester", char_class="fighter"):
    response = client.post("/start", json={"name": name, "char_class": char_class})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["session_id"]


def _accept_violet_quest(client, session_id):
    client.post("/command", json={"session_id": session_id, "command": "go to market"})
    client.post(
        "/command", json={"session_id": session_id, "command": "talk to Violet"}
    )
    client.post("/command", json={"session_id": session_id, "command": "1"})
    started = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    client.post("/command", json={"session_id": session_id, "command": "1"})
    return started


def test_mirt_dialogue_starts_the_vargas_debt_quest(client):
    session_id = _start(client)

    client.post("/command", json={"session_id": session_id, "command": "talk to Mirt"})
    for command in ("1", "2", "1", "1"):
        client.post("/command", json={"session_id": session_id, "command": command})

    missions = client.get(
        "/missions", query_string={"session_id": session_id}
    ).get_json()
    active = {quest["title"]: quest for quest in missions["active"]}

    assert "A Debt to Collect" in active
    assert active["A Debt to Collect"]["objective"] == (
        "Find Vargas in the old warehouse and collect Mirt's debt."
    )
    assert active["A Debt to Collect"]["target"] == "Vargas"


def test_both_vargas_quests_turn_in_after_vargas(recording_io):
    player = Player("Double Quest", "fighter")
    game = Game(player, None, recording_io, temporary=True)

    assert start_quest(player, "shadows_of_the_market", game) is True
    assert start_quest(player, "vargas_debt", game) is True

    ready = record_enemy_defeat(player, "Vargas", game)

    assert set(ready) == {"shadows_of_the_market", "vargas_debt"}
    assert {
        quest["status"] for quest in player.active_quests
    } == {"ready"}
    assert player.completed_quests == []

    assert complete_quest(player, "shadows_of_the_market", game) is True
    assert complete_quest(player, "vargas_debt", game) is True

    assert {
        quest["title"] for quest in player.completed_quests
    } == {"Shadows in the Market", "A Debt to Collect"}
    assert player.gold == 100 + 60 + 50


def test_quest_rewards_and_recruited_ally(recording_io):
    player = Player("Quest Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    before_gold = player.gold

    assert start_quest(player, "shadows_of_the_market", game) is True
    assert [quest["title"] for quest in player.active_quests] == [
        "Shadows in the Market"
    ]
    assert start_quest(player, "shadows_of_the_market", game) is False

    assert recruit_ally(player, "Violet", game) is True
    assert recruit_ally(player, "Violet", game) is False
    assert [ally.name for ally in build_ally_party(player)] == ["Violet"]

    ready = record_enemy_defeat(player, "Vargas", game)

    assert ready == ["shadows_of_the_market"]
    assert player.active_quests[0]["status"] == "ready"
    assert player.completed_quests == []
    assert player.gold == before_gold
    assert "Objective complete: Shadows in the Market" in recording_io.text

    assert complete_quest(player, "shadows_of_the_market", game) is True

    assert player.active_quests == []
    assert [quest["title"] for quest in player.completed_quests] == [
        "Shadows in the Market"
    ]
    assert player.gold == before_gold + 60
    assert player.level == 2
    assert "Quest complete: Shadows in the Market" in recording_io.text
    assert "Violet joins you." in recording_io.text
    assert complete_quest(player, "shadows_of_the_market", game) is False


def test_violet_dialogue_starts_quest_and_recruits_ally(client):
    session_id = _start(client)

    started = _accept_violet_quest(client, session_id)
    texts = [message["text"] for message in started["output"]]
    missions = client.get(
        "/missions", query_string={"session_id": session_id}
    ).get_json()
    state = client.get(
        "/state", query_string={"session_id": session_id}
    ).get_json()

    assert any("Quest started: Shadows in the Market" in text for text in texts)
    assert any("Violet joins you." in text for text in texts)
    assert not any("already travelling" in text for text in texts)
    assert [quest["title"] for quest in missions["active"]] == [
        "Shadows in the Market"
    ]
    assert state["active_quests"][0]["objective"].startswith("Defeat Vargas")


def test_warehouse_group_fight_includes_ally_and_marks_quest_ready(client):
    import server

    session_id = _start(client)
    _accept_violet_quest(client, session_id)

    client.post(
        "/command", json={"session_id": session_id, "command": "go to warehouse"}
    )
    encounter = client.post(
        "/command", json={"session_id": session_id, "command": "attack Vargas"}
    ).get_json()
    combat = encounter["state"]["combat"]
    session = server.active_sessions[session_id]

    assert encounter["state"]["state"] == "CombatState"
    assert [enemy["name"] for enemy in combat["enemies"]] == [
        "Vargas",
        "Hooded Cultist A",
        "Hooded Cultist B",
    ]
    assert [ally["name"] for ally in combat["allies"]] == ["Violet"]
    assert combat["target"] == "Vargas"

    active = session.game.current_state()
    vargas = next(enemy for enemy in active.enemies if enemy.name == "Vargas")
    vargas.hp = 1
    result = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]
    missions = client.get(
        "/missions", query_string={"session_id": session_id}
    ).get_json()

    assert any("You defeated Vargas!" in text for text in texts)
    assert any(
        "Objective complete: Shadows in the Market" in text for text in texts
    )
    assert any("Return to Violet" in text for text in texts)
    assert missions["active"][0]["status"] == "ready"
    assert missions["completed"] == []


@pytest.mark.parametrize(
    ("npc_name", "quest_id", "title", "reward_gold", "option_text"),
    [
        ("Mirt", "vargas_debt", "A Debt to Collect", 50, "settled Vargas"),
        (
            "Violet",
            "shadows_of_the_market",
            "Shadows in the Market",
            60,
            "broke up Vargas",
        ),
    ],
)
def test_quest_turn_in_dialogue_completes_the_quest(
    client, npc_name, quest_id, title, reward_gold, option_text
):
    import server

    session_id = _start(client)
    session = server.active_sessions[session_id]
    player = session.game.player
    start_quest(player, quest_id)
    mark_quest_ready(player, quest_id)

    if npc_name == "Violet":
        client.post(
            "/command", json={"session_id": session_id, "command": "go to market"}
        )

    dialogue = client.post(
        "/command",
        json={"session_id": session_id, "command": f"talk to {npc_name}"},
    ).get_json()
    options = dialogue["state"]["dialogue"]["options"]
    turn_in = next(
        option for option in options if option_text in option["text"]
    )
    before_gold = player.gold

    result = client.post(
        "/command",
        json={"session_id": session_id, "command": str(turn_in["index"])},
    ).get_json()
    missions = client.get(
        "/missions", query_string={"session_id": session_id}
    ).get_json()

    assert player.gold == before_gold + reward_gold
    assert missions["active"] == []
    assert [quest["title"] for quest in missions["completed"]] == [title]
    assert any(
        f"Quest complete: {title}" in message["text"]
        for message in result["output"]
    )
