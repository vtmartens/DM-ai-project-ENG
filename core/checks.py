"""Shared skill-check helper for data-driven interactions."""

from __future__ import annotations

from entities.entity import ASSOCIATED_SKILLS
from util.dice import roll_d20


def _consume_guidance(player, game):
    conditions = getattr(player, "conditions", None)
    if not isinstance(conditions, dict):
        return 0
    guidance = conditions.pop("guidance", None)
    if isinstance(guidance, dict):
        bonus = int(guidance.get("bonus", 0) or 0)
    else:
        try:
            bonus = int(guidance or 0)
        except (TypeError, ValueError):
            bonus = 0
    if bonus and game:
        game.io.show_message(f"Guidance adds {bonus} to the check.")
    return bonus


def skill_check(player, skill, difficulty, game=None):
    """Rolls d20 + skill modifier against a difficulty, with Guidance."""
    advantage, disadvantage = player.roll_flags("check")
    roll, rolls = roll_d20(advantage, disadvantage)
    if rolls and game:
        mode = (
            "advantage"
            if advantage and not disadvantage
            else "disadvantage"
        )
        game.io.show_message(
            f"{mode.capitalize()} roll: {rolls[0]} / {rolls[1]} -> {roll}."
        )

    if skill in ASSOCIATED_SKILLS:
        bonus = player.ability_modifier(skill, game)
    else:
        bonus = int(getattr(player, f"modifier_{skill}", 0) or 0)

    guidance = _consume_guidance(player, game)
    total = roll + bonus + guidance
    if game:
        guidance_text = (
            f", +{guidance} Guidance" if guidance else ""
        )
        game.io.show_message(
            f"{skill.title()} check: {roll} + {bonus} (skill"
            f"{guidance_text}) = {total} vs DC {difficulty}."
        )
    return total >= difficulty
