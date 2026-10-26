import pytest

PUBLIC_ENDPOINTS = ("/", "/classes")

SESSION_ENDPOINTS = (
    "/state",
    "/map",
    "/map_view",
    "/position",
    "/inventory",
    "/stats",
    "/missions",
    "/combat",
    "/log",
    "/available_actions",
    "/notifications",
    "/npcs",
    "/tutorial",
    "/achievements",
    "/abilities",
)


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _start(client, name="API Tester", char_class="fighter"):
    response = client.post("/start", json={"name": name, "char_class": char_class})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["session_id"]


@pytest.mark.parametrize("path", PUBLIC_ENDPOINTS)
def test_public_endpoints_return_200(client, path):
    response = client.get(path)

    assert response.status_code == 200, response.get_data(as_text=True)


def test_classes_are_loaded_from_data(client):
    data = client.get("/classes").get_json()

    assert "fighter" in data


def test_web_client_and_its_assets_are_served(client):
    redirect = client.get("/app")
    page = client.get("/app/")
    styles = client.get("/app/styles.css")
    script = client.get("/app/app.js")

    assert redirect.status_code == 302
    assert redirect.headers["Location"].endswith("/app/")
    assert page.status_code == 200
    assert b"DM AI" in page.data
    assert styles.status_code == 200
    assert script.status_code == 200


def test_root_catalogue_mentions_the_web_client(client):
    data = client.get("/").get_json()

    assert "GET /app" in data["endpoints"]


@pytest.mark.parametrize("path", SESSION_ENDPOINTS)
def test_session_endpoints_return_200(client, path):
    session_id = _start(client)

    response = client.get(path, query_string={"session_id": session_id})

    assert response.status_code == 200, (path, response.get_data(as_text=True))


def test_start_returns_the_initial_structured_output(client):
    response = client.post("/start", json={"name": "Output", "char_class": "fighter"})

    data = response.get_json()
    assert data["session_id"]
    assert data["player"]["name"] == "Output"
    assert isinstance(data["output"], list)
    assert any(message["type"] == "prompt" for message in data["output"])


def test_missing_session_is_a_404(client):
    response = client.get("/state", query_string={"session_id": "no-such-session"})

    assert response.status_code == 404


def test_combat_reports_no_combat_outside_a_fight(client):
    session_id = _start(client)

    data = client.get("/combat", query_string={"session_id": session_id}).get_json()

    assert data == {"in_combat": False}


def test_missions_expose_the_quest_log_shape(client):
    session_id = _start(client)

    data = client.get("/missions", query_string={"session_id": session_id}).get_json()

    assert {"active", "completed", "in_progress"} <= set(data)


def test_log_records_events_emitted_by_the_engine(client):
    session_id = _start(client)

    data = client.get("/log", query_string={"session_id": session_id}).get_json()

    assert isinstance(data["events"], list)
    assert data["events"], "starting a game should emit at least the tavern menu"


def test_available_actions_use_the_real_state_and_targets(client):
    session_id = _start(client)

    data = client.get(
        "/available_actions", query_string={"session_id": session_id}
    ).get_json()

    assert data["context"] == "TavernState"
    assert data["actions"]
    assert set(data["targets"]) == {"items", "npc", "directions"}


def test_preferences_are_stored_on_the_session(client):
    session_id = _start(client)

    response = client.post(
        "/preferences",
        json={
            "session_id": session_id,
            "preferences": {"theme": "dark", "narration": True},
        },
    )
    assert response.status_code == 200

    state = client.get("/state", query_string={"session_id": session_id}).get_json()
    assert state["preferences"] == {"theme": "dark", "narration": True}


def test_preferences_reject_a_non_mapping_payload(client):
    session_id = _start(client)

    response = client.post(
        "/preferences", json={"session_id": session_id, "preferences": ["nope"]}
    )

    assert response.status_code == 400


def test_state_exposes_the_contract_fields(client):
    session_id = _start(client)

    state = client.get("/state", query_string={"session_id": session_id}).get_json()

    assert set(
        [
            "name",
            "char_class",
            "hp",
            "max_hp",
            "state",
            "position",
            "inventory",
            "equipment",
            "stats",
            "active_quests",
            "completed_quests",
            "preferences",
            "combat",
            "dialogue",
        ]
    ) <= set(state)
    assert "mana" in state["stats"]
    assert state["position"]["map"]
    assert state["combat"]["in_combat"] is False
    assert state["dialogue"]["active"] is False


def test_map_view_returns_an_ascii_grid(client):
    session_id = _start(client)

    data = client.get("/map_view", query_string={"session_id": session_id}).get_json()

    assert data["map"] == "tavern"
    assert data["width"] > 0 and data["height"] > 0
    assert "P" in data["ascii"]
    assert len(data["ascii"].splitlines()) == data["height"]


def test_travel_moves_the_player_to_another_map(client):
    session_id = _start(client)

    client.post("/command", json={"session_id": session_id, "command": "2"})
    result = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()

    assert result["state"]["state"] == "MapState"
    assert result["state"]["position"]["map"] == "cellar"


def test_abilities_expose_class_abilities_and_skills(client):
    session_id = _start(client)

    data = client.get("/abilities", query_string={"session_id": session_id}).get_json()

    assert "Powerful Blow" in data["abilities"]
    assert "athletics" in data["skills"]
    assert data["mana"] == 0
    assert data["mana_max"] == 0


def test_use_ability_is_explicitly_not_implemented(client):
    session_id = _start(client)

    response = client.post(
        "/use_ability",
        json={"session_id": session_id, "ability_name": "Powerful Blow"},
    )

    assert response.status_code == 501
    assert response.get_json()["implemented"] is False


def test_command_does_not_repeat_the_opening_menu(client):
    response = client.post("/start", json={"name": "Flow", "char_class": "fighter"})
    session_id = response.get_json()["session_id"]

    command = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    texts = [message["text"] for message in command["output"]]

    assert not any("You are in the tavern. What do you want to do?" in text for text in texts)
    assert any("Who do you want to talk to?" in text for text in texts)


def test_second_choice_enters_dialogue(client):
    response = client.post("/start", json={"name": "Flow", "char_class": "fighter"})
    session_id = response.get_json()["session_id"]

    client.post("/command", json={"session_id": session_id, "command": "1"})
    command = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    texts = [message["text"] for message in command["output"]]
    dialogue = command["state"]["dialogue"]

    assert any("Welcome to the Yawning Portal" in text for text in texts)
    assert dialogue["active"] is True
    assert dialogue["options"]
    assert {"index", "text", "target"} <= set(dialogue["options"][0])


def test_explore_returns_real_nearby_targets(client):
    session_id = _start(client)

    data = client.post("/explore", json={"session_id": session_id}).get_json()

    assert isinstance(data["items"], list)
    assert isinstance(data["exits"], list)
    assert isinstance(data["npc"], list)


def test_assets_info_has_a_stable_empty_catalogue(client):
    catalogue = client.get("/assets_info").get_json()["assets"]
    items = client.get("/assets_info", query_string={"type": "items"}).get_json()["assets"]

    assert items == []
    assert "note" in catalogue


def test_achievements_does_not_mutate_the_cached_catalogue(client):
    from util.data_manager import get_data_manager

    session_id = _start(client)
    response = client.get("/achievements", query_string={"session_id": session_id})

    assert response.status_code == 200
    assert all("unlocked" in entry for entry in response.get_json()["achievements"])
    assert all(
        "unlocked" not in entry
        for entry in get_data_manager().get_achievements()
    )


def test_item_details_resolve_the_players_real_item(client):
    session_id = _start(client)

    response = client.get(
        "/item_details",
        query_string={"session_id": session_id, "object_name": "Healing Potion"},
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()
    assert data["name"] == "Healing Potion"
    assert data["type"] == "heal"
    assert {"action": "use", "description": "Use this item"} in data["uses"]


SAFE_GET_ENDPOINTS = (
    "/saves",
    "/list_saves",
    "/assets_info",
    "/item_details",
)

SAFE_POST_ENDPOINTS = (
    ("/command", {"command": "look"}),
    ("/move", {"direction": "north"}),
    ("/equipment", {"action": "examine", "item": "Healing Potion"}),
    ("/item", {"action": "examine", "item": "Healing Potion"}),
    ("/dialogue", {"npc": "Durnan", "option": "start"}),
    ("/explore", {}),
    ("/combat_action", {"action": "attack"}),
    ("/use_ability", {"ability_name": "Powerful Blow"}),
    ("/read_notification", {"all": True}),
    ("/preferences", {"preferences": {}}),
)


@pytest.mark.parametrize("path", SAFE_GET_ENDPOINTS)
def test_get_endpoints_never_raise(client, path):
    session_id = _start(client)

    response = client.get(
        path,
        query_string={"session_id": session_id, "object_name": "Healing Potion"},
    )

    assert response.status_code != 500, (path, response.get_data(as_text=True))


@pytest.mark.parametrize("path,payload", SAFE_POST_ENDPOINTS)
def test_post_endpoints_never_raise(client, path, payload):
    session_id = _start(client)

    response = client.post(path, json={"session_id": session_id, **payload})

    # 501 is an intentional, explicit "not implemented" answer.
    assert response.status_code != 500, (path, response.get_data(as_text=True))


def test_load_without_a_session_creates_one(client):
    session_id = _start(client)
    client.post("/save", json={"session_id": session_id, "file_name": "fresh-load.json"})

    response = client.post("/load", json={"file_name": "fresh-load.json"})

    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json()
    assert data["session_id"]
    assert data["player"]["name"] == "API Tester"
    assert isinstance(data["output"], list)


def test_save_reports_a_refusal(client, monkeypatch):
    import server

    session_id = _start(client)
    monkeypatch.setattr(server.GameState, "save", lambda self, path="save.json": False)

    response = client.post(
        "/save", json={"session_id": session_id, "file_name": "refused.json"}
    )

    assert response.status_code == 409


def test_save_load_and_delete_round_trip(client):
    session_id = _start(client)

    saved = client.post(
        "/save", json={"session_id": session_id, "file_name": "pytest-save.json"}
    )
    assert saved.status_code == 200, saved.get_data(as_text=True)

    listed = client.get("/saves").get_json()
    assert any(entry["file_name"] == "pytest-save.json" for entry in listed)

    loaded = client.post(
        "/load", json={"session_id": session_id, "file_name": "pytest-save.json"}
    )
    assert loaded.status_code == 200, loaded.get_data(as_text=True)
    loaded_data = loaded.get_json()
    assert loaded_data["player"]["name"] == "API Tester"
    assert loaded_data["state"]["name"] == "API Tester"

    deleted = client.post("/delete_save", json={"file_name": "pytest-save.json"})
    assert deleted.status_code == 200, deleted.get_data(as_text=True)

    listed_after = client.get("/saves").get_json()
    assert all(entry["file_name"] != "pytest-save.json" for entry in listed_after)
