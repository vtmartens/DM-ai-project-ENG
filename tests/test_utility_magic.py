"""Non-combat utility spells and their world interactions."""

from core.abilities import player_abilities, use_ability
from core.game import Game
from core.stealth import attempt_stealth
from entities.npc import NPC
from entities.player import Player
from items.item import Item
from states.dialogue import DialogueState


def _game(recording_io, char_class, map_name="tavern", x=5, y=5):
    player = Player("Magic Tester", char_class)
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map(map_name)
    player.set_position(map_name, x, y)
    return player, game


def _ability(player, name):
    return next(
        (ability["name"], ability)
        for ability in player_abilities(player)
        if ability["name"] == name
    )


def test_detect_magic_reveals_hidden_magical_objects(recording_io):
    player, game = _game(recording_io, "wizard", "cellar", 9, 5)
    trap = game.map_manager.get_map("cellar").get_item_at(10, 5)
    assert trap.is_hidden()
    before_mana = player.mana
    name, definition = _ability(player, "Detect Magic")

    assert use_ability(game, name, definition) is True

    assert trap.hidden is False
    assert trap.detected is True
    assert "Your spell reveals" in recording_io.text
    assert player.mana == before_mana - 3


def test_detect_magic_refuses_without_a_magical_target(recording_io):
    player, game = _game(recording_io, "wizard", "tavern", 5, 5)
    name, definition = _ability(player, "Detect Magic")
    before_mana = player.mana

    assert use_ability(game, name, definition) is False

    assert player.mana == before_mana
    assert "no magical auras" in recording_io.text


def test_disguise_self_grants_stealth_advantage_and_a_bluff(recording_io, monkeypatch):
    player, game = _game(recording_io, "rogue")
    name, definition = _ability(player, "Disguise Self")

    assert use_ability(game, name, definition) is True
    assert player.disguised is True

    seen = {}

    def fake_roll(advantage=False, disadvantage=False):
        seen["advantage"] = advantage
        return 20, []

    monkeypatch.setattr("core.checks.roll_d20", fake_roll)
    assert attempt_stealth(player, game) is True
    assert seen["advantage"] is True

    dialogue = DialogueState(NPC("Mirt"))
    options = [text for text, _ in dialogue.visible_options(game)]
    assert "You do not recognize me, merchant." in options
    dialogue._manage_effect({"type": "clear_disguise"}, game)
    assert player.disguised is False

    player.mana = 4
    assert use_ability(game, name, definition) is True
    assert player.disguised is True


def test_comprehend_languages_reads_the_bandit_ledger(recording_io):
    player, game = _game(recording_io, "cleric")
    player.add_item(Item("Bandit Ledger", "common", {}, 20, "A coded ledger"))
    name, definition = _ability(player, "Comprehend Languages")
    before_mana = player.mana

    assert use_ability(game, name, definition) is True

    assert "underroad_chapter" in {
        quest.get("id") for quest in player.active_quests
    }
    assert "Smuggler Lord" in recording_io.text
    assert player.mana == before_mana - 3


def test_comprehend_languages_reads_the_rune_pillar(recording_io):
    player, game = _game(recording_io, "cleric", "vault", 9, 5)
    name, definition = _ability(player, "Comprehend Languages")

    assert use_ability(game, name, definition) is True

    assert "sentinel's sigil" in recording_io.text


def test_comprehend_languages_refuses_without_text(recording_io):
    player, game = _game(recording_io, "cleric", "tavern", 5, 5)
    name, definition = _ability(player, "Comprehend Languages")
    before_mana = player.mana

    assert use_ability(game, name, definition) is False

    assert player.mana == before_mana
    assert "no ancient text" in recording_io.text


def test_disguise_survives_a_player_round_trip(recording_io):
    player, _ = _game(recording_io, "rogue")
    player.disguised = True

    assert Player.from_dict(player.to_dict()).disguised is True
