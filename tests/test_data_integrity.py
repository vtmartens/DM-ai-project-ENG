import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS_DIR = ROOT / "data" / "items"
MAPS_DIR = ROOT / "data" / "maps"

INVENTORY_FILES = (
    "potions.json",
    "weapons.json",
    "armor.json",
    "accessories.json",
    "keys.json",
)

# Every type that Item.use() / Item.equip() knows how to handle.
IMPLEMENTED_ITEM_TYPES = {
    "heal",
    "light_heal",
    "grave_heal",
    "buff",
    "poison",
    "bomb",
    "weapon",
    "armor",
    "accessory",
    "key",
}


def _load(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_inventory_item_types_all_have_a_use_path():
    for file_name in INVENTORY_FILES:
        for item in _load(ITEMS_DIR / file_name):
            assert item["type"] in IMPLEMENTED_ITEM_TYPES, (
                f"{file_name}: {item['name']} has unhandled type {item['type']!r}"
            )


def test_inventory_items_have_required_fields():
    for file_name in INVENTORY_FILES:
        for item in _load(ITEMS_DIR / file_name):
            for field in ("name", "type", "effect", "value", "description"):
                assert field in item, f"{file_name}: {item.get('name')} is missing {field}"


def test_map_tokens_are_single_characters():
    objects = _load(ITEMS_DIR / "interactive_objects.json")
    npcs = _load(ROOT / "data" / "npc" / "npcs.json")

    bad = [
        f"{obj.get('name')}: {obj.get('token')!r}"
        for obj in objects
        if len(str(obj.get("token", ""))) != 1
    ]
    bad += [
        f"{name}: {data.get('token')!r}"
        for name, data in npcs.items()
        if len(str(data.get("token", ""))) != 1
    ]

    assert not bad, bad


def test_map_objects_reference_defined_objects():
    objects = {obj["name"] for obj in _load(ITEMS_DIR / "interactive_objects.json")}
    map_objects = _load(ITEMS_DIR / "map_objects.json")

    missing = {
        config["name"]
        for configs in map_objects.values()
        for config in configs
        if config["name"] not in objects
    }

    assert not missing, sorted(missing)


def test_map_start_positions_are_walkable():
    for path in MAPS_DIR.glob("*.json"):
        data = _load(path)
        x, y = data["player_start_position"]
        assert data["grid"][y][x] == 0, (
            f"{path.name}: start position ({x}, {y}) is not an empty cell"
        )


def test_class_ability_definitions_cover_starting_and_progression_abilities():
    classes = _load(ROOT / "data" / "classes" / "classes.json")
    abilities = _load(ROOT / "data" / "classes" / "abilities.json")

    expected_names = set()
    for class_name, data in classes.items():
        class_abilities = list(data["special_abilities"])
        for level, ability_name in data.get("progression", {}).get(
            "abilities_per_level", {}
        ).items():
            assert str(level).isdigit()
            class_abilities.append(ability_name)

        for ability_name in class_abilities:
            expected_names.add(ability_name)
            assert ability_name in abilities, (
                f"{class_name}: {ability_name} has no ability definition"
            )
            assert abilities[ability_name]["class"] == class_name

    assert set(abilities) == expected_names


def test_ability_definitions_are_well_formed():
    abilities = _load(ROOT / "data" / "classes" / "abilities.json")
    supported_effects = {"damage", "heal", "guard", "shield", "evade", "bless"}
    ids = set()

    for name, ability in abilities.items():
        for field in (
            "id",
            "class",
            "description",
            "mana_cost",
            "combat_only",
            "effect",
        ):
            assert field in ability, f"{name} is missing {field}"
        assert ability["id"] not in ids, f"duplicate ability id {ability['id']}"
        ids.add(ability["id"])
        assert isinstance(ability["mana_cost"], int) and ability["mana_cost"] >= 0
        assert isinstance(ability["combat_only"], bool)

        effect = ability["effect"]
        assert effect.get("type") in supported_effects, (
            f"{name} has unsupported effect {effect.get('type')!r}"
        )
        if effect["type"] == "damage":
            assert any(key in effect for key in ("flat", "bonus", "multiplier"))
        elif effect["type"] == "heal":
            assert effect.get("amount", 0) > 0
        elif effect["type"] in ("guard", "shield"):
            assert effect.get("amount", 0) > 0
        elif effect["type"] == "bless":
            assert effect.get("attack", 0) > 0 or effect.get("defense", 0) > 0


def test_quest_targets_are_known_npcs():
    quests = _load(ROOT / "data" / "quests" / "quests.json")
    npcs = _load(ROOT / "data" / "npc" / "npcs.json")

    for quest_id, quest in quests.items():
        target = quest.get("target")
        if quest.get("completion") != "dialogue":
            assert target in npcs, f"{quest_id}: unknown target {target!r}"
        assert quest.get("turn_in") in npcs, (
            f"{quest_id}: unknown turn-in NPC {quest.get('turn_in')!r}"
        )
        assert quest.get("title")
        assert quest.get("objective")


def test_map_refresh_adds_maps_missing_from_an_older_session():
    from world.map_manager import MapManager

    manager = MapManager()
    manager.maps.pop("warehouse", None)

    assert manager.refresh_static_map_data() is True

    warehouse = manager.get_map("warehouse")
    assert warehouse is not None
    assert [npc.name for npc in warehouse.npc.values()] == [
        "Vargas",
        "Hooded Cultist A",
        "Hooded Cultist B",
    ]


def test_npc_conversation_options_are_idempotent():
    from entities.npc import NPC
    from util.data_manager import get_data_manager

    # Reload in case an earlier test already converted the cached node.
    get_data_manager().load_data("npc", "conversations.json", reload=True)
    npc = NPC("Durnan")

    first = npc.get_conversation("start")
    second = npc.get_conversation("start")

    assert first["options"]
    assert second["options"] == first["options"]


def test_tavern_exit_door_changes_map(recording_io):
    from core.game import Game
    from entities.player import Player
    from states.tavern import TavernState

    game = Game(Player("Door Tester", "fighter"), TavernState(), recording_io)
    game.set_initial_map("tavern")
    game.player.set_position("tavern", 12, 13)

    result = game.player.move(0, 1, game.map_manager)

    assert result["success"] is True
    assert result["change_map"] is True
    assert game.player.current_map == "market"
    assert (game.player.x, game.player.y) == (12, 2)


def test_tavern_exit_enters_market_state():
    from core.game_state import GameState
    from entities.player import Player
    from states.tavern import TavernState

    session = GameState(Player("Door State", "fighter"), TavernState())
    session.process_command("", provide_input=False)
    session.process_command("9")  # open MapState
    session.game.player.set_position("tavern", 12, 13)
    session.io_buffer.clear()

    session.process_command("south")  # step through the exit

    assert type(session.game.current_state()).__name__ == "MarketState"
    assert session.game.player.current_map == "market"
    assert (session.game.player.x, session.game.player.y) == (12, 2)


def test_dialogue_option_targets_exist():
    conversations = _load(ROOT / "data" / "npc" / "conversations.json")

    for npc_name, graph in conversations.items():
        for state_name, node in graph.items():
            for option in node.get("options", []):
                text, target = option[0], option[1]
                if target is not None:
                    assert target in graph, (
                        f"{npc_name}.{state_name}: {text!r} points to missing state {target!r}"
                    )
                if len(option) > 2:
                    condition = option[2]
                    assert isinstance(condition, dict)
                    assert condition.get("quest")
                    assert condition.get("status") in {
                        "active",
                        "ready",
                        "completed",
                    }
