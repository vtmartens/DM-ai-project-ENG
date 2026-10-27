"""Deterministic hints and their optional AI phrasing."""

from ai.hints import generate_hint
from core.game import Game
from core.hints import build_hint
from core.quests import mark_quest_ready, start_quest
from entities.enemy import Enemy
from entities.npc import NPC
from entities.player import Player
from items.item import Item
from states.combat import CombatState
from states.dialogue import DialogueState


def _game(recording_io, char_class="fighter"):
    player = Player("Hint Tester", char_class)
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    player.set_position("tavern", 5, 5)
    return player, game


def test_hint_mentions_an_active_quest(recording_io):
    player, game = _game(recording_io)
    start_quest(player, "shadows_of_the_market", game)

    hint = build_hint(game)

    assert "Shadows in the Market" in hint
    assert "Defeat Vargas" in hint


def test_ready_quest_hint_points_to_the_turn_in(recording_io):
    player, game = _game(recording_io)
    start_quest(player, "shadows_of_the_market", game)
    mark_quest_ready(player, "shadows_of_the_market")

    hint = build_hint(game)

    assert "ready to turn in" in hint
    assert "Violet" in hint


def test_locked_door_hint_suggests_a_key_or_knock(recording_io):
    player, game = _game(recording_io)
    player.set_position("tavern", 21, 9)

    hint = build_hint(game)

    assert "Cellar door is locked" in hint
    assert "key" in hint.lower() or "Knock" in hint


def test_locked_door_hint_names_a_held_key(recording_io):
    player, game = _game(recording_io)
    player.set_position("tavern", 21, 9)
    player.add_item(Item("Cellar Key", "key", {"opens": ["Cellar Door"]}, 10))

    hint = build_hint(game)

    assert "Cellar Key" in hint


def test_locked_chest_hint_names_a_held_key(recording_io):
    player = Player("Hint Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("warehouse")
    player.set_position("warehouse", 16, 8)
    player.add_item(
        Item(
            "Warehouse Key",
            "key",
            {"opens": ["Warehouse Door", "Sealed Strongbox"]},
            25,
        )
    )

    hint = build_hint(game)

    assert "Sealed Strongbox is locked" in hint
    assert "Warehouse Key" in hint


def test_low_health_hint_suggests_a_potion(recording_io):
    player, game = _game(recording_io)
    player.hp = 1

    hint = build_hint(game)

    assert "1/" in hint
    assert "Healing Potion" in hint


def test_combat_hint_names_the_target(recording_io):
    player, game = _game(recording_io)
    enemy = Enemy("Training Goblin", hp=10, damage=1)
    game.push_state(CombatState(enemy=enemy))

    hint = build_hint(game)

    assert "Training Goblin" in hint


def test_dialogue_hint_names_the_npc(recording_io):
    player, game = _game(recording_io)
    game.push_state(DialogueState(NPC("Durnan")))

    hint = build_hint(game)

    assert "Durnan" in hint


def test_hint_warns_about_a_hostile_guardian(recording_io):
    player = Player("Hint Tester", "fighter")
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("vault")
    player.set_position("vault", 13, 6)

    hint = build_hint(game)

    assert "Iron Sentinel" in hint
    assert "hostile" in hint.lower()


def test_hint_falls_back_when_nothing_is_nearby(recording_io):
    player, game = _game(recording_io)
    player.set_position("tavern", 1, 10)

    hint = build_hint(game)

    assert "Explore the area" in hint


def test_hint_is_deterministic(recording_io):
    _, game = _game(recording_io)

    assert build_hint(game) == build_hint(game)


def test_hint_does_not_change_the_player(recording_io):
    player, game = _game(recording_io)
    before = player.to_dict()

    generate_hint(game)

    assert player.to_dict() == before


def test_ai_hint_uses_the_narrator_and_context(recording_io):
    _, game = _game(recording_io)

    class FakeHintNarrator:
        def __init__(self):
            self.calls = []

        def hint(self, hint, context):
            self.calls.append((hint, context))
            return f"The Dungeon Master whispers: {hint}"

    narrator = FakeHintNarrator()

    result = generate_hint(game, narrator=narrator)

    assert result["source"] == "ai"
    assert result["hint"].startswith("The Dungeon Master whispers:")
    assert narrator.calls
    hint, context = narrator.calls[0]
    assert hint
    assert context["player"]["name"] == "Hint Tester"


def test_ai_hint_falls_back_when_the_narrator_fails(recording_io):
    _, game = _game(recording_io)

    class BrokenNarrator:
        def hint(self, hint, context):
            raise RuntimeError("network down")

    result = generate_hint(game, narrator=BrokenNarrator())

    assert result["source"] == "engine"
    assert result["hint"]


def test_ai_hint_falls_back_when_the_narrator_declines(recording_io):
    _, game = _game(recording_io)

    class SilentNarrator:
        def hint(self, hint, context):
            return None

    result = generate_hint(game, narrator=SilentNarrator())

    assert result["source"] == "engine"


def test_hint_for_a_missing_player():
    assert build_hint(None) == "Choose a class and begin your adventure."
