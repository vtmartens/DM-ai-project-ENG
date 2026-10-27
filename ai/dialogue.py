"""Optional in-character colour for deterministic NPC dialogue lines."""

from __future__ import annotations

import logging

from ai.context import build_context

logger = logging.getLogger("game_rpg.ai")


def _current_dialogue(game):
    from states.dialogue import DialogueState

    state = game.current_state() if hasattr(game, "current_state") else None
    if not isinstance(state, DialogueState) or getattr(state, "npc", None) is None:
        return None, None, ""
    npc = state.npc
    conversation = npc.get_conversation(state.current_state) or {}
    line = str(conversation.get("text", "") or "").strip()
    return state, npc, line


def generate_dialogue_voice(game, narrator=None, memory=None) -> dict:
    """Returns ``{"voice": str, "source": "engine"|"ai", ...}``.

    The engine line is authoritative. A narrator may add delivery and tone
    around the same words, but it cannot change the line or the options. Any
    failure or refusal returns the engine line. No game state is changed.
    """
    state, npc, line = _current_dialogue(game)
    if state is None:
        return {
            "voice": "",
            "source": "engine",
            "npc": None,
            "node": None,
        }

    result = {
        "voice": line,
        "source": "engine",
        "npc": getattr(npc, "name", "NPC"),
        "node": getattr(state, "current_state", "start"),
    }
    if narrator is None or not hasattr(narrator, "dialogue") or not line:
        return result

    try:
        context = build_context(game, memory=memory)
        context["dialogue"] = {
            "npc": getattr(npc, "name", "NPC"),
            "profession": getattr(npc, "profession", ""),
            "node": getattr(state, "current_state", "start"),
        }
        prose = narrator.dialogue(line, context)
    except Exception as exc:
        logger.warning("AI dialogue voice failed: %s", exc)
        prose = None

    prose = prose.strip() if isinstance(prose, str) else ""
    if prose:
        result["voice"] = prose
        result["source"] = "ai"
    return result
