from ai.openai_narrator import OpenAINarrator

EVENTS = [{"type": "narrative", "text": "You enter the tavern."}]
CONTEXT = {"player": {"name": "Aria"}}


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeResponse:
    def __init__(self, content="The hearth crackles.", finish_reason="stop"):
        self.choices = [FakeChoice(content, finish_reason)]


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    def __init__(self, response=None, error=None):
        self.chat = FakeChat(FakeCompletions(response, error))


def _narrator(response=None, error=None):
    client = FakeClient(response, error)
    return OpenAINarrator(client=client), client


def test_narration_uses_the_expected_request_shape():
    narrator, client = _narrator(FakeResponse("The fire crackles."))

    assert narrator.narrate(EVENTS, CONTEXT) == "The fire crackles."

    call = client.chat.completions.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["max_tokens"] == 1024
    assert call["messages"][0]["role"] == "system"
    assert "Dungeon Master" in call["messages"][0]["content"]
    assert call["messages"][1]["role"] == "user"
    assert "You enter the tavern." in call["messages"][1]["content"]
    assert "temperature" not in call


def test_recap_uses_the_recap_prompt():
    narrator, client = _narrator(FakeResponse("Previously, the hearth crackled."))

    assert (
        narrator.recap("Aria rests in the tavern.", CONTEXT)
        == "Previously, the hearth crackled."
    )

    call = client.chat.completions.calls[0]
    assert "previously" in call["messages"][0]["content"].lower()
    assert "Aria rests in the tavern." in call["messages"][1]["content"]
    assert call["max_tokens"] == 256


def test_model_can_be_overridden_for_local_servers():
    client = FakeClient(FakeResponse("Prose."))
    narrator = OpenAINarrator(client=client, model="Qwen2.5-Coder:32B")

    narrator.narrate(EVENTS, CONTEXT)

    assert client.chat.completions.calls[0]["model"] == "Qwen2.5-Coder:32B"


def test_truncated_output_is_dropped():
    narrator, _ = _narrator(FakeResponse("A cut-off sentence", finish_reason="length"))

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_content_filter_drops_the_response():
    narrator, _ = _narrator(FakeResponse("Blocked", finish_reason="content_filter"))

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_empty_content_adds_nothing():
    narrator, _ = _narrator(FakeResponse(""))

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_response_without_choices_adds_nothing():
    response = FakeResponse()
    response.choices = []
    narrator, _ = _narrator(response)

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_no_events_skips_the_client():
    narrator, client = _narrator(FakeResponse())

    assert narrator.narrate([], CONTEXT) is None
    assert client.chat.completions.calls == []


def test_api_failure_falls_back_silently():
    narrator, _ = _narrator(error=RuntimeError("connection refused"))

    assert narrator.narrate(EVENTS, CONTEXT) is None


def test_scene_uses_the_scene_prompt_and_a_small_token_budget():
    narrator, client = _narrator(FakeResponse("Firelight moves across the taproom."))

    assert (
        narrator.describe("The Yawning Portal is warm and crowded.", CONTEXT)
        == "Firelight moves across the taproom."
    )

    call = client.chat.completions.calls[0]
    assert call["max_tokens"] == 256
    assert "scene" in call["messages"][0]["content"].lower()
    assert "Yawning Portal" in call["messages"][1]["content"]


def test_scene_truncation_falls_back():
    narrator, _ = _narrator(FakeResponse("Cut off", finish_reason="length"))

    assert narrator.describe("The Yawning Portal is warm.", CONTEXT) is None


def test_no_scene_skips_the_client():
    narrator, client = _narrator(FakeResponse())

    assert narrator.describe("", CONTEXT) is None
    assert client.chat.completions.calls == []


def test_dialogue_uses_the_dialogue_prompt_and_a_small_token_budget():
    narrator, client = _narrator(FakeResponse("Durnan leans closer."))

    assert (
        narrator.dialogue("Durnan greets you.", CONTEXT)
        == "Durnan leans closer."
    )

    call = client.chat.completions.calls[0]
    assert call["max_tokens"] == 256
    assert "dialogue" in call["messages"][0]["content"].lower()
    assert "Durnan greets you." in call["messages"][1]["content"]


def test_no_dialogue_line_skips_the_client():
    narrator, client = _narrator(FakeResponse())

    assert narrator.dialogue("", CONTEXT) is None
    assert client.chat.completions.calls == []


def test_hint_uses_the_hint_prompt_and_a_small_token_budget():
    narrator, client = _narrator(FakeResponse("The lock sighs open."))

    assert narrator.hint("Use the Cellar Key.", CONTEXT) == "The lock sighs open."

    call = client.chat.completions.calls[0]
    assert call["max_tokens"] == 256
    assert "hint" in call["messages"][0]["content"].lower()
    assert "Cellar Key" in call["messages"][1]["content"]


def test_hint_truncation_falls_back():
    narrator, _ = _narrator(FakeResponse("Cut off", finish_reason="length"))

    assert narrator.hint("Use the Cellar Key.", CONTEXT) is None


def test_hint_content_filter_falls_back():
    narrator, _ = _narrator(FakeResponse("Blocked", finish_reason="content_filter"))

    assert narrator.hint("Use the Cellar Key.", CONTEXT) is None


def test_no_hint_skips_the_client():
    narrator, client = _narrator(FakeResponse())

    assert narrator.hint("", CONTEXT) is None
    assert client.chat.completions.calls == []
