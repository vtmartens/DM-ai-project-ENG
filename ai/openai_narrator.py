from __future__ import annotations

import logging
from typing import Any

from ai import config
from ai.narrator import Narrator
from ai.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("game_rpg.ai")


class OpenAINarrator(Narrator):
    """Dungeon Master narration through any OpenAI-compatible endpoint.

    Works with the OpenAI API, Ollama, LM Studio, vLLM, OpenRouter, Groq and
    similar gateways. Point ``DM_AI_BASE_URL`` at the endpoint and set
    ``DM_AI_MODEL`` to a model it serves. Like the Claude narrator, any failure
    returns None so the game keeps its deterministic text.
    """

    def __init__(
        self,
        client=None,
        model: str | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        if client is None:
            import openai

            client = openai.OpenAI(
                api_key=api_key or config.narration_api_key() or "not-needed",
                base_url=base_url or config.narration_base_url() or None,
                timeout=timeout or config.narration_timeout(),
            )

        self.client = client
        self.model = model or config.openai_model()
        self.max_tokens = max_tokens or config.narration_max_tokens()
        self._disabled = False

    def narrate(
        self, events: list[dict[str, Any]], context: dict[str, Any]
    ) -> str | None:
        if self._disabled or not events:
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(events, context)},
                ],
            )
        except Exception as exc:
            # Narration is optional: never let it break a turn.
            logger.warning("AI narrator unavailable; using engine text only: %s", exc)
            self._disable_if_permanent(exc)
            return None

        choices = getattr(response, "choices", None) or []
        if not choices:
            return None

        choice = choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason in ("length", "content_filter"):
            logger.info(
                "AI narrator stopped with %s; dropping narration", finish_reason
            )
            return None

        content = getattr(getattr(choice, "message", None), "content", None)
        if not isinstance(content, str):
            return None

        return content.strip() or None

    def _disable_if_permanent(self, exc: Exception) -> None:
        try:
            import openai
        except ImportError:
            return

        permanent = (
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.NotFoundError,
        )
        if isinstance(exc, permanent):
            logger.warning("Disabling AI narration for this process after a permanent error")
            self._disabled = True
