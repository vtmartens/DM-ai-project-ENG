import random
from core.io_interface import TerminalIO
from util.dice import roll_d20

# Map of skills associated with attributes (D&D 5e style)
ASSOCIATED_SKILLS = {
    "acrobatics": "dexterity",
    "stealth": "dexterity",
    "gambling": "dexterity",
    "animal_handling": "wisdom",
    "perception": "wisdom",
    "insight": "wisdom",
    "nature": "intelligence",
    "religion": "intelligence",
    "arcana": "intelligence",
    "history": "intelligence",
    "investigation": "intelligence",
    "persuasion": "charisma",
    "intimidation": "charisma",
    "deception": "charisma",
    "athletics": "strength",
    "survival": "wisdom",
    "medicine": "wisdom"
}

class Dice:
    def __init__(self, faces):
        self.faces = faces

    def roll(self):
        return random.randint(1, self.faces)

class Entity:
    def __init__(self, name, hp=10, hp_max=10, strength_base=10, defense=0, dexterity_base=10, constitution_base=10, intelligence_base=10, wisdom_base=10, charisma_base=10, token="and"):
        self.name = name
        self.hp = hp
        self.hp_max = hp_max
        self.token = token
        
        # Base attribute values
        self.strength_base = strength_base
        self.dexterity_base = dexterity_base
        self.constitution_base = constitution_base
        self.intelligence_base = intelligence_base
        self.wisdom_base = wisdom_base
        self.charisma_base = charisma_base
        
        # Calculated modifiers
        self.modifier_strength = self.calculate_modifier(strength_base)
        self.modifier_dexterity = self.calculate_modifier(dexterity_base)
        self.modifier_constitution = self.calculate_modifier(constitution_base)
        self.modifier_intelligence = self.calculate_modifier(intelligence_base)
        self.modifier_wisdom = self.calculate_modifier(wisdom_base)
        self.modifier_charisma = self.calculate_modifier(charisma_base)
        
        # Position attributes
        self.x = 0
        self.y = 0
        self.current_map = None
        
        # Skill proficiencies
        self.skill_proficiencies = {}  # Example: {"perception": True, "persuasion": False}
        self.proficiency_bonus = 2  # Can grow with the level
        
        # Other attributes
        self.defense = defense
        self.armor_class_value = getattr(self, "armor_class_value", None)
        self.inventory = []
        self.gold = 0
        self.experience = 0
        self.level = 1
        self.weapon = None
        self.armor = None
        self.accessories = []
        
        # Game context
        self.game = None
        
    def set_game_context(self, game):
        """
        Sets the game context for this entity.

        Args:
            game: The game instance
        """
        self.game = game
        
        # Propagate the context to the objects contained in the inventory
        for item in self.inventory:
            if hasattr(item, 'set_game_context'):
                item.set_game_context(game)
                
    def take_damage(self, damage, game=None):
        """Unified method for taking damage, accounting for defense."""
        # Use the stored game context if none is provided
        game_ctx = game if game else getattr(self, 'game', None)

        effective_damage = max(1, int(damage) - int(self.defense))
        self.hp = max(0, self.hp - effective_damage)

        if game_ctx:
            game_ctx.io.show_message(f"{self.name} takes {effective_damage} damage!")

        return self.hp > 0
        
    def attack(self, target, game=None):
        """Unified method for attacking"""
        # Use the stored game context if none is provided
        game_ctx = game if game else getattr(self, 'game', None)
        
        damage = self.modifier_strength
        
        if game_ctx:
            game_ctx.io.show_message(f"{self.name} attacks {target.name} and deals {damage} damage!")
            
        return target.take_damage(damage, game_ctx)
        
    def heal(self, quantity, game=None):
        """Heals the entity"""
        # Use the stored game context if none is provided
        game_ctx = game if game else getattr(self, 'game', None)
        
        self.hp = min(self.hp_max, self.hp + quantity)
        
        if game_ctx:
            game_ctx.io.show_message(f"{self.name} recovers {quantity} hit points!")
        
    def add_item(self, item):
        """Adds an item to the inventory"""
        added = item
        # If the item is a string, check whether it matches a known item
        if isinstance(item, str):
            from util.data_manager import get_data_manager
            from items.item import Item

            data_manager = get_data_manager()

            # Search the potions
            potions = data_manager.load_data("items", "potions.json")
            for potion in potions:
                if potion["name"] == item or (item == "Potion" and potion["name"] == "Healing Potion"):
                    # Create a corresponding item
                    new_item = Item.from_dict(potion)
                    self.inventory.append(new_item)
                    added = new_item
                    break
            else:
                # If no matches are found, add it as a string
                self.inventory.append(item)
        else:
            self.inventory.append(item)

        # Only the player has achievement and quest tracking; NPC inventories
        # are ignored by both hooks.
        name = getattr(added, "name", added if isinstance(added, str) else None)

        from core.quests import record_item_acquired

        record_item_acquired(self, name)

        from core.achievements import record_event

        record_event(self, "item_collected", item=name)
        
    def remove_item(self, item_name):
        """Removes an item from the inventory"""
        for item in self.inventory:
            if (isinstance(item, str) and item == item_name) or (hasattr(item, 'name') and item.name == item_name):
                self.inventory.remove(item)
                return True
        return False
        
    def is_alive(self):
        """Checks whether the entity is alive"""
        return self.hp > 0
        
    def wound(self, damage, game):
        """Alternative method for taking damage, for compatibility"""
        return self.take_damage(damage, game)
        
    def add_gold(self, quantity, game=None):
        """Adds gold to the entity"""
        # Use the stored game context if none is provided
        game_ctx = game if game else getattr(self, 'game', None)

        self.gold += quantity
        # Gold can satisfy the "accumulate N coins" achievement.
        from core.achievements import record_event

        record_event(self, "gold_changed", game=game_ctx)

        if game_ctx:
            game_ctx.io.show_message(f"{self.name} received {quantity} gold coins! (Total: {self.gold})")
        
    def gain_experience(self, quantity, game=None):
        """Adds experience and checks whether leveling up is possible"""
        # Use the stored game context if none is provided
        game_ctx = game if game else getattr(self, 'game', None)
        
        self.experience += quantity
        
        # Level-up check: 100 * current level
        required_experience = 100 * self.level
        
        if self.experience >= required_experience:
            self.level += 1
            self.experience -= required_experience
            self._ascend_level(game_ctx)
            return True
        return False
        
    def _ascend_level(self, game=None):
        """Applies the improvements for leveling up"""
        # Use the stored game context if none is provided
        game_ctx = game if game else getattr(self, 'game', None)
        
        self.hp_max += 5
        self.hp = self.hp_max  # Fully heal when leveling up

        # Increment a random base value
        import random
        attributes = ["strength_base", "dexterity_base", "constitution_base", 
                          "intelligence_base", "wisdom_base", "charisma_base"]
        attribute_to_increase = random.choice(attributes)
        
        setattr(self, attribute_to_increase, getattr(self, attribute_to_increase) + 1)
        # Recalculate the corresponding modifier
        modifier_name = f"modifier_{attribute_to_increase[:-5]}"  # Remove "_base"
        setattr(self, modifier_name, self.calculate_modifier(getattr(self, attribute_to_increase)))
        
        self.defense += 1
        
        if game_ctx:
            game_ctx.io.show_message(f"\n*** {self.name} has reached level {self.level}! ***")
            game_ctx.io.show_message(f"Their {attribute_to_increase.replace('_base', '')}, armor class and maximum health have increased!")

    def roll_flags(self, kind="check"):
        """Returns (advantage, disadvantage) from active conditions."""
        conditions = getattr(self, "conditions", None)
        if not isinstance(conditions, dict):
            return False, False
        advantage = bool(
            conditions.get("advantage")
            or conditions.get(f"{kind}_advantage")
        )
        disadvantage = bool(
            conditions.get("disadvantage")
            or conditions.get(f"{kind}_disadvantage")
        )

        from core.conditions import condition_roll_flags

        condition_advantage, condition_disadvantage = condition_roll_flags(
            self, kind
        )
        return (
            advantage or condition_advantage,
            disadvantage or condition_disadvantage,
        )

    def ability_check(self, ability, difficulty, game=None, advantage=None, disadvantage=None):
        # Use the stored game context if none is provided
        game_ctx = game if game else getattr(self, 'game', None)

        condition_advantage, condition_disadvantage = self.roll_flags("check")
        if advantage is None:
            advantage = condition_advantage
        if disadvantage is None:
            disadvantage = condition_disadvantage

        roll, rolls = roll_d20(bool(advantage), bool(disadvantage))
        modifier = getattr(self, f"modifier_{ability}", 0)
        result = roll + modifier

        if game_ctx:
            mode = None
            if advantage and not disadvantage:
                mode = "advantage"
            elif disadvantage and not advantage:
                mode = "disadvantage"
            if mode:
                game_ctx.io.show_message(
                    f"{self.name} rolls {rolls[0]} / {rolls[1]} ({mode}) "
                    f"+ {modifier} ({ability}) = {result}"
                )
            else:
                game_ctx.io.show_message(
                    f"{self.name} rolls {roll} + {modifier} ({ability}) = {result}"
                )

        return result >= difficulty

    def saving_throw(self, ability, difficulty, game=None, advantage=None, disadvantage=None):
        game_ctx = game if game else getattr(self, 'game', None)

        condition_advantage, condition_disadvantage = self.roll_flags("save")
        if advantage is None:
            advantage = condition_advantage
        if disadvantage is None:
            disadvantage = condition_disadvantage

        roll, rolls = roll_d20(bool(advantage), bool(disadvantage))
        modifier = getattr(self, f"modifier_{ability}", 0)
        result = roll + modifier
        passed = result >= difficulty

        if game_ctx:
            mode = None
            if advantage and not disadvantage:
                mode = "advantage"
            elif disadvantage and not advantage:
                mode = "disadvantage"
            if mode:
                game_ctx.io.show_message(
                    f"{self.name} rolls {rolls[0]} / {rolls[1]} ({mode}) "
                    f"+ {modifier} ({ability}) = {result}"
                )
            else:
                game_ctx.io.show_message(
                    f"{self.name} rolls {roll} + {modifier} ({ability}) = {result}"
                )
            game_ctx.io.show_message(
                f"DC {difficulty}: {'success' if passed else 'failure'}."
            )

        return passed

    def calculate_modifier(self, value):
        return (value - 10) // 2

    @property
    def armor_class(self):
        """Armor class: explicit data value, else 10 + Dexterity + defense."""
        explicit = getattr(self, "armor_class_value", None)
        if explicit is not None:
            return int(explicit)
        return 10 + int(self.dexterity) + int(getattr(self, "defense", 0) or 0)

    @property
    def ac(self):
        """Short alias for armor class used by API snapshots and clients."""
        return self.armor_class

    @staticmethod
    def _weapon_properties(weapon) -> dict:
        if weapon is None or isinstance(weapon, str):
            return {}
        properties = getattr(weapon, "properties", {})
        return properties if isinstance(properties, dict) else {}

    def attack_ability(self) -> str:
        """Returns the ability used for the equipped weapon's attack."""
        properties = self._weapon_properties(getattr(self, "weapon", None))
        attack_stat = properties.get("attack_stat")
        if attack_stat in {
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        }:
            return attack_stat
        if properties.get("ranged"):
            return "dexterity"
        if properties.get("finesse"):
            return (
                "dexterity"
                if int(self.dexterity) > int(self.strength)
                else "strength"
            )
        return "strength"

    @property
    def attack_modifier(self) -> int:
        return int(getattr(self, self.attack_ability(), 0) or 0)

    @property
    def attack_damage_modifier(self) -> int:
        """Damage modifier for the equipped weapon, including weapon bonuses."""
        properties = self._weapon_properties(getattr(self, "weapon", None))
        return self.attack_modifier + int(
            properties.get("damage_bonus", 0) or 0
        )

    @property
    def attack_bonus(self):
        """Bonus added to a d20 attack roll."""
        bonus = self.attack_modifier + int(
            getattr(self, "proficiency_bonus", 0) or 0
        )
        weapon = getattr(self, "weapon", None)
        if weapon is not None and not isinstance(weapon, str):
            bonus += int(getattr(weapon, "effect", {}).get("attack", 0) or 0)
        for accessory in getattr(self, "accessories", []) or []:
            bonus += int(
                getattr(accessory, "effect", {}).get("attack", 0) or 0
            )
        return bonus

    @property
    def strength(self):
        return self.modifier_strength

    @strength.setter
    def strength(self, value):
        self.modifier_strength = value
        
    @property
    def dexterity(self):
        return self.modifier_dexterity
        
    @dexterity.setter
    def dexterity(self, value):
        self.modifier_dexterity = value
        
    @property
    def constitution(self):
        return self.modifier_constitution
        
    @constitution.setter
    def constitution(self, value):
        self.modifier_constitution = value
        
    @property
    def intelligence(self):
        return self.modifier_intelligence
        
    @intelligence.setter
    def intelligence(self, value):
        self.modifier_intelligence = value
        
    @property
    def wisdom(self):
        return self.modifier_wisdom
        
    @wisdom.setter
    def wisdom(self, value):
        self.modifier_wisdom = value
        
    @property
    def charisma(self):
        return self.modifier_charisma
        
    @charisma.setter
    def charisma(self, value):
        self.modifier_charisma = value

    def set_position(self, map_name_or_x, x_or_y=None, y=None):
        """
        Sets the entity's position on a specific map or just the coordinates

        Supports two calling modes:
        1. set_position(map_name, x, y) - sets map and coordinates
        2. set_position(x, y) - sets only the coordinates, keeping the current map

        Args:
            map_name_or_x: Name of the map or the X coordinate
            x_or_y: X or Y coordinate
            y: Y coordinate or None
        """
        if y is None:
            # Old mode: set_position(x, y)
            x = map_name_or_x
            y = x_or_y
            # We do not change current_map
        else:
            # New mode: set_position(map_name, x, y)
            self.current_map = map_name_or_x
            x = x_or_y
        
        self.x = x
        self.y = y
    
    def get_position(self):
        """
        Returns the entity's current position

        Returns:
            tuple: Coordinates (x, y), or None if not set
        """
        if self.current_map:
            return (self.x, self.y)
        return None

    def ability_modifier(self, ability_name, game):
        """Calculates the total modifier of an ability, taking proficiency into account"""
        attribute = ASSOCIATED_SKILLS.get(ability_name.lower())
        if not attribute:
            game.io.show_message(f"Unknown ability: {ability_name}")
            return 0

        modifier_base = getattr(self, f"modifier_{attribute}", 0)
        prof_bonus = self.proficiency_bonus if self.skill_proficiencies.get(ability_name.lower()) else 0
        return modifier_base + prof_bonus

    def to_dict(self, already_serialized=None):
        """
        Converts the entity into a dictionary for serialization.
        Handles circular references through the already_serialized parameter.

        Args:
            already_serialized (set, optional): Set of IDs of already serialized objects

        Returns:
            dict: Dictionary representation of the entity
        """
        # For backward compatibility, if the method is called with a wrong number of parameters
        # behave like the old method
        import inspect
        if already_serialized is not None and not isinstance(already_serialized, set):
            # It could be a mistaken call, ignore the parameter
            already_serialized = None
            
        # Initialize the set if not provided
        if already_serialized is None:
            already_serialized = set()
            
        # Avoid circular references
        if id(self) in already_serialized:
            return {"reference_id": id(self), "name": self.name, "type": "riferimento"}
            
        # Add this object to the set
        already_serialized.add(id(self))
        
        # Function to serialize safely
        def serialize_safely(item):
            if item is None:
                return None
            if not hasattr(item, 'to_dict'):
                if isinstance(item, (str, int, float, bool)):
                    return item
                return getattr(item, 'name', str(item))
                
            # First try with already_serialized
            try:
                return item.to_dict(already_serialized)
            except TypeError:
                # If it fails, try without the parameter
                return item.to_dict()
        
        # Serialize lists safely
        def serialize_list(items):
            result = []
            for item in items:
                result.append(serialize_safely(item))
            return result
        
        return {
            "name": self.name,
            "hp": self.hp,
            "hp_max": self.hp_max,
            "token": self.token,
            "strength_base": self.strength_base,
            "dexterity_base": self.dexterity_base,
            "constitution_base": self.constitution_base,
            "intelligence_base": self.intelligence_base,
            "wisdom_base": self.wisdom_base,
            "charisma_base": self.charisma_base,
            "x": self.x,
            "y": self.y,
            "current_map": self.current_map,
            "skill_proficiencies": self.skill_proficiencies,
            "proficiency_bonus": self.proficiency_bonus,
            "defense": self.defense,
            "armor_class_value": getattr(self, "armor_class_value", None),
            "inventory": serialize_list(self.inventory),
            "gold": self.gold,
            "experience": self.experience,
            "level": self.level,
            "weapon": serialize_safely(self.weapon),
            "armor": serialize_safely(self.armor),
            "accessories": serialize_list(self.accessories),
        }
    
    @classmethod
    def from_dict(cls, data, loaded_objects=None):
        """
        Creates an Entity instance from a dictionary.
        Handles circular references through loaded_objects.

        Args:
            data (dict): Dictionary with the entity's data
            loaded_objects (dict, optional): Dictionary of already loaded objects

        Returns:
            Entity: New Entity instance
        """
        # Handle the reference case
        if data.get("type") == "riferimento" and "reference_id" in data:
            ref_id = data["reference_id"]
            if loaded_objects and ref_id in loaded_objects:
                return loaded_objects[ref_id]
            return None
        
        # Create the base object
        entity = cls(
            name=data.get("name", "Unknown"),
            hp=data.get("hp", 10),
            hp_max=data.get("hp_max", 10),
            strength_base=data.get("strength_base", 10),
            dexterity_base=data.get("dexterity_base", 10),
            constitution_base=data.get("constitution_base", 10),
            intelligence_base=data.get("intelligence_base", 10),
            wisdom_base=data.get("wisdom_base", 10),
            charisma_base=data.get("charisma_base", 10),
            defense=data.get("defense", 0),
            token=data.get("token", "and")
        )
        
        # Register the object for future references
        if loaded_objects is not None:
            loaded_objects[id(entity)] = entity
        
        # Set additional attributes
        entity.x = data.get("x", 0)
        entity.y = data.get("y", 0)
        entity.current_map = data.get("current_map", None)
        entity.skill_proficiencies = data.get("skill_proficiencies", {})
        entity.proficiency_bonus = data.get("proficiency_bonus", 2)
        entity.defense = data.get("defense", 0)
        entity.armor_class_value = data.get("armor_class_value")
        entity.gold = data.get("gold", 0)
        entity.experience = data.get("experience", 0)
        entity.level = data.get("level", 1)
        
        # The complex objects (inventory, weapon, armor, accessories)
        # will be handled in the derived classes
        
        return entity
