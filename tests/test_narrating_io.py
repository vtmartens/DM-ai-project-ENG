import pickle
from types import SimpleNamespace

from ai.io import NarratingIO
from ai.narrator import NullNarrator
from tests.helpers import RecordingIO


class FakeNarrator:
    def __init__(self, reply="The torchlight wavers."):
        self.reply = reply
        self.calls = []

    def narrate(self, events, context):
        self.calls.append(([dict(event) for event in events], dict(context)))
        return self.reply


class ExplodingNarrator:
    def narrate(self, events, context):
        raise RuntimeError("model unavailable")


def _game_stub():
    player = SimpleNamespace(
        name="Aria",
        char_class="wizard",
        hp=5,
        hp_max=6,
        current_map="tavern",
        x=5,
        y=5,
    )
    return SimpleNamespace(
        player=player,
        current_state=lambda: None,
        get_player_position=lambda: {},
    )


def test_web_narration_does_not_pause_for_confirmation():
    from core.game_state import WebGameIO

    io = NarratingIO(WebGameIO(), NullNarrator())

    assert io.pause_for_confirmation is False


def test_dialogue_options_are_only_logged_for_terminal_style_io():
    from core.game_state import WebGameIO

    web = NarratingIO(WebGameIO(), NullNarrator())
    terminal = NarratingIO(RecordingIO(), NullNarrator())

    assert web.dialogue_options_in_log is False
    assert terminal.dialogue_options_in_log is True


def test_narration_wrapper_tracks_web_input():
    from core.game_state import WebGameIO

    base = WebGameIO()
    io = NarratingIO(base, NullNarrator())

    io.set_input("7")
    assert io.last_input == "7"
    assert base.last_input == "7"

    io.begin_turn("", available=False)
    assert io.last_input == ""
    assert base.last_input == ""


def test_map_messages_are_not_narrated(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)

    io.show_map("###\n#P#\n###")
    io.flush()

    assert narrator.calls == []
    assert recording_io.messages[-1] == {"type": "map", "text": "###\n#P#\n###"}


def test_engine_text_is_held_until_flush(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)

    io.show_message("You enter the tavern.")
    assert recording_io.text == ""

    io.request_input("> ")

    assert narrator.calls
    assert recording_io.messages[0] == {
        "type": "narration",
        "text": "The torchlight wavers.",
    }
    assert recording_io.messages[1] == {
        "type": "narrative",
        "text": "You enter the tavern.",
    }


def test_narration_is_emitted_before_engine_text_and_prompt(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)
    io.show_message("You enter the tavern.")
    io.show_message("1. Sit by the fire")

    io.request_input("> ")

    assert len(narrator.calls) == 1
    events, _ = narrator.calls[0]
    assert [event["text"] for event in events] == [
        "You enter the tavern.",
        "1. Sit by the fire",
    ]
    assert [m["type"] for m in recording_io.messages] == [
        "narration",
        "narrative",
        "narrative",
        "prompt",
    ]
    assert recording_io.messages[0]["text"] == "The torchlight wavers."
    assert recording_io.messages[-1] == {"type": "prompt", "text": "> "}


def test_a_second_prompt_does_not_repeat_narration(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)
    io.show_message("The door creaks open.")

    io.request_input("> ")
    io.request_input("> ")

    assert len(narrator.calls) == 1


def test_system_messages_flush_pending_and_are_not_narrated(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)
    io.show_message("You gain 10 gold.")

    io.system_message("Saved.")

    assert len(narrator.calls) == 1
    assert recording_io.messages[0] == {
        "type": "narration",
        "text": "The torchlight wavers.",
    }
    assert recording_io.messages[1] == {
        "type": "narrative",
        "text": "You gain 10 gold.",
    }
    assert recording_io.messages[-1] == {"type": "system", "text": "Saved."}


def test_narrator_returning_none_adds_nothing(recording_io):
    io = NarratingIO(recording_io, NullNarrator())
    io.show_message("You enter the tavern.")

    io.flush()

    assert recording_io.text == "You enter the tavern."


def test_narrator_failure_is_silent(recording_io):
    io = NarratingIO(recording_io, ExplodingNarrator())
    io.show_message("You enter the tavern.")

    assert io.request_input("> ") == ""
    narrative = [m["text"] for m in recording_io.messages if m["type"] == "narrative"]
    assert narrative == ["You enter the tavern."]


def test_context_comes_from_the_attached_game(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)
    io.set_game(_game_stub())
    io.show_message("You enter the tavern.")

    io.flush()

    context = narrator.calls[0][1]
    assert context["player"]["name"] == "Aria"
    assert context["player"]["class"] == "wizard"
    assert context["map"] == "tavern"
    assert context["position"] == [5, 5]


def test_memory_is_passed_to_the_next_narration(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)
    io.set_game(_game_stub())
    io.set_input("look")
    io.show_message("You enter the tavern.")
    io.flush()

    assert "recent" not in narrator.calls[0][1]
    assert io.memory

    io.set_input("talk to Durnan")
    io.show_message("Durnan greets you.")
    io.flush()

    events, context = narrator.calls[1]
    recent = context["recent"]
    assert any("You enter the tavern." in entry for entry in recent)
    assert any("Player: look" in entry for entry in recent)
    assert [event["text"] for event in events] == ["Durnan greets you."]


def test_memory_skips_menu_and_state_noise(recording_io):
    io = NarratingIO(recording_io, NullNarrator())
    io.show_message("1. Sit by the fire")
    io.show_message("HP Goblin A: 10/10")
    io.show_message("You enter the tavern.")

    io.flush()

    assert io.memory == ["You enter the tavern."]


def test_memory_is_bounded(recording_io):
    io = NarratingIO(recording_io, NullNarrator())
    io.memory_limit = 3
    for index in range(5):
        io.show_message(f"Event {index}")
        io.flush()

    assert io.memory == ["Event 2", "Event 3", "Event 4"]


def test_memory_can_be_disabled(recording_io):
    io = NarratingIO(recording_io, NullNarrator())
    io.memory_limit = 0
    io.show_message("An event.")

    io.flush()

    assert io.memory == []


def test_memory_survives_pickle(monkeypatch):
    import ai.io as ai_io

    class RebuiltNarrator:
        def narrate(self, events, context):
            return None

    monkeypatch.setattr(ai_io, "create_narrator_from_env", lambda: RebuiltNarrator())
    io = NarratingIO(RecordingIO(), FakeNarrator())
    io.memory = ["Earlier event."]
    io.memory_limit = 4

    restored = pickle.loads(pickle.dumps(io))

    assert restored.memory == ["Earlier event."]
    assert restored.memory_limit == 4


def test_title_menu_is_not_narrated_before_a_player_exists(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)
    io.set_game(SimpleNamespace(player=None))
    io.show_message("1. New Game")

    io.request_input("> ")

    assert narrator.calls == []
    narrative = [m["text"] for m in recording_io.messages if m["type"] == "narrative"]
    assert narrative == ["1. New Game"]


def test_clear_drops_pending_events(recording_io):
    narrator = FakeNarrator()
    io = NarratingIO(recording_io, narrator)
    io.show_message("Stale event.")

    io.clear()
    io.request_input("> ")

    assert narrator.calls == []


def test_pickle_round_trip_drops_and_rebuilds_the_narrator(monkeypatch):
    import ai.io as ai_io

    class RebuiltNarrator:
        def narrate(self, events, context):
            return None

    monkeypatch.setattr(ai_io, "create_narrator_from_env", lambda: RebuiltNarrator())
    base = RecordingIO()
    io = NarratingIO(base, FakeNarrator())

    restored = pickle.loads(pickle.dumps(io))

    assert isinstance(restored, NarratingIO)
    assert isinstance(restored.narrator, RebuiltNarrator)
    restored.show_message("After the reload.")
    restored.flush()
    assert restored.base.text == "After the reload."


def test_web_command_appends_narration_end_to_end(monkeypatch):
    import ai.io as ai_io
    from core.game_state import GameState
    from entities.player import Player
    from states.tavern import TavernState

    class FakeNarrator:
        def narrate(self, events, context):
            assert context["player"]["name"] == "Aria"
            return "The hearth crackles."

    monkeypatch.setattr(ai_io, "create_narrator_from_env", lambda: FakeNarrator())
    session = GameState(Player("Aria", "fighter"), TavernState())

    session.process_command("", provide_input=False)

    messages = session.io_buffer.get_structured_output()
    assert {"type": "narration", "text": "The hearth crackles."} in messages


def test_web_game_state_with_narration_can_be_pickled(monkeypatch):
    import ai.io as ai_io
    from core.game_state import GameState
    from entities.player import Player
    from states.tavern import TavernState

    class FakeNarrator:
        def narrate(self, events, context):
            return None

    monkeypatch.setattr(ai_io, "create_narrator_from_env", lambda: FakeNarrator())

    session = GameState(Player("Pickle", "fighter"), TavernState())
    restored = pickle.loads(pickle.dumps(session))

    assert isinstance(restored.io_buffer, ai_io.NarratingIO)
    assert restored.game.player.name == "Pickle"
