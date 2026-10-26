from core.game import Game
from entities.npc import NPC
from entities.player import Player
from states.dialogue import DialogueState


def test_terminal_dialogue_still_logs_numbered_options(recording_io):
    game = Game(Player("Talker", "fighter"), None, recording_io, temporary=True)
    state = DialogueState(NPC("Durnan"))
    game.push_state(state)

    state.run(game)

    assert "Options:" in recording_io.text
    assert "1. " in recording_io.text
