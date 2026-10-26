from core.io_interface import GameIO


class RecordingIO(GameIO):
    """A GameIO implementation that records output instead of using a terminal."""

    def __init__(self):
        super().__init__()
        self.messages = []

    def show_message(self, text):
        self.messages.append({"type": "narrative", "text": text})

    def show_narration(self, text):
        self.messages.append({"type": "narration", "text": text})

    def show_map(self, text):
        self.messages.append({"type": "map", "text": text})

    def system_message(self, text):
        self.messages.append({"type": "system", "text": text})

    def error_message(self, text):
        self.messages.append({"type": "error", "text": text})

    def request_input(self, prompt=""):
        self.last_input = ""
        self.messages.append({"type": "prompt", "text": prompt})
        return self.last_input

    def get_structured_output(self):
        return list(self.messages)

    def clear(self):
        self.messages = []

    @property
    def text(self):
        return "\n".join(message["text"] for message in self.messages)
