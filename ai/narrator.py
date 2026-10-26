from __future__ import annotations

from typing import Any, Protocol


class Narrator(Protocol):
    """Turns a batch of deterministic engine events into optional prose."""

    def narrate(
        self, events: list[dict[str, Any]], context: dict[str, Any]
    ) -> str | None:
        """Returns one short paragraph, or None to add nothing."""
        ...


class NullNarrator:
    """A narrator that never adds text. Useful as an explicit no-op."""

    def narrate(
        self, events: list[dict[str, Any]], context: dict[str, Any]
    ) -> str | None:
        return None
