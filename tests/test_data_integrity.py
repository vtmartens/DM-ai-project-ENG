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


def test_map_start_positions_are_walkable():
    for path in MAPS_DIR.glob("*.json"):
        data = _load(path)
        x, y = data["player_start_position"]
        assert data["grid"][y][x] == 0, (
            f"{path.name}: start position ({x}, {y}) is not an empty cell"
        )


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


def test_dialogue_option_targets_exist():
    conversations = _load(ROOT / "data" / "npc" / "conversations.json")

    for npc_name, graph in conversations.items():
        for state_name, node in graph.items():
            for text, target in node.get("options", []):
                if target is not None:
                    assert target in graph, (
                        f"{npc_name}.{state_name}: {text!r} points to missing state {target!r}"
                    )
