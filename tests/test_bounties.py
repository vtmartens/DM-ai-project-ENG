"""Tavern bounty board, progress tracking and claims."""

import pytest

from core.bounties import (
    MAX_ACTIVE_BOUNTIES,
    accept_bounty,
    active_bounty_count,
    bounty_definitions,
    bounty_entries,
    bounty_status,
    claim_bounty,
)
from core.game import Game
from core.quests import record_enemy_defeat, start_quest
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


@pytest.fixture
def client():
    import server

    server.app.config.update(TESTING=True)
    with server.app.test_client() as test_client:
        yield test_client


def _game(recording_io):
    player = Player("Bounty Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    return player, game


def test_bounty_definitions_expose_contracts_and_rewards():
    definitions = bounty_definitions()

    assert set(definitions) == {
        "bounty_goblin_road",
        "bounty_wolf_cull",
        "bounty_waystation_chief",
    }
    for definition in definitions.values():
        assert definition["bounty"] is True
        assert definition["target_type"]
        assert int(definition["target_count"]) >= 1
        assert definition["turn_in"] == "Bounty Board"
        assert definition["reward"]["gold"] > 0


def test_bounty_progress_counts_matching_monsters_and_readies_the_contract(
    recording_io,
):
    player, game = _game(recording_io)
    start_quest(player, "bounty_goblin_road", game)

    record_enemy_defeat(player, "Goblin A", game, monster_type="goblin")
    assert bounty_status(player, "bounty_goblin_road") == "active"
    entry = next(
        item
        for item in bounty_entries(player)
        if item["id"] == "bounty_goblin_road"
    )
    assert (entry["progress"], entry["target_count"]) == (1, 2)

    record_enemy_defeat(player, "Goblin B", game, monster_type="goblin")
    assert bounty_status(player, "bounty_goblin_road") == "ready"
    assert player.active_quests[0]["progress"] == 2

    record_enemy_defeat(player, "Goblin C", game, monster_type="goblin")
    assert player.progress_quests["bounty_goblin_road"]["progress"] == 2


def test_combat_victory_advances_matching_bounty_progress(recording_io):
    player, game = _game(recording_io)
    start_quest(player, "bounty_goblin_road", game)
    enemy = Enemy("Goblin Scout", monster_type="goblin")
    enemy.hp = 0
    combat = CombatState(enemy=enemy)
    game.push_state(combat)

    combat._process_defeated_enemies(game)

    assert player.progress_quests["bounty_goblin_road"]["progress"] == 1
    assert "Bounty progress: 1/2." in recording_io.text


def test_accepting_more_than_the_limit_is_refused(recording_io):
    player, game = _game(recording_io)

    assert accept_bounty(player, "bounty_goblin_road", game) is True
    assert accept_bounty(player, "bounty_wolf_cull", game) is True
    assert active_bounty_count(player) == MAX_ACTIVE_BOUNTIES
    assert accept_bounty(player, "bounty_waystation_chief", game) is False
    assert "at most 2 active bounties" in recording_io.text


def test_claiming_requires_readiness_and_grants_the_reward_once(recording_io):
    player, game = _game(recording_io)
    start_quest(player, "bounty_wolf_cull", game)
    before_gold = player.gold

    assert claim_bounty(player, "bounty_wolf_cull", game) is False
    assert player.gold == before_gold

    record_enemy_defeat(player, "Wolf A", game, monster_type="wolf")
    record_enemy_defeat(player, "Wolf B", game, monster_type="wolf")
    assert bounty_status(player, "bounty_wolf_cull") == "ready"
    assert claim_bounty(player, "bounty_wolf_cull", game) is True

    assert player.gold == before_gold + 35
    assert bounty_status(player, "bounty_wolf_cull") == "available"
    assert player.active_quests == []
    assert claim_bounty(player, "bounty_wolf_cull", game) is False
    assert accept_bounty(player, "bounty_wolf_cull", game) is True
    assert player.active_quests[0]["id"] == "bounty_wolf_cull"


def test_bounty_board_state_accepts_and_claims(client):
    import server

    session_id = client.post(
        "/start", json={"name": "Board Tester", "char_class": "fighter"}
    ).get_json()["session_id"]

    opened = client.post(
        "/command", json={"session_id": session_id, "command": "bounties"}
    ).get_json()
    assert opened["state"]["state"] == "BountyBoardState"
    assert any("BOUNTY BOARD" in message["text"] for message in opened["output"])

    actions = client.get(
        "/available_actions", query_string={"session_id": session_id}
    ).get_json()
    assert actions["context"] == "BountyBoardState"
    assert {"accept", "claim", "leave"} <= set(actions["actions"])

    accepted = client.post(
        "/command", json={"session_id": session_id, "command": "1"}
    ).get_json()
    assert accepted["state"]["state"] == "BountyBoardState"
    session = server.active_sessions[session_id]
    player = session.game.player
    assert player.active_quests[0]["id"] == "bounty_goblin_road"

    record_enemy_defeat(player, "Goblin A", session.game, monster_type="goblin")
    record_enemy_defeat(player, "Goblin B", session.game, monster_type="goblin")
    before_claim_gold = player.gold

    claimed = client.post(
        "/command", json={"session_id": session_id, "command": "claim 1"}
    ).get_json()

    assert claimed["state"]["state"] == "BountyBoardState"
    assert player.gold == before_claim_gold + 40
    assert player.active_quests == []
    assert any(
        "Quest complete: Goblin Toll" in message["text"]
        for message in claimed["output"]
    )


def test_tavern_bounty_command_opens_the_board(client):
    session_id = client.post(
        "/start", json={"name": "Tavern Board", "char_class": "fighter"}
    ).get_json()["session_id"]

    result = client.post(
        "/command", json={"session_id": session_id, "command": "contracts"}
    ).get_json()

    assert result["state"]["state"] == "BountyBoardState"
