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


def test_base_stats_and_mana_match_class_data(client):
    response = client.post("/start", json={"name": "Mana", "char_class": "wizard"})
    session_id = response.get_json()["session_id"]

    state = client.get("/state", query_string={"session_id": session_id}).get_json()
    stats = state["stats"]
    classes = client.get("/classes").get_json()

    assert stats["intelligence_base"] == 16
    # The effective modifier can include equipped gear; only the base score
    # is expected to match the class preview.
    assert stats["intelligence"] >= (16 - 10) // 2
    assert stats["mana"] == 20
    assert stats["mana_max"] == 20
    assert classes["wizard"]["base_stats"]["intelligence"] == stats["intelligence_base"]
    assert classes["wizard"]["mana_base"] == stats["mana"]


def test_map_view_returns_an_ascii_grid(client):
    session_id = _start(client)

    data = client.get("/map_view", query_string={"session_id": session_id}).get_json()

    assert data["map"] == "tavern"
    assert data["width"] > 0 and data["height"] > 0
    assert "P" in data["ascii"]
    assert len(data["ascii"].splitlines()) == data["height"]
    assert all(len(line) == data["width"] for line in data["ascii"].splitlines())

    legend = {entry["token"]: entry for entry in data["legend"]}
    assert legend["P"]["names"] == ["You"]
    assert "counter" in legend["B"]["names"]
    assert "chair" in legend["S"]["names"]
    assert "table" in legend["T"]["names"]
    assert "Elminster" in legend["E"]["names"]

    elminster = legend["E"]
    assert any(str(kind).casefold() == "npc" for kind in elminster["types"])
    assert any(
        member["name"] == "Elminster"
        and str(member["type"]).casefold() == "npc"
        for member in elminster["members"]
    )


def test_display_map_emits_a_monospaced_map_message(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "9"}
    ).get_json()
    maps = [message for message in result["output"] if message["type"] == "map"]

    assert maps, "the map state should emit a preformatted map message"
    lines = maps[0]["text"].splitlines()
    assert len(lines) > 1
    assert all(len(line) == len(lines[0]) for line in lines)

    texts = [message["text"] for message in result["output"]]
    assert any(text.strip() == "S = Chair" for text in texts)
    assert any(text.strip() == "T = Table" for text in texts)
    assert any(text.strip() == "D = Durnan (NPC)" for text in texts)


def test_move_on_map_updates_position_and_redraws(client):
    session_id = _start(client)

    started = client.post(
        "/command", json={"session_id": session_id, "command": "10"}
    ).get_json()
    assert started["state"]["state"] == "MapState"
    assert any("=== MOVEMENT ===" in message["text"] for message in started["output"])

    moved = client.post(
        "/command", json={"session_id": session_id, "command": "south"}
    ).get_json()
    assert moved["state"]["position"]["x"] == 5
    assert moved["state"]["position"]["y"] == 6

    maps = [message for message in moved["output"] if message["type"] == "map"]
    assert maps, "moving should redraw the map"
    lines = maps[-1]["text"].splitlines()
    assert lines[6][5] == "P"
    assert lines[6][6] == "D"  # Durnan is beside the player


def test_nearby_elements_are_in_english(client):
    session_id = _start(client)
    # Move beside Durnan, open the map, then choose "Show nearby elements".
    client.post("/command", json={"session_id": session_id, "command": "go to Durnan"})
    client.post("/command", json={"session_id": session_id, "command": "9"})
    result = client.post(
        "/command", json={"session_id": session_id, "command": "3"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert any("Characters:" in text for text in texts)
    assert not any("Personaggi" in text for text in texts)


def test_walk_to_npc_moves_next_to_it(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "go to Durnan"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["position"]["x"] == 5
    assert result["state"]["position"]["y"] == 6
    assert any("You move to Durnan" in text for text in texts)

    dialogue = client.post(
        "/command", json={"session_id": session_id, "command": "talk to Durnan"}
    ).get_json()
    assert dialogue["state"]["state"] == "DialogueState"
    assert dialogue["state"]["dialogue"]["npc"] == "Durnan"


def test_walk_to_object_moves_adjacent(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "walk to barrel"}
    ).get_json()
    position = result["state"]["position"]
    texts = [message["text"] for message in result["output"]]

    assert abs(position["x"] - 1) + abs(position["y"] - 1) == 1
    assert any("You move to barrel" in text for text in texts)


def test_walk_from_the_movement_menu(client):
    session_id = _start(client)
    client.post("/command", json={"session_id": session_id, "command": "10"})

    result = client.post(
        "/command", json={"session_id": session_id, "command": "walk to Durnan"}
    ).get_json()

    assert result["state"]["state"] == "MapState"
    assert result["state"]["position"]["x"] == 5
    assert result["state"]["position"]["y"] == 6
    maps = [message for message in result["output"] if message["type"] == "map"]
    assert maps
    lines = maps[-1]["text"].splitlines()
    assert lines[6][5] == "P"
    assert lines[6][6] == "D"


def test_already_adjacent_target_does_not_move(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "move to chair"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["position"]["x"] == 5
    assert result["state"]["position"]["y"] == 5
    assert any("already next to chair" in text for text in texts)


def test_talk_targeting_works_from_the_map_screen(client):
    session_id = _start(client)
    client.post("/command", json={"session_id": session_id, "command": "10"})
    client.post("/command", json={"session_id": session_id, "command": "south"})

    result = client.post(
        "/command", json={"session_id": session_id, "command": "talk to Durnan"}
    ).get_json()

    assert result["state"]["state"] == "DialogueState"
    assert result["state"]["dialogue"]["active"] is True
    assert result["state"]["dialogue"]["npc"] == "Durnan"


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
    details = {ability["name"]: ability for ability in data["ability_details"]}

    assert "Powerful Blow" in data["abilities"]
    assert "athletics" in data["skills"]
    assert data["mana"] == 0
    assert data["mana_max"] == 0
    assert data["in_combat"] is False
    assert details["Powerful Blow"]["mana_cost"] == 0
    assert details["Powerful Blow"]["combat_only"] is True
    assert details["Powerful Blow"]["description"]


def test_use_ability_casts_magic_missile_in_combat(client):
    import server

    session_id = _start(client, char_class="wizard")
    client.post("/command", json={"session_id": session_id, "command": "go to cellar"})
    client.post(
        "/command", json={"session_id": session_id, "command": "attack the Specter"}
    )
    session = server.active_sessions[session_id]
    combat = session.game.current_state()
    before_hp = combat.opponent.hp
    before_mana = session.game.player.mana

    response = client.post(
        "/use_ability",
        json={"session_id": session_id, "ability_id": "magic_missile"},
    )
    data = response.get_json()
    texts = [message["text"] for message in data["output"]]

    assert response.status_code == 200
    assert data["used"] is True
    assert combat.opponent.hp == before_hp - 8
    assert session.game.player.mana == before_mana - 5
    assert data["state"]["state"] == "CombatState"
    assert data["combat"]["in_combat"] is True
    assert any("Magic Missile" in text for text in texts)


def test_use_ability_cure_wounds_outside_combat(client):
    import server

    session_id = _start(client, char_class="cleric")
    session = server.active_sessions[session_id]
    session.game.player.hp = 1
    before_mana = session.game.player.mana

    data = client.post(
        "/use_ability",
        json={"session_id": session_id, "ability_name": "Cure Wounds"},
    ).get_json()

    assert data["used"] is True
    assert session.game.player.hp == min(session.game.player.hp_max, 9)
    assert session.game.player.mana == before_mana - 4
    assert data["state"]["state"] == "TavernState"


def test_use_ability_unknown_ability_returns_404(client):
    session_id = _start(client)

    response = client.post(
        "/use_ability",
        json={"session_id": session_id, "ability_name": "Fireball"},
    )

    assert response.status_code == 404


def test_use_ability_combat_only_outside_combat_is_refused(client):
    session_id = _start(client)

    data = client.post(
        "/use_ability",
        json={"session_id": session_id, "ability_name": "Powerful Blow"},
    ).get_json()
    texts = [message["text"] for message in data["output"]]

    assert data["used"] is False
    assert data["state"]["state"] == "TavernState"
    assert any("can only be used in combat" in text for text in texts)


def test_use_ability_without_mana_is_refused(client):
    import server

    session_id = _start(client, char_class="wizard")
    client.post("/command", json={"session_id": session_id, "command": "go to cellar"})
    client.post(
        "/command", json={"session_id": session_id, "command": "attack the Specter"}
    )
    session = server.active_sessions[session_id]
    combat = session.game.current_state()
    session.game.player.mana = 0
    before_hp = combat.opponent.hp

    data = client.post(
        "/use_ability",
        json={"session_id": session_id, "ability_name": "Magic Missile"},
    ).get_json()
    texts = [message["text"] for message in data["output"]]

    assert data["used"] is False
    assert combat.opponent.hp == before_hp
    assert session.game.player.mana == 0
    assert any("need 5 mana" in text for text in texts)


def test_combat_ability_menu_uses_a_class_ability(client):
    import server

    session_id = _start(client, char_class="wizard")
    client.post("/command", json={"session_id": session_id, "command": "go to cellar"})
    client.post(
        "/command", json={"session_id": session_id, "command": "attack the Specter"}
    )
    session = server.active_sessions[session_id]
    combat = session.game.current_state()
    before_hp = combat.opponent.hp

    menu = client.post(
        "/command", json={"session_id": session_id, "command": "5"}
    ).get_json()
    result = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    texts = [message["text"] for message in menu["output"]]

    assert any("Which ability?" in text for text in texts)
    assert any("Magic Missile" in text for text in texts)
    assert session.game.player.mana == 15
    assert combat.opponent.hp == before_hp - 8
    assert result["state"]["state"] == "CombatState"


def test_command_does_not_repeat_the_opening_menu(client):
    response = client.post("/start", json={"name": "Flow", "char_class": "fighter"})
    session_id = response.get_json()["session_id"]

    command = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    texts = [message["text"] for message in command["output"]]

    assert not any("You are in the tavern. What do you want to do?" in text for text in texts)
    assert any("Who do you want to talk to?" in text for text in texts)


def test_go_to_exit_leaves_the_tavern(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "go to exit"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["state"] == "MarketState"
    assert result["state"]["position"]["map"] == "market"
    assert result["state"]["position"]["x"] == 12
    assert result["state"]["position"]["y"] == 2
    assert any("You move to exit to market" in text for text in texts)
    assert any("You leave through the exit to market" in text for text in texts)


def test_leave_alias_works(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "leave"}
    ).get_json()

    assert result["state"]["state"] == "MarketState"
    assert result["state"]["position"]["map"] == "market"


def test_stale_session_uses_the_current_exit_coordinates(client):
    """A session saved before the door-data fix must still leave correctly."""
    import server

    session_id = _start(client)
    session = server.active_sessions[session_id]
    tavern = session.game.map_manager.get_map("tavern")

    # The old tavern exit pointed at (12, 1), where the market's door object sits.
    tavern.doors[(12, 14)] = ("market", 12, 1)
    session.game.player.set_position("tavern", 12, 14)
    server.save_session(session_id, session)

    # Simulate a server restart: the next command reloads the pickle from disk.
    server.active_sessions.clear()
    result = client.post(
        "/command", json={"session_id": session_id, "command": "leave the tavern"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["state"] == "MarketState"
    assert result["state"]["position"]["map"] == "market"
    assert result["state"]["position"]["x"] == 12
    assert result["state"]["position"]["y"] == 2
    assert any("You leave through the exit to market" in text for text in texts)
    assert not any("cannot find a path" in text.lower() for text in texts)


def test_unavailable_door_arrival_uses_a_nearby_free_cell(client):
    import server

    session_id = _start(client)
    session = server.active_sessions[session_id]
    tavern = session.game.map_manager.get_map("tavern")
    market = session.game.map_manager.get_map("market")

    tavern.doors[(12, 14)] = ("market", 12, 1)
    assert (12, 1) in market.items
    session.game.player.set_position("tavern", 12, 14)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "leave the tavern"}
    ).get_json()
    position = result["state"]["position"]
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["state"] == "MarketState"
    assert position["map"] == "market"
    assert (position["x"], position["y"]) != (12, 1)
    assert market.is_valid_position(position["x"], position["y"])
    assert (position["x"], position["y"]) not in market.items
    assert (position["x"], position["y"]) not in market.npc
    assert not any("cannot find a path" in text.lower() for text in texts)


def test_leave_market_returns_to_the_tavern_exit(client):
    session_id = _start(client)

    client.post("/command", json={"session_id": session_id, "command": "go to exit"})
    result = client.post(
        "/command", json={"session_id": session_id, "command": "leave the market"}
    ).get_json()

    assert result["state"]["state"] == "TavernState"
    assert result["state"]["position"]["map"] == "tavern"
    assert result["state"]["position"]["x"] == 12
    assert result["state"]["position"]["y"] == 13


@pytest.mark.parametrize("command", ["leave cellar", "go to exit"])
def test_cellar_exit_returns_to_the_market(client, command):
    """The cellar's exit_door object must not shadow its map exit."""
    session_id = _start(client)

    client.post("/command", json={"session_id": session_id, "command": "go to cellar"})
    result = client.post(
        "/command", json={"session_id": session_id, "command": command}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["state"] == "MarketState"
    assert result["state"]["position"]["map"] == "market"
    assert result["state"]["position"]["x"] == 14
    assert result["state"]["position"]["y"] == 5
    assert any("You move to exit to market" in text for text in texts)
    assert any("You leave through the exit to market" in text for text in texts)
    assert not any("You move to exit_door" in text for text in texts)


def test_unknown_go_target_does_not_fall_back_to_a_map_exit(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "go to nowhere"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["position"]["map"] == "tavern"
    assert result["state"]["position"]["x"] == 5
    assert result["state"]["position"]["y"] == 5
    assert any("There is no place called nowhere" in text for text in texts)


def test_map_view_shows_the_tavern_exit(client):
    session_id = _start(client)

    view = client.get("/map_view", query_string={"session_id": session_id}).get_json()
    lines = view["ascii"].splitlines()
    legend = {entry["token"]: entry for entry in view["legend"]}

    assert lines[14][12] == ">"
    assert "Exit to market" in legend[">"]["names"]
    assert "door" in legend[">"]["types"]


def test_natural_language_talk_targets_an_npc(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "talk to Durnan"}
    ).get_json()

    assert result["state"]["state"] == "DialogueState"
    assert result["state"]["dialogue"]["active"] is True
    assert result["state"]["dialogue"]["npc"] == "Durnan"
    assert result["state"]["dialogue"]["options"]


def test_natural_language_travel_targets_a_map(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "go to the market"}
    ).get_json()

    assert result["state"]["state"] == "MarketState"
    assert result["state"]["position"]["map"] == "market"


def test_natural_language_use_targets_an_item(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "use Healing Potion"}
    ).get_json()

    assert result["state"]["state"] == "TavernState"
    assert "Healing Potion" not in result["state"]["inventory"]


def test_natural_language_attack_targets_an_npc(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "attack Durnan"}
    ).get_json()

    assert result["state"]["state"] == "CombatState"
    assert result["state"]["combat"]["in_combat"] is True
    assert result["state"]["combat"]["enemies"][0]["name"] == "Durnan"


@pytest.mark.parametrize(
    ("npc_name", "position"),
    [("Specter", (5, 5)), ("Cultist", (12, 8))],
)
def test_defeated_cellar_npc_is_removed_from_the_map(client, npc_name, position):
    import server

    session_id = _start(client)
    client.post("/command", json={"session_id": session_id, "command": "go to cellar"})
    client.post(
        "/command",
        json={"session_id": session_id, "command": f"attack the {npc_name}"},
    )

    session = server.active_sessions[session_id]
    combat = session.game.current_state()
    assert type(combat).__name__ == "CombatState"
    combat.opponent.hp = 1

    result = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    cellar = session.game.map_manager.get_map("cellar")
    view = client.get(
        "/map_view", query_string={"session_id": session_id}
    ).get_json()
    legend_names = {name for entry in view["legend"] for name in entry["names"]}

    assert result["state"]["state"] == "MapState"
    assert position not in cellar.npc
    assert len(cellar.npc) == 1
    assert npc_name not in legend_names


def test_loading_a_session_prunes_already_defeated_npcs(client):
    import server

    session_id = _start(client)
    client.post("/command", json={"session_id": session_id, "command": "go to cellar"})
    session = server.active_sessions[session_id]
    cellar = session.game.map_manager.get_map("cellar")
    for npc in cellar.npc.values():
        npc.hp = 0

    server.save_session(session_id, session)
    server.active_sessions.clear()

    view = client.get(
        "/map_view", query_string={"session_id": session_id}
    ).get_json()
    legend_names = {name for entry in view["legend"] for name in entry["names"]}
    loaded = server.load_session(session_id)

    assert "Specter" not in legend_names
    assert "Cultist" not in legend_names
    assert loaded.game.map_manager.get_map("cellar").npc == {}


def test_natural_language_examine_shows_a_description(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "examine chair"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert any("A wooden chair" in text for text in texts)
    assert not any("Nothing happens with chair" in text for text in texts)


def test_unknown_target_falls_back_to_the_menu(client):
    session_id = _start(client)

    result = client.post(
        "/command", json={"session_id": session_id, "command": "talk to nobody"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["state"] == "TavernState"
    assert any("Who do you want to talk to?" in text for text in texts)
    assert any("You don't see nobody here." in text for text in texts)


def test_dialogue_option_with_no_target_returns_to_tavern(client):
    response = client.post(
        "/start", json={"name": "Dialogue Exit", "char_class": "fighter"}
    )
    session_id = response.get_json()["session_id"]

    for command in ("1", "1", "2", "1"):
        client.post("/command", json={"session_id": session_id, "command": command})

    result = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    texts = [message["text"] for message in result["output"]]

    assert result["state"]["state"] == "TavernState"
    assert result["state"]["dialogue"]["active"] is False
    assert any("conclude the dialogue" in text for text in texts)
    assert any("You return to the tavern" in text for text in texts)


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


def test_web_dialogue_options_are_not_repeated_in_the_log(client):
    response = client.post(
        "/start", json={"name": "Buttons", "char_class": "fighter"}
    )
    session_id = response.get_json()["session_id"]

    client.post("/command", json={"session_id": session_id, "command": "1"})
    command = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    texts = [message["text"] for message in command["output"]]
    option_lines = {
        f"{option['index']}. {option['text']}"
        for option in command["state"]["dialogue"]["options"]
    }

    assert command["state"]["dialogue"]["options"]
    assert not any(text.strip() == "Options:" for text in texts)
    assert not any(text.strip() in option_lines for text in texts)
    assert not any("Choose an option" in text for text in texts)


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

    # These endpoints may refuse a request, but they must never crash.
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
