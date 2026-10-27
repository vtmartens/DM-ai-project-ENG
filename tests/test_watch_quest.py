"""Violet's Watch side quest, evidence cache and outcome branches."""

from core.game import Game
from core.quests import mark_quest_ready, start_quest
from entities.npc import NPC
from entities.player import Player
from tests.helpers import RecordingIO
from states.dialogue import DialogueState


def _game(recording_io=None):
    io = recording_io or RecordingIO()
    player = Player("Watch Tester", "fighter")
    player.reputation = {"violet_watch": 10}
    player.completed_quests = [
        {
            "id": "shadows_of_the_market",
            "title": "Shadows in the Market",
            "status": "completed",
        }
    ]
    game = Game(player, None, io, temporary=True)
    game.set_initial_map("market")
    return player, game, io


def _ready_player(recording_io=None):
    player, game, io = _game(recording_io)
    start_quest(player, "watchman_ledger", game)
    from items.item import Item

    player.add_item(
        Item(
            "Watch Ledger",
            "document",
            {},
            50,
            "A watch ledger recording missing confiscated goods",
        )
    )
    mark_quest_ready(player, "watchman_ledger", game)
    return player, game, io


def test_violet_offers_the_watch_quest_at_friendly_standing():
    player, game, _ = _game()
    dialogue = DialogueState(NPC("Violet"))

    options = [text for text, _ in dialogue.visible_options(game)]
    assert "I heard the Watch has a corruption problem." in options

    start_quest(player, "watchman_ledger", game)
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "I heard the Watch has a corruption problem." not in options
    assert "About Watch Sergeant Vell..." in options


def test_watch_cache_yields_the_ledger_and_readies_the_quest():
    player, game, _ = _game()
    start_quest(player, "watchman_ledger", game)
    game.player.set_position("warehouse", 7, 10)
    cache = game.map_manager.get_map("warehouse").get_item_at(8, 10)

    cache.interact(player, game)

    assert any(item.name == "Watch Ledger" for item in player.inventory)
    quest = next(
        quest
        for quest in player.active_quests
        if quest["id"] in {"watchman_ledger", "underroad_chapter"}
        and quest["id"] == "watchman_ledger"
    )
    assert quest["status"] == "ready"


def test_watch_ledger_can_be_given_to_violet():
    player, game, _ = _ready_player()
    dialogue = DialogueState(NPC("Violet"))
    node = dialogue.npc.get_conversation("watchman_violet")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["violet_watch"] == 18
    assert "watchman_ledger" in {
        quest.get("id") for quest in player.completed_quests
    }
    assert not any(item.name == "Watch Ledger" for item in player.inventory)
    assert "watch_whistleblower" in player.achievements


def test_watch_ledger_can_be_given_to_mirt_for_gold():
    player, game, _ = _ready_player()
    player.gold = 0
    dialogue = DialogueState(NPC("Violet"))
    node = dialogue.npc.get_conversation("watchman_mirt")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["mirt_network"] == 8
    assert player.gold == 160
    assert not any(item.name == "Watch Ledger" for item in player.inventory)
    assert "watchman_ledger" in {
        quest.get("id") for quest in player.completed_quests
    }


def test_watch_ledger_can_be_kept_with_a_reputation_cost():
    player, game, _ = _ready_player()
    dialogue = DialogueState(NPC("Violet"))
    node = dialogue.npc.get_conversation("watchman_keep")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["violet_watch"] == 5
    assert any(item.name == "Watch Ledger" for item in player.inventory)
    assert "watchman_ledger" in {
        quest.get("id") for quest in player.completed_quests
    }


def test_watch_quest_requires_the_shadows_quest_and_friendly_standing():
    player, game, _ = _game()
    player.completed_quests = []
    dialogue = DialogueState(NPC("Violet"))

    options = [text for text, _ in dialogue.visible_options(game)]
    assert "I heard the Watch has a corruption problem." not in options

    player.completed_quests = [
        {"id": "shadows_of_the_market", "title": "Shadows"}
    ]
    player.reputation["violet_watch"] = 5
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "I heard the Watch has a corruption problem." not in options


def test_watch_quest_does_not_offer_itself_after_completion():
    player, game, _ = _ready_player()
    dialogue = DialogueState(NPC("Violet"))
    node = dialogue.npc.get_conversation("watchman_violet")
    dialogue._manage_effect(node["effect"], game)

    options = [text for text, _ in dialogue.visible_options(game)]

    assert "I heard the Watch has a corruption problem." not in options
    assert "What happened to Vell?" in options
