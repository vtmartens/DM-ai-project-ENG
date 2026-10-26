import ai.io as ai_io
from tests.helpers import RecordingIO


class FakeNarrator:
    def narrate(self, events, context):
        return "AI prose"


def test_narration_is_off_by_default():
    base = RecordingIO()

    assert ai_io.create_narrator_from_env() is None
    assert ai_io.create_game_io(base) is base


def test_enabling_narration_wraps_the_io(monkeypatch):
    import ai.claude_narrator as claude_module

    monkeypatch.setenv("DM_AI_NARRATION", "1")
    monkeypatch.setattr(claude_module, "ClaudeNarrator", lambda *args, **kwargs: FakeNarrator())

    base = RecordingIO()
    io = ai_io.create_game_io(base)

    assert isinstance(io, ai_io.NarratingIO)
    assert io.base is base
    assert isinstance(io.narrator, FakeNarrator)


def test_unknown_provider_is_ignored(monkeypatch):
    monkeypatch.setenv("DM_AI_NARRATION", "1")
    monkeypatch.setenv("DM_AI_PROVIDER", "gemini")
    base = RecordingIO()

    assert ai_io.create_game_io(base) is base


def test_openai_provider_wraps_the_io(monkeypatch):
    import ai.openai_narrator as openai_module

    monkeypatch.setenv("DM_AI_NARRATION", "1")
    monkeypatch.setenv("DM_AI_PROVIDER", "openai")
    monkeypatch.setattr(openai_module, "OpenAINarrator", lambda *args, **kwargs: FakeNarrator())

    base = RecordingIO()
    io = ai_io.create_game_io(base)

    assert isinstance(io, ai_io.NarratingIO)
    assert isinstance(io.narrator, FakeNarrator)


def test_unavailable_sdk_falls_back_to_plain_io(monkeypatch):
    import ai.claude_narrator as claude_module

    monkeypatch.setenv("DM_AI_NARRATION", "1")

    def explode(*args, **kwargs):
        raise ImportError("anthropic is not installed")

    monkeypatch.setattr(claude_module, "ClaudeNarrator", explode)
    base = RecordingIO()

    assert ai_io.create_game_io(base) is base


def test_unavailable_openai_sdk_falls_back_to_plain_io(monkeypatch):
    import ai.openai_narrator as openai_module

    monkeypatch.setenv("DM_AI_NARRATION", "1")
    monkeypatch.setenv("DM_AI_PROVIDER", "openai-compatible")

    def explode(*args, **kwargs):
        raise ImportError("openai is not installed")

    monkeypatch.setattr(openai_module, "OpenAINarrator", explode)
    base = RecordingIO()

    assert ai_io.create_game_io(base) is base


def test_attach_game_is_a_no_op_for_plain_io():
    base = RecordingIO()

    assert ai_io.attach_game(base, object()) is base
