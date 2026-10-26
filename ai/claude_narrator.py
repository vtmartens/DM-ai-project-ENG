from __future__ import annotations

import logging
from typing import Any

from ai import config
from ai.narrator import Narrator
from ai.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("game_rpg.ai")

# One short atmospheric paragraph; keep output deliberately small.
FALLBACK_MODEL = "claude-opus-4-8"


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

        prompt = build_user_prompt(events, context)

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
