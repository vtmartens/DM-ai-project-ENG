"""Environment-driven configuration for the optional AI narrator."""

import os

TRUE_VALUES = {"1", "true", "yes", "on"}

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT = 20.0


def narration_enabled() -> bool:
    """AI narration is opt-in so the game never makes surprise API calls."""
    return os.getenv("DM_AI_NARRATION", "").strip().lower() in TRUE_VALUES


def narration_provider() -> str:
    return os.getenv("DM_AI_PROVIDER", "claude").strip().lower() or "claude"


def narration_model() -> str:
    return os.getenv("DM_AI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def openai_model() -> str:
    """Model name for an OpenAI-compatible endpoint (set DM_AI_MODEL for local models)."""
    return os.getenv("DM_AI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL


def narration_api_key() -> str:
    return (os.getenv("DM_AI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


def narration_base_url() -> str:
    return (os.getenv("DM_AI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip()


def narration_max_tokens() -> int:
    try:
        return max(64, int(os.getenv("DM_AI_MAX_TOKENS", str(DEFAULT_MAX_TOKENS))))
    except ValueError:
        return DEFAULT_MAX_TOKENS


def narration_timeout() -> float:
    try:
        return max(1.0, float(os.getenv("DM_AI_TIMEOUT", str(DEFAULT_TIMEOUT))))
    except ValueError:
        return DEFAULT_TIMEOUT
