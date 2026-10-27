"""Deterministic session recap with optional AI rephrasing."""

from __future__ import annotations

import logging
import re
from typing import Any

from ai.context import build_context
from core.conditions import condition_catalogue
from core.factions import reputation_entries, shop_discount

logger = logging.getLogger("game_rpg.ai")

ENGINE_FALLBACK = "Your story has only just begun."

_MENU_LINE = re.compile(r"^\d+[\.\)]\s")
_RECENT_SKIP_TYPES = {
    "prompt",
    "map",
    "hint",
    "recap",
    "narration",
}
_RECENT_SKIP_PREFIXES = (
    "===",
    "COMBAT:",
    "Turn:",
    "HP ",
    "Choice:",
    "Choose",
    "What do you want to do",
    "Welcome ",
    "The tavern remains waiting",
    "You resume the dialogue",
)


def _compact_line(text: Any) -> str | None:
    line = " ".join(str(text or "").split()).strip()
    if not line or line.startswith("Player:"):
        return None
    if _MENU_LINE.match(line) or line.startswith(_RECENT_SKIP_PREFIXES):
        return None
    if "What do you want to do" in line:
        return None
    if any(
        marker in line
        for marker in (
            " - Weapon:",
            " - Armor:",
            " - Accessories:",
            " - Weapons:",
            " - Strength:",
        )
    ):
        return None
    return line if len(line) <= 200 else line[:197] + "..."


def _recent_lines(memory=None, events=None) -> list[str]:
    lines = []
    for entry in memory or []:
        line = _compact_line(entry)
        if line:
            lines.append(line)

    if not lines:
        for event in events or []:
            if not isinstance(event, dict):
                continue
            if event.get("type") in _RECENT_SKIP_TYPES:
                continue
            line = _compact_line(event.get("text"))
            if line:
                lines.append(line)

    # Drop adjacent duplicates and keep the freshest few lines.
    unique = []
    for line in lines:
        if not unique or unique[-1] != line:
            unique.append(line)
    return unique[-4:]


def _condition_labels(conditions) -> list[str]:
    if not isinstance(conditions, dict) or not conditions:
        return []
    catalogue = condition_catalogue()
    fallback = {
        "poison": "Poisoned",
        "guidance": "Guidance",
        "advantage": "Advantage",
        "disadvantage": "Disadvantage",
    }
    labels = []
    for condition_id in conditions:
        definition = catalogue.get(condition_id)
        if isinstance(definition, dict):
            labels.append(definition.get("name", condition_id))
        else:
            labels.append(
                fallback.get(
                    condition_id,
                    str(condition_id).replace("_", " ").title(),
                )
            )
    return labels


def _active_quest_summary(player) -> str | None:
    active = [
        quest
        for quest in (getattr(player, "active_quests", []) or [])
        if isinstance(quest, dict)
    ]
    if not active:
        return None

    if len(active) == 1:
        quest = active[0]
        title = quest.get("title") or quest.get("id") or "Unknown quest"
        objective = quest.get("objective") or ""
        status = (
            "ready to turn in"
            if quest.get("status") == "ready"
            else "in progress"
        )
        summary = f"Active quest: {title}"
        if objective:
            summary += f" — {objective}"
        return summary + f" ({status})."

    titles = [
        str(quest.get("title") or quest.get("id") or "Unknown quest")
        for quest in active[:2]
    ]
    summary = "Active quests: " + ", ".join(titles)
    remaining = len(active) - len(titles)
    if remaining:
        summary += f", and {remaining} more"
    return summary + "."


def _reputation_summary(player) -> str | None:
    entries = [
        entry
        for entry in reputation_entries(player)
        if entry.get("value")
    ]
    if not entries:
        return None
    standing = ", ".join(
        f"{entry['name']} {entry['value']:+d} ({entry['tier_label']})"
        for entry in entries
    )
    summary = "Faction standing: " + standing + "."
    discount = shop_discount(player)
    if discount:
        summary += f" Mirt's Network discount: {discount}%."
    return summary


def _campaign_summary(player) -> str | None:
    claimed = {
        str(flag)
        for flag in (getattr(player, "claimed_rewards", []) or [])
        if isinstance(flag, str)
    }
    completed = {
        str(quest.get("id"))
        for quest in (getattr(player, "completed_quests", []) or [])
        if isinstance(quest, dict) and quest.get("id")
    }
    parts = []
    choices = {
        "runeheart_kept": "you kept the Runeheart Amulet",
        "runeheart_mirt": "you gave the Runeheart to Mirt",
        "runeheart_violet": "you gave the Runeheart to Violet",
    }
    for flag, text in choices.items():
        if flag in claimed:
            parts.append("Runeheart choice: " + text + ".")
            break
    if "sanctum_chapter" in completed:
        parts.append("The Sealed Sanctum is complete.")
    return " ".join(parts) or None


def _party_summary(player) -> str | None:
    from core.party import STANCES, ally_stance

    allies = [
        str(name)
        for name in (getattr(player, "allies", []) or [])
        if isinstance(name, str)
    ]
    if not allies:
        return None
    labels = [
        f"{name} ({STANCES[ally_stance(player, name)].lower()})"
        for name in allies
    ]
    return "Companions: " + ", ".join(labels) + "."


def _rune_trials_summary(player) -> str | None:
    best = int(getattr(player, "rune_trials_best", 0) or 0)
    runs = int(getattr(player, "rune_trials_runs", 0) or 0)
    if not best and not runs:
        return None
    summary = f"Best Rune Trial depth: wave {best}"
    if runs:
        summary += f" ({runs} completed {'run' if runs == 1 else 'runs'})"
    return summary + "."


def build_recap(game, memory=None, events=None) -> str:
    """Builds a short factual recap from the player's current state."""
    player = getattr(game, "player", None)
    if player is None:
        return ENGINE_FALLBACK

    name = str(getattr(player, "name", "") or "You")
    char_class = str(getattr(player, "char_class", "") or "adventurer")
    char_class = char_class.replace("_", " ").title()
    level = int(getattr(player, "level", 1) or 1)
    location = str(getattr(player, "current_map", "") or "").replace("_", " ").title()
    hp = int(getattr(player, "hp", 0) or 0)
    hp_max = int(getattr(player, "hp_max", 0) or 0)
    mana = int(getattr(player, "mana", 0) or 0)
    mana_max = int(getattr(player, "mana_max", 0) or 0)
    gold = int(getattr(player, "gold", 0) or 0)

    place = f"in the {location}" if location else "between places"
    state = f"{name} the {char_class} is level {level}, {place}, with {hp}/{hp_max} HP"
    if mana_max:
        state += f" and {mana}/{mana_max} mana"
    state += f", carrying {gold} gold."
    parts = [state]

    cycle = max(1, int(getattr(player, "cycle", 1) or 1))
    if cycle > 1:
        parts.append(f"This is cycle {cycle} of the story.")

    quest_summary = _active_quest_summary(player)
    if quest_summary:
        parts.append(quest_summary)

    completed = len(getattr(player, "completed_quests", []) or [])
    if completed:
        parts.append(
            f"Completed quests: {completed}."
        )

    conditions = _condition_labels(getattr(player, "conditions", {}))
    if conditions:
        parts.append("Affected by: " + ", ".join(conditions) + ".")

    party_summary = _party_summary(player)
    if party_summary:
        parts.append(party_summary)

    reputation_summary = _reputation_summary(player)
    if reputation_summary:
        parts.append(reputation_summary)

    campaign_summary = _campaign_summary(player)
    if campaign_summary:
        parts.append(campaign_summary)

    trials_summary = _rune_trials_summary(player)
    if trials_summary:
        parts.append(trials_summary)

    shards = int(getattr(player, "rune_shards", 0) or 0)
    if shards:
        parts.append(f"Rune Shards: {shards}.")

    if level >= 10:
        parts.append("Class capstone unlocked.")

    defeats = int(getattr(player, "defeats", 0) or 0)
    if defeats:
        parts.append(
            f"You have been defeated {defeats} "
            f"{'time' if defeats == 1 else 'times'}."
        )

    recent = _recent_lines(memory=memory, events=events)
    if recent:
        parts.append("Recently: " + " ".join(recent))
    else:
        parts.append("Nothing notable has happened yet.")

    return " ".join(parts)


def generate_recap(game, narrator=None, memory=None, events=None) -> dict:
    """Returns ``{"recap": str, "source": "engine"|"ai"}``.

    The deterministic recap is always available. When a narrator is configured,
    it is asked to rephrase it; any failure or refusal keeps the engine text.
    Recaps never change game state.
    """
    try:
        engine_recap = build_recap(game, memory=memory, events=events)
    except Exception as exc:  # a recap must never break the session
        logger.warning("Recap generation failed: %s", exc)
        engine_recap = ENGINE_FALLBACK

    if narrator is None or not hasattr(narrator, "recap"):
        return {"recap": engine_recap, "source": "engine"}

    try:
        context = build_context(game, memory=memory)
        prose = narrator.recap(engine_recap, context)
    except Exception as exc:
        logger.warning("AI recap failed: %s", exc)
        prose = None

    prose = prose.strip() if isinstance(prose, str) else ""
    if prose:
        return {"recap": prose, "source": "ai"}

    return {"recap": engine_recap, "source": "engine"}
