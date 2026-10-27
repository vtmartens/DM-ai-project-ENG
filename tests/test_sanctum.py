"""The Sealed Sanctum capstone chapter."""

from core.achievements import achievement_definitions
from core.encounters import build_encounter
from core.factions import reputation_value
from core.game import Game
from core.item_catalogue import item_definition
from core.quests import complete_quest, record_enemy_defeat, start_quest
from entities.npc import NPC
from entities.player import Player
from items.item import Item
from states.combat import CombatState
from states.dialogue import DialogueState
from states.sanctum import SanctumState
from states.underroad import UnderroadState
from tests.helpers import RecordingIO


class ScriptedIO(RecordingIO):
    def __init__(self, replies):
        super().__init__()
        self.replies = iter(replies)

    def request_input(self, prompt=""):
        self.last_input = next(self.replies, "")
        self.messages.append({"type": "prompt", "text": prompt})
        return self.last_input


def _game(recording_io, underroad_cleared=True, cache_claimed=True):
    player = Player("Sanctum Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("underroad")
    player.set_position("underroad", 2, 7)
    if underroad_cleared:
        player.cleared_areas = ["underroad"]
    if cache_claimed:
        player.claimed_rewards = ["underroad_cache"]
    return player, game


def _sanctum(recording_io, **kwargs):
    player, game = _game(recording_io, **kwargs)
    state = SanctumState(game)
    game.push_state(state)
    return player, game, state


def test_sanctum_map_encounter_quest_and_rewards_are_defined():
    player = Player("Map Tester", "fighter")
    game = Game(player, None, None, temporary=True)
    sanctum = game.map_manager.get_map("sanctum")
    encounter = build_encounter("sanctum_boss")

    assert sanctum is not None
    assert sanctum.doors[(1, 7)] == ("underroad", 2, 7)
    assert sanctum.player_start_position == (2, 7)
    assert encounter is not None
    assert [enemy.name for enemy in encounter["enemies"]] == [
        "Rune Warden",
        "Rune Sentinel A",
        "Rune Sentinel B",
    ]
    assert encounter["clears_area"] == "sanctum"
    assert item_definition("Runeheart Amulet") is not None
    assert any(
        entry.get("id") == "sanctum_breaker"
        for entry in achievement_definitions()
    )


def test_underroad_sanctum_door_requires_clear_and_cache(recording_io):
    player, game = _game(recording_io, underroad_cleared=False)
    state = UnderroadState(game)
    game.push_state(state)

    assert state._enter_sanctum(game) is False

    player.cleared_areas = ["underroad"]
    player.claimed_rewards = []
    assert state._enter_sanctum(game) is False
    assert isinstance(game.current_state(), UnderroadState)

    player.claimed_rewards = ["underroad_cache"]
    assert state._enter_sanctum(game) is True
    assert isinstance(game.current_state(), SanctumState)
    assert player.current_map == "sanctum"
    assert (player.x, player.y) == (2, 7)


def test_underroad_actions_only_offer_sanctum_after_clearing(recording_io):
    player, game = _game(recording_io, underroad_cleared=False)
    state = UnderroadState(game)

    assert "sanctum" not in state.available_actions(game)

    player.cleared_areas = ["underroad"]
    assert "sanctum" in state.available_actions(game)


def test_entering_sanctum_starts_the_capstone_quest(recording_io):
    player, game, state = _sanctum(recording_io)

    state._ensure_quest(game)

    assert any(
        quest.get("id") == "sanctum_chapter"
        for quest in player.active_quests
    )


def test_rune_ward_amulet_bypasses_the_threshold(recording_io):
    player, game, state = _sanctum(recording_io)
    player.add_item(
        Item("Rune-Ward Amulet", "accessory", {"defense": 1}, 140)
    )

    assert state._raise_amulet(game) is True
    assert "sanctum_ward" in player.claimed_rewards
    assert "Rune-Ward" in recording_io.text


def test_forcing_the_ward_costs_health_and_weakens_on_failure(
    recording_io, monkeypatch
):
    player, game, state = _sanctum(recording_io)
    player.hp = 50
    player.hp_max = 50
    monkeypatch.setattr(
        Player, "saving_throw", lambda self, *args, **kwargs: False
    )

    assert state._force_ward(game) is True

    assert player.hp == 42
    assert player.conditions["weakened"]["turns"] == 2
    assert "sanctum_ward" in player.claimed_rewards


def test_forcing_the_ward_successfully_avoids_damage(recording_io, monkeypatch):
    player, game, state = _sanctum(recording_io)
    player.hp = 50
    monkeypatch.setattr(
        Player, "saving_throw", lambda self, *args, **kwargs: True
    )

    assert state._force_ward(game) is True

    assert player.hp == 50
    assert "weakened" not in player.conditions
    assert "sanctum_ward" in player.claimed_rewards


def test_rune_warden_victory_clears_the_sanctum_and_readies_the_quest(
    recording_io,
):
    player, game, state = _sanctum(recording_io)
    state._ensure_quest(game)

    assert state._confront(game) is True
    combat = game.current_state()
    assert isinstance(combat, CombatState)
    for enemy in combat.enemies:
        enemy.hp = 0

    assert combat._check_end_combat(game) is True

    assert "sanctum" in player.cleared_areas
    quest = next(
        quest
        for quest in player.active_quests
        if quest.get("id") == "sanctum_chapter"
    )
    assert quest["status"] == "ready"
    assert "sanctum_breaker" in player.achievements
    assert isinstance(game.current_state(), SanctumState)


def test_runeheart_vault_grants_the_unique_reward_once():
    io = ScriptedIO(["1"])
    player = Player("Sanctum Tester", "fighter")
    game = Game(player, None, io, temporary=True)
    game.set_initial_map("sanctum")
    player.cleared_areas = ["underroad", "sanctum"]
    player.gold = 100
    state = SanctumState(game)
    game.push_state(state)

    assert state._open_vault(game) is True
    assert "Runeheart Amulet" in [item.name for item in player.inventory]
    assert player.gold == 220
    assert "sanctum_vault" in player.claimed_rewards
    assert "runeheart_kept" in player.claimed_rewards

    assert state._open_vault(game) is False
    assert player.gold == 220
    assert [item.name for item in player.inventory].count(
        "Runeheart Amulet"
    ) == 1


def test_runeheart_can_be_given_to_mirt_for_reputation(recording_io):
    player, game, state = _sanctum(recording_io)
    player.cleared_areas = ["underroad", "sanctum"]
    player.gold = 0

    assert state._apply_vault_choice(player, "mirt", game) is True

    assert player.gold == 320
    assert "Runeheart Amulet" not in [item.name for item in player.inventory]
    assert reputation_value(player, "mirt_network") == 12
    assert "runeheart_mirt" in player.claimed_rewards


def test_runeheart_can_be_given_to_violet_for_reputation(recording_io):
    player, game, state = _sanctum(recording_io)
    player.cleared_areas = ["underroad", "sanctum"]
    player.gold = 0

    assert state._apply_vault_choice(player, "violet", game) is True

    assert player.gold == 220
    assert "Runeheart Amulet" not in [item.name for item in player.inventory]
    assert reputation_value(player, "violet_watch") == 12
    assert "runeheart_violet" in player.claimed_rewards


def test_sanctum_leave_returns_to_the_underroad(recording_io):
    player, game, state = _sanctum(recording_io)

    state._leave(game)

    assert isinstance(game.current_state(), UnderroadState)
    assert player.current_map == "underroad"
    assert (player.x, player.y) == (2, 7)


def test_mirt_offers_and_tracks_the_sanctum_chapter(recording_io):
    player, game = _game(recording_io)
    player.completed_quests.append(
        {
            "id": "underroad_chapter",
            "title": "The Underroad",
            "status": "completed",
        }
    )
    dialogue = DialogueState(NPC("Mirt"))

    offer = [
        text for text, _ in dialogue.visible_options(game)
    ]
    assert "You mentioned a sealed sanctum beneath the Underroad." in offer

    start_quest(player, "sanctum_chapter", game)
    active = [text for text, _ in dialogue.visible_options(game)]
    assert "About the sealed sanctum..." in active
    assert "You mentioned a sealed sanctum beneath the Underroad." not in active

    record_enemy_defeat(player, "Rune Warden", game)
    ready = [text for text, _ in dialogue.visible_options(game)]
    assert "The Rune Warden is destroyed." in ready

    assert complete_quest(player, "sanctum_chapter", game) is True
    done = [text for text, _ in dialogue.visible_options(game)]
    assert "What lies beyond the sanctum?" in done


def test_sanctum_quick_actions_follow_the_current_phase(recording_io):
    player, game, state = _sanctum(recording_io)

    assert state.available_actions(game) == ["amulet", "force", "leave"]

    player.claimed_rewards.append("sanctum_ward")
    assert state.available_actions(game) == ["confront", "vault", "leave"]

    player.cleared_areas = ["underroad", "sanctum"]
    assert state.available_actions(game) == [
        "vault",
        "trials",
        "forge",
        "leave",
    ]


def test_sanctum_state_and_ward_survive_a_round_trip(recording_io):
    player, game, state = _sanctum(recording_io)
    state.phase = "main_menu"
    player.claimed_rewards.append("sanctum_ward")

    restored = SanctumState.from_dict(state.to_dict(), game)

    assert restored.phase == "main_menu"
    assert restored._ward_passed(player) is True
