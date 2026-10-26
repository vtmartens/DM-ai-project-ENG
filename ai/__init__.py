"""Optional AI Dungeon Master narration.

The game engine stays authoritative: ``NarratingIO`` forwards every deterministic
message unchanged and only appends a short prose paragraph before the next prompt.
"""

from ai.io import NarratingIO, attach_game, create_game_io, create_narrator_from_env
from ai.narrator import Narrator, NullNarrator

__all__ = [
    "NarratingIO",
    "Narrator",
    "NullNarrator",
    "attach_game",
    "create_game_io",
    "create_narrator_from_env",
]
