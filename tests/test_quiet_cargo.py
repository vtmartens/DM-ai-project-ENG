"""Nessa's Underroad side quest, the impound wagon and its outcomes."""

import core.checks
from core.game import Game
from core.quests import mark_quest_ready, start_quest
from entities.npc import NPC
from entities.player import Player
from items.item import Item
from states.dialogue import DialogueState
from states.map_state import MapState
from states.underroad import UnderroadState


def _game(recording_io, chapter_completed=True):
    player = Player("Cargo Tester", "fighter")
    if chapter_completed:
        player.completed_quests = [
            {
                "id": "underroad_chapter",
                "title": "The Underroad",
                "status": "completed",
            }
        ]
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("underroad")
    return player, game


def _ready_player(recording_io):
    player, game = _game(recording_io)
    start_quest(player, "quiet_cargo", game)
    player.add_item(
        Item(
            "Cargo Manifest",
            "document",
            {},
            55,
            "A Watch impound manifest bound for the Underroad",
        )
    )
    mark_quest_ready(player, "quiet_cargo", game)
    return player, game


def test_nessa_offers_the_quiet_cargo_after_the_underroad_chapter(
    recording_io,
):
    player, game = _game(recording_io)
    dialogue = DialogueState(NPC("Nessa"))

    options = [text for text, _ in dialogue.visible_options(game)]
    assert "What happened to the cargo?" in options

    start_quest(player, "quiet_cargo", game)
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "What happened to the cargo?" not in options
    assert "About the impounded cargo..." in options


def test_nessa_does_not_offer_before_the_underroad_is_finished(recording_io):
    player, game = _game(recording_io, chapter_completed=False)
    dialogue = DialogueState(NPC("Nessa"))

    options = [text for text, _ in dialogue.visible_options(game)]
    assert "What happened to the cargo?" not in options

    dialogue.current_state = "nessa_info"
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "Tell me about the wagon." not in options


def test_impound_wagon_is_hidden_and_yields_the_manifest(
    recording_io, monkeypatch
):
    player, game = _game(recording_io)
    start_quest(player, "quiet_cargo", game)
    game.set_initial_map("market")
    player.set_position("market", 22, 8)
    wagon = game.map_manager.get_map("market").get_item_at(23, 8)
    monkeypatch.setattr(
        core.checks, "roll_d20", lambda *args, **kwargs: (20, [])
    )

    assert wagon.is_hidden()
    MapState()._search_area(game)
    assert wagon.hidden is False
    assert wagon.detected is True

    wagon.interact(player, game)

    assert any(item.name == "Cargo Manifest" for item in player.inventory)
    quest = next(
        quest
        for quest in player.active_quests
        if quest["id"] == "quiet_cargo"
    )
    assert quest["status"] == "ready"


def test_carrying_the_manifest_readies_the_quest_on_accept(recording_io):
    player, game = _game(recording_io)
    player.add_item(
        Item(
            "Cargo Manifest",
            "document",
            {},
            55,
            "A Watch impound manifest bound for the Underroad",
        )
    )

    start_quest(player, "quiet_cargo", game)

    quest = next(
        quest
        for quest in player.active_quests
        if quest["id"] == "quiet_cargo"
    )
    assert quest["status"] == "ready"


def test_manifest_can_be_given_to_nessa_for_underroad_standing(recording_io):
    player, game = _ready_player(recording_io)
    dialogue = DialogueState(NPC("Nessa"))
    node = dialogue.npc.get_conversation("quiet_cargo_nessa")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["underroad_smugglers"] == 8
    assert any(item.name == "Runner's Satchel" for item in player.inventory)
    assert not any(item.name == "Cargo Manifest" for item in player.inventory)
    assert "quiet_cargo" in {
        quest.get("id") for quest in player.completed_quests
    }
    assert "quiet_cargo" in player.achievements


def test_manifest_can_be_sent_to_violets_watch(recording_io):
    player, game = _ready_player(recording_io)
    player.gold = 0
    dialogue = DialogueState(NPC("Nessa"))
    node = dialogue.npc.get_conversation("quiet_cargo_violet")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["violet_watch"] == 8
    assert player.gold == 220
    assert not any(item.name == "Cargo Manifest" for item in player.inventory)
    assert "quiet_cargo" in {
        quest.get("id") for quest in player.completed_quests
    }


def test_manifest_can_be_sold_to_mirt(recording_io):
    player, game = _ready_player(recording_io)
    player.gold = 0
    dialogue = DialogueState(NPC("Nessa"))
    node = dialogue.npc.get_conversation("quiet_cargo_mirt")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["mirt_network"] == 8
    assert player.gold == 220
    assert not any(item.name == "Cargo Manifest" for item in player.inventory)
    assert "quiet_cargo" in {
        quest.get("id") for quest in player.completed_quests
    }


def test_nessa_offer_is_suppressed_after_completion(recording_io):
    player, game = _ready_player(recording_io)
    dialogue = DialogueState(NPC("Nessa"))
    node = dialogue.npc.get_conversation("quiet_cargo_nessa")
    dialogue._manage_effect(node["effect"], game)

    options = [text for text, _ in dialogue.visible_options(game)]

    assert "What happened to the cargo?" not in options
    assert "What happened to the tunnel families?" in options


def test_cleared_underroad_menu_opens_nessa_dialogue(recording_io):
    player, game = _game(recording_io)
    player.cleared_areas = ["underroad"]
    state = UnderroadState(game)
    game.push_state(state)

    assert "talk to Nessa" in state.available_actions(game)

    assert state._talk_to_nessa(game) is True
    current = game.current_state()
    assert isinstance(current, DialogueState)
    assert current.npc.name == "Nessa"


def test_nessa_cannot_be_reached_before_the_underroad_is_cleared(recording_io):
    player, game = _game(recording_io)
    state = UnderroadState(game)
    game.push_state(state)

    assert "talk to Nessa" not in state.available_actions(game)
    assert state._talk_to_nessa(game) is False
