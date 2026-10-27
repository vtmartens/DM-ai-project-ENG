from ai.claude_narrator import ClaudeNarrator

EVENTS = [{"type": "narrative", "text": "You enter the tavern."}]
CONTEXT = {"player": {"name": "Aria"}}


class FakeBlock:
    def __init__(self, text, type="text"):
        self.type = type
        self.text = text


class FakeResponse:
    def __init__(self, text="The torchlight wavers.", stop_reason="end_turn"):
        self.content = [FakeBlock(text)]
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeBeta:
    def __init__(self, messages):
        self.messages = messages


class FakeClient:
    def __init__(self, response=None, error=None):
        self.messages = FakeMessages(response, error)
        self.beta = FakeBeta(self.messages)


def _narrator(response=None, error=None):
    client = FakeClient(response, error)
    return ClaudeNarrator(client=client), client


def test_narration_uses_the_expected_request_shape():
    narrator, client = _narrator(FakeResponse("The fire crackles."))

    assert narrator.narrate(EVENTS, CONTEXT) == "The fire crackles."

    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["max_tokens"] == 1024
    assert call["output_config"] == {"effort": "low"}
    assert call["betas"] == ["server-side-fallback-2026-06-01"]
    assert call["fallbacks"] == [{"model": "claude-opus-4-8"}]
    assert "Dungeon Master" in call["system"]
    assert "You enter the tavern." in call["messages"][0]["content"]


def test_recap_uses_the_recap_prompt():
    narrator, client = _narrator(FakeResponse("Previously, the fire crackled."))

    assert (
        narrator.recap("Aria rests in the tavern.", CONTEXT)
        == "Previously, the fire crackled."
    )

    call = client.messages.calls[0]
    assert "previously" in call["system"].lower()
    assert "Aria rests in the tavern." in call["messages"][0]["content"]
    assert call["max_tokens"] == 256


def test_refusal_adds_no_narration():
    narrator, _ = _narrator(FakeResponse("Should not be used", stop_reason="refusal"))

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_truncated_output_is_dropped():
    narrator, _ = _narrator(FakeResponse("A cut-off sentence", stop_reason="max_tokens"))

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_empty_text_adds_nothing():
    narrator, _ = _narrator(FakeResponse(""))

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_no_events_skips_the_client():
    narrator, client = _narrator(FakeResponse())

    assert narrator.narrate([], CONTEXT) is None
    assert client.messages.calls == []


def test_api_failure_falls_back_silently():
    narrator, _ = _narrator(error=RuntimeError("network down"))

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_model_and_token_limit_can_be_overridden():
    client = FakeClient(FakeResponse("Prose."))
    narrator = ClaudeNarrator(client=client, model="claude-sonnet-5-5", max_tokens=256)

    narrator.narrate(EVENTS, CONTEXT)

    call = client.messages.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["max_tokens"] == 256


def test_scene_uses_the_scene_prompt_and_a_small_token_budget():
    narrator, client = _narrator(FakeResponse("Firelight moves across the taproom."))

    assert (
        narrator.describe("The Yawning Portal is warm and crowded.", CONTEXT)
        == "Firelight moves across the taproom."
    )

    call = client.messages.calls[0]
    assert call["max_tokens"] == 256
    assert "scene" in call["system"].lower()
    assert "Yawning Portal" in call["messages"][0]["content"]


def test_scene_refusal_falls_back():
    narrator, _ = _narrator(FakeResponse("Ignored", stop_reason="refusal"))

    assert narrator.describe("The Yawning Portal is warm.", CONTEXT) is None


def test_no_scene_skips_the_client():
    narrator, client = _narrator(FakeResponse())

    assert narrator.describe("", CONTEXT) is None
    assert client.messages.calls == []


def test_dialogue_uses_the_dialogue_prompt_and_a_small_token_budget():
    narrator, client = _narrator(FakeResponse("Durnan leans closer."))

    assert (
        narrator.dialogue("Durnan greets you.", CONTEXT)
        == "Durnan leans closer."
    )

    call = client.messages.calls[0]
    assert call["max_tokens"] == 256
    assert "dialogue" in call["system"].lower()
    assert "Durnan greets you." in call["messages"][0]["content"]


def test_no_dialogue_line_skips_the_client():
    narrator, client = _narrator(FakeResponse())

    assert narrator.dialogue("", CONTEXT) is None
    assert client.messages.calls == []


def test_hint_uses_the_hint_prompt_and_a_small_token_budget():
    narrator, client = _narrator(FakeResponse("The lock sighs open."))

    assert narrator.hint("Use the Cellar Key.", CONTEXT) == "The lock sighs open."

    call = client.messages.calls[0]
    assert call["max_tokens"] == 256
    assert "hint" in call["system"].lower()
    assert "Cellar Key" in call["messages"][0]["content"]


def test_hint_refusal_falls_back():
    narrator, _ = _narrator(FakeResponse("Ignored", stop_reason="refusal"))

    assert narrator.hint("Use the Cellar Key.", CONTEXT) is None


def test_hint_api_failure_falls_back_silently():
    narrator, _ = _narrator(error=RuntimeError("network down"))

    assert narrator.hint("Use the Cellar Key.", CONTEXT) is None


def test_no_hint_skips_the_client():
    narrator, client = _narrator(FakeResponse())

    assert narrator.hint("", CONTEXT) is None
    assert client.messages.calls == []
