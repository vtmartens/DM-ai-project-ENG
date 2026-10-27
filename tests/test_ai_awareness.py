"""AI context, hints and recap coverage for the wider game state."""

from types import SimpleNamespace

from ai.context import build_context
from ai.recap import build_recap
from core.conditions import apply_condition
from core.game import Game
from core.hints import build_hint
from core.quests import start_quest
from entities.enemy import Enemy
from entities.player import Player
from states.combat import CombatState


def _game(recording_io):
    player = Player("Aria", "fighter")
    player.level = 10
    player.reputation = {"mirt_network": 12}
    player.completed_quests = [
        {
            "id": "sanctum_chapter",
            "title": "The Sealed Sanctum",
            "status": "completed",
        }
    ]
    player.claimed_rewards = ["sanctum_ward", "runeheart_mirt"]
    player.cleared_areas = ["sanctum"]
    player.rune_trials_best = 4
    player.rune_trials_runs = 1
    game = Game(player, None, recording_io, temporary=True)
    game.set_initial_map("tavern")
    start_quest(player, "shadows_of_the_market", game)
    apply_condition(player, "prone", turns=2, game=game)
    return player, game


def test_context_includes_world_quests_factions_campaign_and_trials(recording_io):
    player, game = _game(recording_io)
    enemy = Enemy("Training Dummy", hp=30)
    ally = SimpleNamespace(name="Violet", hp=20)
    combat = CombatState(enemy=enemy, allies=[ally])
    combat.effects["cover"] = True
    game.push_state(combat)

    context = build_context(game, memory=["The sanctum gate opened."])

    assert context["conditions"] == ["Prone"]
    assert context["quests"]["active"][0]["title"] == "Shadows in the Market"
    assert context["quests"]["completed"] == 1
    assert context["factions"]["shop_discount"] == 5
    assert any(
        entry["id"] == "mirt_network" and entry["tier"] == "friendly"
        for entry in context["factions"]["standing"]
    )
    assert context["campaign"] == {
        "sanctum_cleared": True,
        "runeheart_choice": "mirt",
        "sanctum_complete": True,
    }
    assert context["rune_trials"] == {"best": 4, "runs": 1}
    assert context["combat"]["covering"] is True
    assert context["combat"]["flanking"] is True
    assert context["combat"]["target"] == "Training Dummy"
    assert context["recent"] == ["The sanctum gate opened."]


def test_recap_includes_factions_campaign_trials_and_capstone(recording_io):
    _, game = _game(recording_io)

    recap = build_recap(game, memory=["You returned to the tavern."])

    assert "Faction standing: Mirt's Network +12 (Friendly)." in recap
    assert "Mirt's Network discount: 5%." in recap
    assert "Runeheart choice: you gave the Runeheart to Mirt." in recap
    assert "The Sealed Sanctum is complete." in recap
    assert "Best Rune Trial depth: wave 4 (1 completed run)." in recap
    assert "Class capstone unlocked." in recap


def test_combat_hints_cover_prone_and_staggered(recording_io):
    player, game = _game(recording_io)
    combat = CombatState(enemy=Enemy("Dummy", hp=20))
    game.push_state(combat)

    assert "prone" in build_hint(game).lower()

    player.conditions.clear()
    apply_condition(player, "staggered", turns=1, game=game)
    hint = build_hint(game)
    assert "staggered" in hint.lower()
    assert "abilities" in hint.lower()
