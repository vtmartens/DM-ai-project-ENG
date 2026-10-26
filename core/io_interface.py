from abc import ABC, abstractmethod


class NeedsInput(Exception):
    """Raised by non-blocking IO when a state must wait for the next command."""


# Abstract interface for game I/O
class GameIO(ABC):
    def __init__(self):
        self.last_input = None
    
    @abstractmethod
    def show_message(self, text: str):
        """Shows a narrative message from the game"""
        pass

    @abstractmethod
    def system_message(self, text: str):
        """Shows a technical/system message"""
        pass
        
    @abstractmethod
    def error_message(self, text: str):
        """Shows an error message"""
        pass

    @abstractmethod
    def request_input(self, prompt: str = "") -> str:
        pass
    
    def get_last_input(self) -> str:
        """Returns the last input entered"""
        return self.last_input
        
    def get_structured_output(self) -> list:
        """
        Returns the structured output in the form of a list of dictionaries
        [
            {"type": "system", "text": "You opened the chest"},
            {"type": "narrative", "text": "Inside you find a scroll"},
            {"type": "narration", "text": "AI-generated prose"}
        ]
        """
        # Empty default implementation
        return []

    def show_narration(self, text: str):
        """Shows AI-generated prose. Defaults to a normal narrative message."""
        self.show_message(text)

    def show_map(self, text: str):
        """Shows preformatted map text. Defaults to a normal narrative message."""
        self.show_message(text)

    @property
    def pause_for_confirmation(self) -> bool:
        """Whether ``press_enter`` should block for a confirmation prompt.

        Terminals block; request/response web sessions do not need to.
        """
        return True

    def flush(self):
        """Emits any buffered output. The default implementation does nothing."""
        pass

# Base implementation for the terminal
class TerminalIO(GameIO):
    def __init__(self):
        super().__init__()
        self.buffer = []
        
    def show_message(self, text: str):
        print(text)
        self.buffer.append({"type": "narrative", "text": text})
        
    def system_message(self, text: str):
        print(f"[SYSTEM] {text}")
        self.buffer.append({"type": "system", "text": text})
        
    def error_message(self, text: str):
        print(f"[ERROR] {text}")
        self.buffer.append({"type": "error", "text": text})

    def request_input(self, prompt: str = "") -> str:
        self.last_input = input(prompt)
        self.buffer.append({"type": "prompt", "text": prompt})
        return self.last_input
        
    def get_structured_output(self) -> list:
        """Returns the structured output as a list of dictionaries"""
        return self.buffer
        
    def clear(self):
        """Clears the message buffer"""
        self.buffer = []