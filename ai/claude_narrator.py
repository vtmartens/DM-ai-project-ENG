from __future__ import annotations

import logging
from typing import Any

from ai import config
from ai.narrator import Narrator
from ai.prompts import (
    DIALOGUE_SYSTEM_PROMPT,
    HINT_SYSTEM_PROMPT,
    RECAP_SYSTEM_PROMPT,
    SCENE_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_dialogue_prompt,
    build_hint_prompt,
    build_recap_prompt,
    build_scene_prompt,
    build_user_prompt,
)

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
        return self._complete(
            SYSTEM_PROMPT,
            build_user_prompt(events, context),
            self.max_tokens,
        )

    def hint(self, hint: str, context: dict[str, Any]) -> str | None:
        if self._disabled or not hint:
            return None
        return self._complete(
            HINT_SYSTEM_PROMPT,
            build_hint_prompt(hint, context),
            min(self.max_tokens, 256),
        )

    def recap(self, summary: str, context: dict[str, Any]) -> str | None:
        if self._disabled or not summary:
            return None
        return self._complete(
            RECAP_SYSTEM_PROMPT,
            build_recap_prompt(summary, context),
            min(self.max_tokens, 256),
        )

    def describe(self, scene: str, context: dict[str, Any]) -> str | None:
        if self._disabled or not scene:
            return None
        return self._complete(
            SCENE_SYSTEM_PROMPT,
            build_scene_prompt(scene, context),
            min(self.max_tokens, 256),
        )

    def dialogue(self, line: str, context: dict[str, Any]) -> str | None:
        if self._disabled or not line:
            return None
        return self._complete(
            DIALOGUE_SYSTEM_PROMPT,
            build_dialogue_prompt(line, context),
            min(self.max_tokens, 256),
        )

    def _complete(self, system_prompt: str, prompt: str, max_tokens: int) -> str | None:
        if self._disabled:
            return None

        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-06-01"],
                fallbacks=[{"model": FALLBACK_MODEL}],
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            # AI output is optional garnish: never let it break a turn or a hint.
            logger.warning("AI request unavailable; using engine text only: %s", exc)
            self._disable_if_permanent(exc)
            return None

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            logger.info("AI request refused; using engine text only")
            return None
        if stop_reason == "max_tokens":
            logger.warning("AI request hit max_tokens; dropping truncated output")
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
