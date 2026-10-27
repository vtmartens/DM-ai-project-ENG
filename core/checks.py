"""Shared skill-check helpers for data-driven interactions."""

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


def _skill_bonus(entity, skill, game):
    if skill in ASSOCIATED_SKILLS:
        return entity.ability_modifier(skill, game)
    return int(getattr(entity, f"modifier_{skill}", 0) or 0)


def _roll_skill(entity, skill, game=None, consume_guidance=False):
    """Rolls one skill check and returns its component values."""
    advantage, disadvantage = entity.roll_flags("check")
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

    bonus = _skill_bonus(entity, skill, game)
    guidance = _consume_guidance(entity, game) if consume_guidance else 0
    total = roll + bonus + guidance
    return {
        "roll": roll,
        "bonus": bonus,
        "guidance": guidance,
        "total": total,
    }


def skill_check_total(entity, skill, game=None, consume_guidance=False):
    """Rolls one skill check and returns its roll, bonus and total."""
    return _roll_skill(
        entity,
        skill,
        game=game,
        consume_guidance=consume_guidance,
    )


def skill_check(player, skill, difficulty, game=None):
    """Rolls d20 + skill modifier against a difficulty, with Guidance."""
    result = _roll_skill(
        player, skill, game=game, consume_guidance=True
    )
    if game:
        guidance_text = (
            f", +{result['guidance']} Guidance" if result["guidance"] else ""
        )
        game.io.show_message(
            f"{skill.title()} check: {result['roll']} + {result['bonus']} "
            f"(skill{guidance_text}) = {result['total']} vs DC {difficulty}."
        )
    return result["total"] >= difficulty


def contested_skill_check(
    player, player_skill, target, target_skill, game=None
):
    """Rolls opposing skill checks and returns both totals and the winner."""
    player_result = _roll_skill(
        player, player_skill, game=game, consume_guidance=True
    )
    target_result = _roll_skill(
        target, target_skill, game=game, consume_guidance=False
    )
    if game:
        guidance_text = (
            f", +{player_result['guidance']} Guidance"
            if player_result["guidance"]
            else ""
        )
        game.io.show_message(
            f"{player_skill.title()} check: {player_result['roll']} + "
            f"{player_result['bonus']}{guidance_text} = "
            f"{player_result['total']}."
        )
        game.io.show_message(
            f"{getattr(target, 'name', 'The target')} {target_skill.title()} "
            f"check: {target_result['roll']} + {target_result['bonus']} = "
            f"{target_result['total']}."
        )
    return {
        "success": player_result["total"] >= target_result["total"],
        "player_total": player_result["total"],
        "target_total": target_result["total"],
    }
