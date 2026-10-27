"""Optional AI phrasing for deterministic engine hints."""

from __future__ import annotations

import logging

from ai.context import build_context
from core.hints import build_hint

logger = logging.getLogger("game_rpg.ai")

ENGINE_FALLBACK = (
    "Explore the area, talk to the people nearby, and check your quest log."
)


def generate_hint(game, narrator=None) -> dict:
    """Returns ``{"hint": str, "source": "engine"|"ai"}``.

    The deterministic hint is always available. When a narrator is configured,
    it is asked to rephrase that hint; any failure or refusal keeps the engine
    text. Hints never change game state.
    """
    try:
        engine_hint = build_hint(game)
    except Exception as exc:  # a hint must never break the session
        logger.warning("Hint generation failed: %s", exc)
        engine_hint = ENGINE_FALLBACK

    if narrator is None or not hasattr(narrator, "hint"):
        return {"hint": engine_hint, "source": "engine"}

    try:
        context = build_context(game)
        prose = narrator.hint(engine_hint, context)
    except Exception as exc:
        logger.warning("AI hint failed: %s", exc)
        prose = None

    prose = prose.strip() if isinstance(prose, str) else ""
    if prose:
        return {"hint": prose, "source": "ai"}

    return {"hint": engine_hint, "source": "engine"}
