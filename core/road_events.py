"""Data-driven non-combat and ambush events on the Trade Road."""

from __future__ import annotations

import random

from core.item_catalogue import item_definition
from items.item import Item
from util.data_manager import get_data_manager


def road_event_catalogue() -> dict:
    data = get_data_manager().load_data("road", "road_events.json")
    return data if isinstance(data, dict) else {}


def event_flag(event) -> str:
    return str(
        event.get("reward_flag")
        or f"road_event_{event.get('id', 'unknown')}"
    )


def _already_claimed(player, event) -> bool:
    return event_flag(event) in (
        getattr(player, "claimed_rewards", []) or []
    )


def available_road_events(player) -> list[dict]:
    events = []
    for event in road_event_catalogue().values():
        if not isinstance(event, dict) or not event.get("id"):
            continue
        if event.get("once") and _already_claimed(player, event):
            continue
        events.append(dict(event))
    return events


def choose_road_event(player, chooser=None):
    events = available_road_events(player)
    if not events:
        return None
    if chooser is not None:
        return chooser(events)
    weights = [max(1, int(event.get("weight", 1) or 1)) for event in events]
    return random.choices(events, weights=weights, k=1)[0]


def get_road_event(event_id) -> dict | None:
    event = road_event_catalogue().get(str(event_id or ""))
    return dict(event) if isinstance(event, dict) else None


def start_road_event(game, event_id=None):
    """Selects and starts one road event, returning it when handled."""
    if game is None or getattr(game, "player", None) is None:
        return None

    if event_id is not None:
        event = get_road_event(event_id)
        if event is None or (
            event.get("once") and _already_claimed(game.player, event)
        ):
            return None
    else:
        event = choose_road_event(game.player)
    if event is None:
        return None

    if event.get("type") == "ambush":
        from core.wilderness import start_road_encounter

        return start_road_encounter(game)

    from states.road_event import RoadEventState

    game.push_state(RoadEventState(event, game))
    return event


def mark_event_claimed(player, event) -> None:
    claimed = getattr(player, "claimed_rewards", None)
    if not isinstance(claimed, list):
        claimed = []
        player.claimed_rewards = claimed
    flag = event_flag(event)
    if flag not in claimed:
        claimed.append(flag)


def grant_event_reward(player, reward, game=None) -> list[str]:
    """Applies a gold/XP/item reward and returns granted item names."""
    if not isinstance(reward, dict):
        return []

    gold = int(reward.get("gold", 0) or 0)
    experience = int(reward.get("experience", 0) or 0)
    if gold:
        player.add_gold(gold, game)
    if experience:
        player.gain_experience(experience, game)

    granted = []
    for item_name in reward.get("items", []) or []:
        definition = item_definition(item_name)
        if definition is None:
            continue
        player.add_item(Item.from_dict(definition))
        granted.append(item_name)
        if game:
            game.io.show_message(f"You received: {item_name}.")
    return granted
