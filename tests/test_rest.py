import pytest


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _start(client, char_class="wizard"):
    response = client.post(
        "/start", json={"name": "Rest Tester", "char_class": char_class}
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["session_id"]


def _player(client, session_id):
    import server

    return server.active_sessions[session_id].game.player


def _log_text(client, session_id):
    events = client.get(
        "/log", query_string={"session_id": session_id, "max": 200}
    ).get_json()["events"]
    return "\n".join(event.get("text", "") for event in events)


def test_rest_restores_hp_mana_and_clears_conditions(client):
    session_id = _start(client)
    player = _player(client, session_id)
    player.hp = 1
    player.mana = 0
    player.gold = 100
    player.conditions = {
        "poison": {"damage": 2, "turns": 3},
        "burning": {"turns": 2},
        "frightened": {"turns": 1},
    }

    response = client.post(
        "/command", json={"session_id": session_id, "command": "14"}
    )

    assert response.status_code == 200
    assert player.hp == player.hp_max
    assert player.mana == player.mana_max
    assert player.gold == 90
    assert player.conditions == {}
    log = _log_text(client, session_id)
    assert "long rest" in log
    assert "The rest clears: Burning, Frightened, Poisoned." in log


@pytest.mark.parametrize("command", ["rest", "sleep", "I'd like to rest."])
def test_rest_accepts_natural_language(client, command):
    session_id = _start(client)
    player = _player(client, session_id)
    player.hp = 2
    player.mana = 0
    player.gold = 25

    client.post("/command", json={"session_id": session_id, "command": command})

    assert player.hp == player.hp_max
    assert player.mana == player.mana_max
    assert player.gold == 15


def test_rest_is_refused_without_enough_gold(client):
    session_id = _start(client)
    player = _player(client, session_id)
    player.hp = 1
    player.gold = 5
    player.conditions = {"poison": {"damage": 2, "turns": 3}}

    client.post("/command", json={"session_id": session_id, "command": "14"})

    assert player.hp == 1
    assert player.gold == 5
    assert "poison" in player.conditions
    assert "only have 5" in _log_text(client, session_id)


def test_rest_says_when_already_rested(client):
    session_id = _start(client)
    player = _player(client, session_id)
    player.gold = 100

    client.post("/command", json={"session_id": session_id, "command": "14"})

    assert player.gold == 100
    assert "already rested" in _log_text(client, session_id)


def test_rest_is_advertised_in_the_tavern(client):
    session_id = _start(client)

    data = client.get(
        "/available_actions", query_string={"session_id": session_id}
    ).get_json()

    assert data["context"] == "TavernState"
    assert "rest" in data["actions"]
