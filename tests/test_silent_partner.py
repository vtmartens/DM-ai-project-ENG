"""Mirt's Network side quest, merchant ledger and outcome branches."""

from core.game import Game
from core.quests import mark_quest_ready, start_quest
from entities.npc import NPC
from entities.player import Player
from tests.helpers import RecordingIO
from states.dialogue import DialogueState


def _game(recording_io=None):
    io = recording_io or RecordingIO()
    player = Player("Network Tester", "fighter")
    player.reputation = {"mirt_network": 10}
    player.completed_quests = [
        {
            "id": "underroad_chapter",
            "title": "The Underroad",
            "status": "completed",
        }
    ]
    game = Game(player, None, io, temporary=True)
    game.set_initial_map("market")
    return player, game, io


def _ready_player(recording_io=None):
    player, game, io = _game(recording_io)
    start_quest(player, "silent_partner", game)
    from items.item import Item

    player.add_item(
        Item(
            "Merchant Ledger",
            "document",
            {},
            60,
            "A merchant's private ledger listing cursed relics",
        )
    )
    mark_quest_ready(player, "silent_partner", game)
    return player, game, io


def test_mirt_offers_the_silent_partner_at_friendly_standing():
    player, game, _ = _game()
    dialogue = DialogueState(NPC("Mirt"))

    options = [text for text, _ in dialogue.visible_options(game)]
    assert "One of your merchants is selling cursed relics." in options

    start_quest(player, "silent_partner", game)
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "One of your merchants is selling cursed relics." not in options
    assert "About Gundren's relics..." in options


def test_merchant_lockbox_yields_the_ledger_and_readies_the_quest():
    player, game, _ = _game()
    start_quest(player, "silent_partner", game)
    game.player.set_position("market", 5, 10)
    lockbox = game.map_manager.get_map("market").get_item_at(5, 9)

    lockbox.interact(player, game)

    assert any(item.name == "Merchant Ledger" for item in player.inventory)
    quest = next(
        quest
        for quest in player.active_quests
        if quest["id"] == "silent_partner"
    )
    assert quest["status"] == "ready"


def test_ledger_can_be_given_to_mirt():
    player, game, _ = _ready_player()
    dialogue = DialogueState(NPC("Mirt"))
    node = dialogue.npc.get_conversation("silent_partner_mirt")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["mirt_network"] == 18
    assert not any(item.name == "Merchant Ledger" for item in player.inventory)
    assert "silent_partner" in {
        quest.get("id") for quest in player.completed_quests
    }
    assert "silent_partner" in player.achievements


def test_ledger_can_protect_the_underroad_trade():
    player, game, _ = _ready_player()
    player.gold = 0
    dialogue = DialogueState(NPC("Mirt"))
    node = dialogue.npc.get_conversation("silent_partner_underroad")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["underroad_smugglers"] == 8
    assert player.gold == 200
    assert not any(item.name == "Merchant Ledger" for item in player.inventory)
    assert "silent_partner" in {
        quest.get("id") for quest in player.completed_quests
    }


def test_ledger_can_be_kept_with_a_reputation_cost():
    player, game, _ = _ready_player()
    dialogue = DialogueState(NPC("Mirt"))
    node = dialogue.npc.get_conversation("silent_partner_keep")

    dialogue._manage_effect(node["effect"], game)

    assert player.reputation["mirt_network"] == 5
    assert any(item.name == "Merchant Ledger" for item in player.inventory)
    assert "silent_partner" in {
        quest.get("id") for quest in player.completed_quests
    }


def test_offer_requires_underroad_completion_and_friendly_standing():
    player, game, _ = _game()
    player.completed_quests = []
    dialogue = DialogueState(NPC("Mirt"))
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "One of your merchants is selling cursed relics." not in options

    player.completed_quests = [
        {"id": "underroad_chapter", "title": "The Underroad"}
    ]
    player.reputation["mirt_network"] = 5
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "One of your merchants is selling cursed relics." not in options


def test_offer_is_suppressed_after_completion():
    player, game, _ = _ready_player()
    dialogue = DialogueState(NPC("Mirt"))
    node = dialogue.npc.get_conversation("silent_partner_mirt")
    dialogue._manage_effect(node["effect"], game)

    options = [text for text, _ in dialogue.visible_options(game)]

    assert "One of your merchants is selling cursed relics." not in options
    assert "What happened with Gundren?" in options
