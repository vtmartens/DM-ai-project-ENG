from __future__ import annotations

from typing import Any, Protocol


class Narrator(Protocol):
    """Turns deterministic engine input into optional prose."""

    def narrate(
        self, events: list[dict[str, Any]], context: dict[str, Any]
    ) -> str | None:
        """Returns one short paragraph, or None to add nothing."""
        ...

    def hint(self, hint: str, context: dict[str, Any]) -> str | None:
        """Rewrites an engine hint, or returns None to use it unchanged."""
        ...

    def recap(self, summary: str, context: dict[str, Any]) -> str | None:
        """Rewrites a deterministic recap, or returns None to use it unchanged."""
        ...

    def describe(self, scene: str, context: dict[str, Any]) -> str | None:
        """Adds atmosphere around a deterministic scene, or returns None."""
        ...


class NullNarrator:
    """A narrator that never adds text. Useful as an explicit no-op."""

    def narrate(
        self, events: list[dict[str, Any]], context: dict[str, Any]
    ) -> str | None:
        return None

    def hint(self, hint: str, context: dict[str, Any]) -> str | None:
        return None

    def recap(self, summary: str, context: dict[str, Any]) -> str | None:
        return None

    def describe(self, scene: str, context: dict[str, Any]) -> str | None:
        return None
