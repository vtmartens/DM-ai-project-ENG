"""Stealth checks, passive Perception and surprise helpers."""

from __future__ import annotations

from core.checks import skill_check_total


def nearby_observers(game, radius=4):
    """Returns NPCs near the player who could notice movement."""
    player = getattr(game, "player", None)
    if player is None or not getattr(player, "current_map", None):
        return []
    current_map = game.map_manager.get_map(player.current_map)
    if current_map is None:
        return []
    return list(
        current_map.get_nearby_npcs(player.x, player.y, radius).values()
    )


def perception_modifier(npc, game=None):
    """Returns an NPC's Perception modifier, preferring its data stats."""
    npc_data = getattr(npc, "npc_data", {}) or {}
    wisdom = npc_data.get("wisdom", npc_data.get("wisdom_base"))
    if wisdom is None:
        return int(getattr(npc, "modifier_wisdom", 0) or 0)

    modifier = (int(wisdom) - 10) // 2
    proficiencies = getattr(npc, "skill_proficiencies", {}) or {}
    if proficiencies.get("perception"):
        modifier += int(getattr(npc, "proficiency_bonus", 2) or 2)
    return modifier


def passive_perception(npc, game=None):
    return max(1, 10 + perception_modifier(npc, game))


def observer_threshold(game, radius=4):
    """Returns (highest passive Perception, observers) for the nearby area."""
    observers = nearby_observers(game, radius)
    if not observers:
        return None, []
    threshold = max(passive_perception(npc, game) for npc in observers)
    return threshold, observers


def attempt_stealth(player, game, radius=4, moving=False):
    """Rolls Stealth against nearby observers and updates player.stealthed."""
    threshold, observers = observer_threshold(game, radius)
    if not observers:
        player.stealthed = True
        if game and not moving:
            game.io.show_message("You slip into the shadows.")
        return True

    result = skill_check_total(
        player,
        "stealth",
        game=game,
        consume_guidance=True,
        advantage=True if getattr(player, "disguised", False) else None,
    )
    guidance_text = (
        f", +{result['guidance']} Guidance" if result["guidance"] else ""
    )
    if game:
        game.io.show_message(
            f"Stealth check: {result['roll']} + {result['bonus']}"
            f"{guidance_text} = {result['total']} vs passive "
            f"Perception {threshold}."
        )

    passed = result["total"] >= threshold
    player.stealthed = passed
    if game:
        if passed:
            if moving:
                game.io.show_message("You stay out of sight.")
            else:
                game.io.show_message("You slip into the shadows.")
        else:
            observer = max(
                observers,
                key=lambda npc: passive_perception(npc, game),
            )
            game.io.show_message(
                f"{getattr(observer, 'name', 'Someone')} notices you."
            )
    return passed


def maintain_stealth(player, game, radius=4):
    """Re-checks Stealth after a move while hidden."""
    if not bool(getattr(player, "stealthed", False)):
        return True
    return attempt_stealth(player, game, radius=radius, moving=True)


def clear_stealth(player, game=None, message=None):
    """Ends stealth and optionally explains why."""
    was_hidden = bool(getattr(player, "stealthed", False))
    player.stealthed = False
    if was_hidden and game and message:
        game.io.show_message(message)
    return was_hidden
