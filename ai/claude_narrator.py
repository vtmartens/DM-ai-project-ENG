from __future__ import annotations

import json
import logging
from typing import Any

from ai import config
from ai.narrator import Narrator

logger = logging.getLogger("game_rpg.ai")

# One short atmospheric paragraph; keep output deliberately small.
FALLBACK_MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = (
    "You are the Dungeon Master of a text-based fantasy RPG.\n"
    "You receive JSON with two fields:\n"
    '- "events": the exact messages the game engine emitted this turn, in order.\n'
    '- "context": a small snapshot of the player, location and active state.\n\n'
    "Write ONE short atmospheric paragraph (2-4 sentences) in second person, present\n"
    "tense, that accompanies the events.\n"
    "The engine's own text is shown to the player unchanged, so do not repeat menu\n"
    "options, numbers, stat lines, or the events verbatim - add sensory detail, mood,\n"
    "and the world's reaction.\n\n"
    "Hard rules:\n"
    "- Never change or contradict a number, outcome, item, character, or state.\n"
    "- Never invent a choice, action, item, NPC, or event the events do not imply.\n"
    "- Do not decide the player's actions or choices, and do not reveal hidden information.\n"
    "- Return prose only: no headings, JSON, bullet points, or commentary.\n"
    "- If the events contain nothing narrative (only a menu or a numeric report),\n"
    "  describe the setting in one or two sentences without listing the choices."
)


class ClaudeNarrator(Narrator):
    """Dungeon Master narration through the official Anthropic SDK.

    Any API, authentication or parsing failure returns None so the game can fall
    back to its deterministic text. Permanent failures disable further attempts.
    """

    def __init__(
        self,
        client=None,
        model: str | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ):
        if client is None:
            import anthropic

            client = anthropic.Anthropic(timeout=timeout or config.narration_timeout())

        self.client = client
        self.model = model or config.narration_model()
        self.max_tokens = max_tokens or config.narration_max_tokens()
        self._disabled = False

    def narrate(
        self, events: list[dict[str, Any]], context: dict[str, Any]
    ) -> str | None:
        if self._disabled or not events:
            return None

        prompt = self._build_user_prompt(events, context)

        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-06-01"],
                fallbacks=[{"model": FALLBACK_MODEL}],
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            # Narration is an optional garnish: never let it break a turn.
            logger.warning("AI narrator unavailable; using engine text only: %s", exc)
            self._disable_if_permanent(exc)
            return None

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            logger.info("AI narrator refused this turn; using engine text only")
            return None
        if stop_reason == "max_tokens":
            logger.warning("AI narrator hit max_tokens; dropping truncated narration")
            return None

        text = "".join(
            block.text
            for block in (getattr(response, "content", None) or [])
            if getattr(block, "type", None) == "text"
            and getattr(block, "text", None)
        ).strip()

        return text or None

    @staticmethod
    def _build_user_prompt(
        events: list[dict[str, Any]], context: dict[str, Any]
    ) -> str:
        payload = json.dumps(
            {"events": events, "context": context},
            ensure_ascii=False,
            indent=2,
        )
        return f"Turn data:\n{payload}"

    def _disable_if_permanent(self, exc: Exception) -> None:
        try:
            import anthropic
        except ImportError:
            return

        permanent = (
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
            anthropic.NotFoundError,
        )
        if isinstance(exc, permanent):
            logger.warning("Disabling AI narration for this process after a permanent error")
            self._disabled = True
