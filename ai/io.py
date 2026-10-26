from __future__ import annotations

import logging
from typing import Any

from ai.context import build_context
from ai.narrator import Narrator
from core.io_interface import GameIO

logger = logging.getLogger("game_rpg.ai")

OPENAI_PROVIDERS = {"openai", "openai-compatible", "compatible"}


class NarratingIO(GameIO):
    """GameIO decorator that appends optional AI narration after each turn.

    Every engine message is forwarded immediately and unchanged, so menus,
    numbers and outcomes can never be broken by the model. Narrative messages
    are also accumulated; before the next prompt the narrator is asked for one
    prose paragraph, which is appended. A missing or failing narrator simply
    means no extra paragraph.
    """

    def __init__(self, base: GameIO, narrator: Narrator, game=None):
        super().__init__()
        self.base = base
        self.narrator = narrator
        self.game = game
        self.pending: list[dict[str, str]] = []

    def set_game(self, game):
        """Sets the game whose context is sent with each narration request."""
        self.game = game
        return self

    @property
    def pause_for_confirmation(self) -> bool:
        return getattr(self.base, "pause_for_confirmation", True)

    def show_message(self, text: str) -> None:
        # Hold the engine text until the turn is flushed so the Dungeon Master
        # narration can be emitted *before* the NPC dialogue and options.
        self.pending.append({"type": "narrative", "text": text})

    def show_map(self, text: str) -> None:
        """Maps are UI, not narrative: forward them without sending to the model."""
        self.base.show_map(text)

    def system_message(self, text: str) -> None:
        self.flush()
        self.base.system_message(text)

    def error_message(self, text: str) -> None:
        self.flush()
        self.base.error_message(text)

    def request_input(self, prompt: str = "") -> str:
        self.flush()
        self.last_input = self.base.request_input(prompt)
        return self.last_input

    def flush(self) -> None:
        """Emits the turn: DM narration first, then the engine's own text."""
        if not self.pending:
            return

        events = self.pending
        self.pending = []

        prose = None
        if self.narrator is not None:
            try:
                context = build_context(self.game) if self.game is not None else {}
                # A game with no player yet is the title/load menu, not the story.
                if self.game is None or context:
                    prose = self.narrator.narrate(events, context)
            except Exception as exc:
                # Narration must never interrupt the game.
                logger.warning("AI narration failed: %s", exc)

        if prose:
            self.base.show_narration(prose)

        # The engine's deterministic text is still shown unchanged.
        for event in events:
            self.base.show_message(event["text"])

    def clear(self) -> None:
        self.pending = []
        self.base.clear()

    def get_structured_output(self):
        return self.base.get_structured_output()

    def __getattr__(self, name: str):
        # Delegates the web-specific WebGameIO surface (set_input, get_output,
        # get_output_text, ...) without narrowing the wrapper to one IO type.
        if name == "base":
            raise AttributeError(name)
        return getattr(self.base, name)

    def __getstate__(self):
        # Anthropic clients hold sockets and locks, so keep them out of pickled
        # web sessions. The narrator is rebuilt from the environment on load.
        state = self.__dict__.copy()
        state["narrator"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if self.__dict__.get("narrator") is None:
            self.narrator = create_narrator_from_env()


def create_narrator_from_env() -> Narrator | None:
    """Builds the configured narrator, or returns None when AI narration is off."""
    from ai import config

    if not config.narration_enabled():
        return None

    provider = config.narration_provider()

    try:
        if provider == "claude":
            from ai.claude_narrator import ClaudeNarrator

            return ClaudeNarrator()

        if provider in OPENAI_PROVIDERS:
            from ai.openai_narrator import OpenAINarrator

            return OpenAINarrator()
    except Exception as exc:
        logger.warning("AI narration disabled: %s", exc)
        return None

    logger.warning("Unsupported DM_AI_PROVIDER=%r; AI narration disabled", provider)
    return None


def create_game_io(base_io: GameIO, game=None) -> GameIO:
    """Wraps an IO with narration when the feature is enabled and available."""
    narrator = create_narrator_from_env()
    if narrator is None:
        return base_io
    return NarratingIO(base_io, narrator, game=game)


def attach_game(io: GameIO, game):
    """Gives a NarratingIO the game it should read context from."""
    if isinstance(io, NarratingIO):
        io.set_game(game)
    return io
