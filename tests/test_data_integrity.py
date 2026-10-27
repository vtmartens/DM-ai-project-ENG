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
    supported_effects = {
        "damage",
        "heal",
        "guard",
        "shield",
        "evade",
        "bless",
        "knock",
        "mage_hand",
        "guidance",
    }
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


def test_enemy_ability_definitions_are_well_formed():
    abilities = _load(ROOT / "data" / "monsters" / "abilities.json")
    assert abilities

    for ability_id, ability in abilities.items():
        assert ability.get("id") == ability_id
        assert ability.get("name")
        assert int(ability.get("cooldown", 0)) >= 0

        effect = ability.get("effect", {})
        assert effect.get("type") in {"attack", "heal"}, ability_id
        save = ability.get("save")
        if save is not None:
            assert isinstance(save, dict), ability_id
            assert save.get("ability") in {
                "strength",
                "dexterity",
                "constitution",
                "intelligence",
                "wisdom",
                "charisma",
            }, ability_id
            assert 5 <= int(save.get("dc", 0)) <= 30, ability_id
            assert save.get("success", "half") in {
                "half",
                "negate",
            }, ability_id
            assert effect.get("type") == "attack", ability_id
        if effect["type"] == "attack":
            assert int(effect.get("damage", 0)) > 0, ability_id
            poison = effect.get("poison")
            if poison is not None:
                assert int(poison.get("damage", 0)) > 0, ability_id
                assert int(poison.get("turns", 0)) > 0, ability_id
        else:
            assert int(effect.get("amount", 0)) > 0, ability_id


def test_enemy_ability_references_are_defined():
    abilities = set(_load(ROOT / "data" / "monsters" / "abilities.json"))
    monsters = _load(ROOT / "data" / "monsters" / "monsters.json")
    npcs = _load(ROOT / "data" / "npc" / "npcs.json")

    referenced = set()
    for monster in monsters.values():
        if isinstance(monster, dict):
            referenced.update(monster.get("abilities", []) or [])
    for npc in npcs.values():
        if isinstance(npc, dict):
            referenced.update(npc.get("abilities", []) or [])

    assert referenced <= abilities, sorted(referenced - abilities)


def test_encounter_definitions_are_well_formed():
    encounters = _load(ROOT / "data" / "monsters" / "encounters.json")
    monsters = _load(ROOT / "data" / "monsters" / "monsters.json")
    npcs = _load(ROOT / "data" / "npc" / "npcs.json")
    assert encounters

    for encounter_id, encounter in encounters.items():
        assert encounter.get("title"), encounter_id
        assert encounter.get("description"), encounter_id
        assert encounter.get("difficulty") in {"easy", "medium", "hard"}, encounter_id

        specs = encounter.get("enemies") or []
        assert 1 <= len(specs) <= 4, encounter_id
        for spec in specs:
            assert isinstance(spec, dict), encounter_id
            if spec.get("monster_type"):
                assert spec["monster_type"] in monsters, (
                    f"{encounter_id}: unknown monster {spec['monster_type']!r}"
                )
            elif spec.get("npc"):
                assert spec["npc"] in npcs, (
                    f"{encounter_id}: unknown NPC {spec['npc']!r}"
                )
            else:
                raise AssertionError(
                    f"{encounter_id}: enemy spec needs monster_type or npc"
                )

        reward = encounter.get("reward") or {}
        gold = reward.get("gold", 0)
        experience = reward.get("experience", 0)
        assert isinstance(gold, int) and gold >= 0, encounter_id
        assert isinstance(experience, int) and experience >= 0, encounter_id
        assert gold or experience, encounter_id


def test_quest_targets_are_known_npcs():
    quests = _load(ROOT / "data" / "quests" / "quests.json")
    npcs = _load(ROOT / "data" / "npc" / "npcs.json")

    for quest_id, quest in quests.items():
        target = quest.get("target")
        if quest.get("completion") != "dialogue" and not quest.get("target_item"):
            assert target in npcs, f"{quest_id}: unknown target {target!r}"
        assert quest.get("turn_in") in npcs, (
            f"{quest_id}: unknown turn-in NPC {quest.get('turn_in')!r}"
        )
        assert quest.get("title")
        assert quest.get("objective")


def test_quest_target_and_reward_items_are_defined():
    items = {
        item["name"]
        for file_name in INVENTORY_FILES
        for item in _load(ITEMS_DIR / file_name)
    }
    quests = _load(ROOT / "data" / "quests" / "quests.json")

    for quest_id, quest in quests.items():
        target_item = quest.get("target_item")
        if target_item:
            assert target_item in items, (
                f"{quest_id}: unknown target item {target_item!r}"
            )

        reward_items = (quest.get("reward") or {}).get("items") or []
        for reward_item in reward_items:
            assert reward_item in items, (
                f"{quest_id}: unknown reward item {reward_item!r}"
            )


def test_cellar_npcs_are_defined():
    npcs = _load(ROOT / "data" / "npc" / "npcs.json")
    placements = _load(ROOT / "data" / "npc" / "map_npcs.json")

    for npc_name in placements.get("cellar", []):
        assert npc_name["name"] in npcs, (
            f"cellar NPC {npc_name['name']!r} has no definition in npcs.json"
        )


def test_keyed_map_doors_have_a_matching_key():
    objects = {
        obj["name"]: obj
        for obj in _load(ITEMS_DIR / "interactive_objects.json")
    }
    map_objects = _load(ITEMS_DIR / "map_objects.json")
    keys = _load(ITEMS_DIR / "keys.json")

    def normalize(value):
        return str(value).replace("_", " ").casefold()

    targets = {
        normalize(target)
        for key in keys
        for target in (key.get("effect", {}).get("opens") or [])
    }

    for map_path in MAPS_DIR.glob("*.json"):
        map_data = _load(map_path)
        placed = {
            tuple(config["position"]): config["name"]
            for config in map_objects.get(map_path.stem, [])
        }
        for cell_string in map_data.get("doors", {}):
            cell = eval(cell_string)
            object_name = placed.get(cell)
            if object_name is None:
                continue
            definition = objects.get(object_name, {})
            if definition.get("type") != "door":
                continue
            if not definition.get("requires_key"):
                continue
            wanted = normalize(object_name)
            assert "*" in targets or any(
                target == wanted or target in wanted or wanted in target
                for target in targets
            ), (
                f"{map_path.stem}{cell}: keyed door {object_name!r} "
                "has no matching key"
            )


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
