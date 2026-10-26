from core.game import Game
from entities.player import Player
from states.base_state import BaseGameState


class DummyState(BaseGameState):
    def __init__(self, name):
        super().__init__()
        self.state_name = name
        self.events = []

    def enter(self, game=None):
        super().enter(game)
        self.events.append("enter")

    def exit(self, game=None):
        super().exit(game)
        self.events.append("exit")

    def pause(self, game=None):
        self.events.append("pause")

    def resume(self, game=None):
        self.events.append("resume")

    def run(self, game=None):
        self.events.append("run")


def _game(io):
    return Game(Player("State Tester", "fighter"), None, io, temporary=True)


def test_push_pauses_the_previous_state_and_pop_resumes_it(recording_io):
    game = _game(recording_io)
    first = DummyState("first")
    second = DummyState("second")

    game.push_state(first)
    assert first.events == ["enter"]

    game.push_state(second)
    assert first.events[-1] == "pause"
    assert second.events == ["enter"]

    game.pop_state()
    assert second.events[-1] == "exit"
    assert first.events[-1] == "resume"
    assert game.current_state() is first


def test_change_state_exits_the_old_state_and_enters_the_new_one(recording_io):
    game = _game(recording_io)
    first = DummyState("first")
    second = DummyState("second")

    game.push_state(first)
    game.change_state(second)

    assert first.events[-1] == "exit"
    assert second.events[0] == "enter"
    assert game.current_state() is second


def test_popping_the_last_state_ends_the_game(recording_io):
    game = _game(recording_io)
    game.push_state(DummyState("only"))

    game.pop_state()

    assert game.current_state() is None
    assert game.active is False


def test_push_ignores_none(recording_io):
    game = _game(recording_io)
    game.push_state(None)

    assert game.current_state() is None
    assert game.active is True
