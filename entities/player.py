import json
import os
from items.item import Item
from entities.entity import Entity, ASSOCIATED_SKILLS

class Player(Entity):
    def __init__(self, name, char_class):
        # Initialize player-specific values
        self.char_class = char_class
        
        # Load the class data from JSON
        self.classes_data = self._load_data_classes()
        
        # Get the base stats for the selected class
        stats_base = self._get_stats_char_class(char_class)
        class_data = self.classes_data.get(char_class, {})
        hp_base = class_data.get("hp_base", stats_base.get("hp_base", 20))

        # Call the base class constructor with values from the chosen class
        super().__init__(name,
                         hp=hp_base,
                         hp_max=hp_base,
                         strength_base=stats_base.get("strength", 12),
                         defense=2, 
                         dexterity_base=stats_base.get("dexterity", 10), 
                         constitution_base=stats_base.get("constitution", 12), 
                         intelligence_base=stats_base.get("intelligence", 10), 
                         wisdom_base=stats_base.get("wisdom", 10), 
                         charisma_base=stats_base.get("charisma", 10), 
                         token="P")  # P for Player

        # Set other values different from the Entity defaults
        self.gold = 100
        # mana_base lives at the top level of the class data, not in base_stats
        self.mana = class_data.get("mana_base", 0)
        self.mana_max = class_data.get("mana_base", 0)
        
        # Initialize quest attributes
        self.progress_quests = {}
        self.active_quests = []
        self.completed_quests = []
        
        # Initialize class-specific skill proficiencies
        self._initialize_skills()
        
        # Class-specific attributes that are not in Entity
        self._initialize_for_char_class()
        self.defense_base = self.defense
        self.initiative_base = self.modifier_dexterity
        self.initiative = self.initiative_base
        self.conditions = {}
        self.allies = []
        self.defeats = 0

        # Achievement tracking (persisted with the player)
        from core.achievements import DEFAULT_ACHIEVEMENT_STATS

        self.achievements = []
        self.achievement_timestamps = {}
        self.achievement_stats = {
            key: (list(value) if isinstance(value, list) else value)
            for key, value in DEFAULT_ACHIEVEMENT_STATS.items()
        }

        self._create_inventory_base()
        self._seed_achievement_items()
        self.recalculate_initiative()

    def _equipment_stat_bonus(self, ability):
        """Returns the equipment bonus applied to an ability modifier."""
        equipment = []
        if getattr(self, "weapon", None):
            equipment.append(self.weapon)
        if getattr(self, "armor", None):
            equipment.append(self.armor)
        equipment.extend(getattr(self, "accessories", []) or [])

        bonus = 0
        for item in equipment:
            if isinstance(item, str):
                continue
            bonus += int(
                getattr(item, "effect", {}).get(ability, 0) or 0
            )
        return bonus

    def _recalculate_ability_modifier(self, ability):
        base = getattr(self, f"{ability}_base")
        setattr(
            self,
            f"modifier_{ability}",
            self.calculate_modifier(base) + self._equipment_stat_bonus(ability),
        )

    def recalculate_initiative(self):
        """Rebuilds initiative from Dexterity and accessory bonuses."""
        accessory_initiative = sum(
            int(getattr(accessory, "effect", {}).get("initiative", 0) or 0)
            for accessory in getattr(self, "accessories", [])
        )
        self.initiative_base = self.modifier_dexterity
        self.initiative = self.initiative_base + accessory_initiative

    def _seed_achievement_items(self):
        """Counts the starting inventory as collected for the collector achievement."""
        collected = self.achievement_stats.setdefault("unique_items_collected", [])
        equipped = [self.weapon, self.armor, *getattr(self, "accessories", [])]
        for item in [*self.inventory, *equipped]:
            name = getattr(item, "name", None)
            if name and name not in collected:
                collected.append(name)

    def _load_data_classes(self):
        """Loads the class data from the JSON file"""
        file_path = os.path.join("data", "classes", "classes.json")
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            # On error, return an empty dictionary
            return {}
    
    def _get_stats_char_class(self, char_class):
        """Gets the base stats for the specified class"""
        if char_class in self.classes_data:
            return self.classes_data[char_class].get("base_stats", {})
        return {}
    
    def _initialize_skills(self):
        """Initializes the skill proficiencies based on the class"""
        # Check whether the class exists in the class data
        if self.char_class in self.classes_data:
            # In the future this could be extended to read the proficiencies from JSON
            pass
        
        # Keep the existing hardcoded proficiencies for compatibility
        if self.char_class == "fighter":
            self.skill_proficiencies["athletics"] = True
            self.skill_proficiencies["intimidation"] = True
        elif self.char_class == "wizard":
            self.skill_proficiencies["arcana"] = True
            self.skill_proficiencies["history"] = True
        elif self.char_class == "rogue":
            self.skill_proficiencies["stealth"] = True
            self.skill_proficiencies["acrobatics"] = True
        # For all other classes, no specific proficiency
    
    def _initialize_for_char_class(self):
        """Sets specific attributes based on the character's class"""
        # If the class exists in the class data
        if self.char_class in self.classes_data:
            class_data = self.classes_data[self.char_class]
            stats_base = class_data.get("base_stats", {})
            
            # Update the base stats with those from JSON
            self.hp = class_data.get("hp_base", self.hp)
            self.hp_max = class_data.get("hp_base", self.hp_max)
            
            # Recalculate the modifiers
            self.modifier_strength = self.calculate_modifier(self.strength_base)
            self.modifier_dexterity = self.calculate_modifier(self.dexterity_base)
            self.modifier_constitution = self.calculate_modifier(self.constitution_base)
            self.modifier_intelligence = self.calculate_modifier(self.intelligence_base)
            self.modifier_wisdom = self.calculate_modifier(self.wisdom_base)
            self.modifier_charisma = self.calculate_modifier(self.charisma_base)
            
            # Rogue-specific attribute
            if self.char_class == "rogue":
                self.luck = 5
        else:
            # Handling of the currently hardcoded classes for compatibility
            if self.char_class == "fighter":
                self.hp += 5
                self.hp_max += 5
                self.strength_base += 4
                self.modifier_strength = self.calculate_modifier(self.strength_base)
            elif self.char_class == "wizard":
                self.strength_base -= 2
                self.intelligence_base = 16
                self.modifier_strength = self.calculate_modifier(self.strength_base)
                self.modifier_intelligence = self.calculate_modifier(self.intelligence_base)
            elif self.char_class == "rogue":
                self.dexterity_base = 16
                self.modifier_dexterity = self.calculate_modifier(self.dexterity_base)
                self.luck = 5
    
    def _create_inventory_base(self):
        """Creates a base inventory based on the character's class"""
        # Common items for everyone
        potion = Item("Healing Potion", "heal", {"heal": 10}, 25, "Restores 10 hit points")
        key = Item("Common Key", "key", {}, 1, "A simple key that might open doors or chests")

        # Base weapons for all classes
        weapon_base = None
        armor_base = None
        
        # If the class exists in the class data, use the equipment defined in JSON
        if self.char_class in self.classes_data:
            equipment = self.classes_data[self.char_class].get("starting_equipment", [])
            
            # Create items based on the equipment defined in JSON
            if equipment and len(equipment) >= 3:
                weapon_name = equipment[0]
                armor_name = equipment[2] if len(equipment) > 2 else "Simple Clothes"
                
                if "sword" in weapon_name.lower() or "mace" in weapon_name.lower():
                    weapon_base = Item(weapon_name, "weapon", {"strength": 3}, 15, f"A sturdy {weapon_name.lower()}")
                elif "staff" in weapon_name.lower():
                    weapon_base = Item(weapon_name, "weapon", {"strength": 1, "intelligence": 2}, 20, f"A {weapon_name.lower()} that amplifies magical powers")
                elif "dagger" in weapon_name.lower():
                    weapon_base = Item(weapon_name, "weapon", {"strength": 2, "dexterity": 1}, 12, f"A sharp, handy {weapon_name.lower()}")
                else:
                    weapon_base = Item(weapon_name, "weapon", {"strength": 2}, 10, f"A {weapon_name.lower()}")
                
                if "chainmail" in armor_name.lower() or "heavy" in armor_name.lower():
                    armor_base = Item(armor_name, "armor", {"defense": 3}, 25, f"A {armor_name.lower()} that offers good protection")
                elif "robe" in armor_name.lower() or "wizard" in armor_name.lower():
                    armor_base = Item(armor_name, "armor", {"defense": 1, "intelligence": 1}, 15, f"A light {armor_name.lower()} with magical properties")
                elif "leather" in armor_name.lower() or "light" in armor_name.lower():
                    armor_base = Item(armor_name, "armor", {"defense": 2, "dexterity": 1}, 18, "A light armor that does not restrict movement")
                else:
                    armor_base = Item(armor_name, "armor", {"defense": 1}, 10, f"A {armor_name.lower()}")
            else:
                # Default equipment if not defined in JSON
                weapon_base = Item("Traveler's Staff", "weapon", {"strength": 1}, 5, "A simple wooden staff")
                armor_base = Item("Sturdy Clothes", "armor", {"defense": 1}, 5, "Reinforced clothes that offer minimal protection")
        else:
            # Use the existing code for the default classes
            if self.char_class == "fighter":
                weapon_base = Item("Short Sword", "weapon", {"strength": 3}, 15, "A short but sturdy sword")
                armor_base = Item("Chainmail", "armor", {"defense": 3}, 25, "A chainmail shirt that offers good protection")

            elif self.char_class == "wizard":
                weapon_base = Item("Arcane Staff", "weapon", {"strength": 1, "intelligence": 2}, 20, "A staff that amplifies magical powers")
                armor_base = Item("Wizard's Robe", "armor", {"defense": 1, "intelligence": 1}, 15, "A light robe with magical properties")

            elif self.char_class == "rogue":
                weapon_base = Item("dagger", "weapon", {"strength": 2, "dexterity": 1}, 12, "A sharp, handy dagger")
                armor_base = Item("Leather Armor", "armor", {"defense": 2, "dexterity": 1}, 18, "A light armor that does not restrict movement")

            else:
                weapon_base = Item("Traveler's Staff", "weapon", {"strength": 1}, 5, "A simple wooden staff")
                armor_base = Item("Sturdy Clothes", "armor", {"defense": 1}, 5, "Reinforced clothes that offer minimal protection")
        
        # Add the items to the inventory
        self.inventory.append(potion)
        self.inventory.append(key)
        self.inventory.append(weapon_base)
        self.inventory.append(armor_base)
        
        # Automatically equip the base weapon and armor
        weapon_base.equip(self)
        armor_base.equip(self)
        
        # Add a base accessory based on the class
        if self.char_class == "fighter":
            amulet = Item("Amulet of Strength", "accessory", {"strength": 1}, 10, "An amulet that increases strength")
            self.inventory.append(amulet)
            amulet.equip(self)
        elif self.char_class == "wizard":
            ring = Item("Ring of the Mind", "accessory", {"intelligence": 1}, 10, "A ring that improves concentration")
            self.inventory.append(ring)
            ring.equip(self)
        elif self.char_class == "rogue":
            gloves = Item("Thief's Gloves", "accessory", {"dexterity": 1}, 10, "Gloves that improve dexterity")
            self.inventory.append(gloves)
            gloves.equip(self)
        elif self.char_class == "cleric":
            symbol = Item("Holy Symbol", "accessory", {"wisdom": 1}, 10, "A holy symbol that increases wisdom")
            self.inventory.append(symbol)
            symbol.equip(self)

    def attack(self, enemy, game=None):
        """Attacks an enemy using the unified method"""
        # Use the base class method to handle the attack
        return super().attack(enemy, game)
    
    def _ascend_level(self, game=None):
        """Applies class-specific HP/mana growth and ability unlocks."""
        class_data = self.classes_data.get(self.char_class, {})
        progression = class_data.get("progression", {})
        hp_gain = int(progression.get("hp_per_level", 5) or 0)
        mana_gain = int(progression.get("mana_per_level", 0) or 0)

        self.hp_max += hp_gain
        self.hp = self.hp_max  # Fully heal when leveling up
        if mana_gain:
            self.mana_max += mana_gain
            self.mana = min(self.mana_max, self.mana + mana_gain)

        # Keep the existing generic stat/defense growth as well.
        import random

        attributes = [
            "strength_base",
            "dexterity_base",
            "constitution_base",
            "intelligence_base",
            "wisdom_base",
            "charisma_base",
        ]
        attribute_to_increase = random.choice(attributes)
        setattr(
            self,
            attribute_to_increase,
            getattr(self, attribute_to_increase) + 1,
        )
        self._recalculate_ability_modifier(attribute_to_increase[:-5])

        if not hasattr(self, "defense_base"):
            gear_defense = (
                int(getattr(getattr(self, "armor", None), "effect", {}).get(
                    "defense", 0
                )
                or 0)
            )
            gear_defense += sum(
                int(getattr(accessory, "effect", {}).get("defense", 0) or 0)
                for accessory in getattr(self, "accessories", [])
            )
            self.defense_base = max(0, self.defense - gear_defense)
        self.defense_base += 1
        self.defense += 1

        self.recalculate_initiative()

        from core.abilities import abilities_unlocked_at_level

        unlocked = abilities_unlocked_at_level(self, self.level)

        if game:
            game.io.show_message(
                f"\n*** {self.name} has reached level {self.level}! ***"
            )
            growth = f"Maximum HP increased by {hp_gain}"
            if mana_gain:
                growth += f" and mana by {mana_gain}"
            game.io.show_message(growth + ".")
            game.io.show_message(
                f"Your {attribute_to_increase.replace('_base', '')} and armor class increased!"
            )
            for ability_name in unlocked:
                game.io.show_message(f"You learned {ability_name}!")
            game.io.show_message("You have grown stronger!")

        return unlocked

    def move(self, dx, dy, map_manager):
        """
        Attempts to move the player in the specified direction

        Args:
            dx (int): Movement along the X axis
            dy (int): Movement along the Y axis
            map_manager: Game map manager

        Returns:
            bool: True if the movement occurred, False otherwise
        """
        if not map_manager or not self.current_map:
            return False
        
        return map_manager.move_player(self, dx, dy)
    
    def interact_with_adjacent_item(self, map_manager, game=None):
        """
        Interacts with the object adjacent to the player, if present

        Args:
            map_manager: Game map manager
            game: Reference to the main game object

        Returns:
            bool: True if an interaction occurred, False otherwise
        """
        if not map_manager or not self.current_map:
            return False
        
        map = map_manager.get_map(self.current_map)
        if not map:
            return False
        
        # Check in all adjacent directions
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            x, y = self.x + dx, self.y + dy
            item = map.get_item_at(x, y)
            if item:
                if game and game.io:
                    game.io.show_message(f"You interact with {item.name}")
                item.interact(self)
                return True
            
        if game and game.io:
            game.io.show_message("There are no objects nearby to interact with.")
        return False
    
    def interact_with_adjacent_npc(self, map_manager, game=None):
        """
        Interacts with the NPC adjacent to the player, if present

        Args:
            map_manager: Game map manager
            game: Reference to the main game object (optional if stored)

        Returns:
            bool: True if an interaction occurred, False otherwise
        """
        # Use the stored game context if none is provided
        game_ctx = game if game else getattr(self, 'game', None)
        
        if not map_manager or not self.current_map:
            return False
        
        map = map_manager.get_map(self.current_map)
        if not map:
            return False
        
        # Check in all adjacent directions
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            x, y = self.x + dx, self.y + dy
            npc = map.get_npc_at(x, y)
            if npc:
                if game_ctx and game_ctx.io:
                    game_ctx.io.show_message(f"You talk with {npc.name}")
                from states.dialogue import DialogueState
                game_ctx.push_state(DialogueState(npc))
                return True
            
        if game_ctx and game_ctx.io:
            game_ctx.io.show_message("There are no characters nearby to talk to.")
        return False
    
    def get_nearby_items(self, map_manager, radius=1):
        """
        Returns the objects near the player

        Args:
            map_manager: Game map manager
            radius (int): Search radius

        Returns:
            dict: Dictionary of nearby objects
        """
        if not map_manager or not self.current_map:
            return {}
        
        map = map_manager.get_map(self.current_map)
        if not map:
            return {}
        
        return map.get_nearby_items(self.x, self.y, radius)
    
    def get_nearby_npcs(self, map_manager, radius=1):
        """
        Returns the NPCs near the player

        Args:
            map_manager: Game map manager
            radius (int): Search radius

        Returns:
            dict: Dictionary of nearby NPCs
        """
        if not map_manager or not self.current_map:
            return {}
        
        map = map_manager.get_map(self.current_map)
        if not map:
            return {}
        
        return map.get_nearby_npcs(self.x, self.y, radius)

    def to_dict(self, already_serialized=None):
        """
        Converts the player into a dictionary for serialization.

        Args:
            already_serialized (set, optional): Set of IDs of already serialized objects

        Returns:
            dict: Dictionary representation of the player
        """
        # Get the base dictionary from the parent class
        data = super().to_dict(already_serialized)
        
        # Add player-specific attributes
        data.update({
            "char_class": self.char_class,
            "progress_quests": self.progress_quests,
            "active_quests": self.active_quests,
            "completed_quests": self.completed_quests,
            "position": [self.x, self.y],  # For compatibility
            "mana": getattr(self, "mana", 0),
            "mana_max": getattr(self, "mana_max", 0),
            "initiative": getattr(self, "initiative", 0),
            "defense_base": getattr(self, "defense_base", 2),
            "initiative_base": getattr(
                self, "initiative_base", self.modifier_dexterity
            ),
            "conditions": dict(getattr(self, "conditions", {})),
            "allies": list(getattr(self, "allies", [])),
            "defeats": int(getattr(self, "defeats", 0) or 0),
            "achievements": list(getattr(self, "achievements", [])),
            "achievement_timestamps": dict(
                getattr(self, "achievement_timestamps", {})
            ),
            "achievement_stats": {
                key: (list(value) if isinstance(value, list) else value)
                for key, value in getattr(
                    self, "achievement_stats", {}
                ).items()
            },
        })
        
        return data
        
    @classmethod
    def from_dict(cls, data):
        """
        Creates a Player instance from a dictionary.

        Args:
            data (dict): Dictionary with the player's data

        Returns:
            Player: New Player instance
        """
        # Extract the subclass-specific data
        name = data.get("name", "Unknown")
        char_class = data.get("char_class", "fighter")
        
        # Create the instance with the base parameters
        player = cls(name, char_class)
        
        # Set the base attributes using the base class
        # We skip the initialization that Entity.from_dict performs
        # because the Player constructor has specific logic

        # Set the base attributes
        player.hp = data.get("hp", player.hp)
        player.hp_max = data.get("hp_max", player.hp_max)
        player.strength_base = data.get("strength_base", player.strength_base)
        player.dexterity_base = data.get("dexterity_base", player.dexterity_base)
        player.constitution_base = data.get("constitution_base", player.constitution_base)
        player.intelligence_base = data.get("intelligence_base", player.intelligence_base)
        player.wisdom_base = data.get("wisdom_base", player.wisdom_base)
        player.charisma_base = data.get("charisma_base", player.charisma_base)
        
        # Set the modifiers
        player.modifier_strength = player.calculate_modifier(player.strength_base)
        player.modifier_dexterity = player.calculate_modifier(player.dexterity_base)
        player.modifier_constitution = player.calculate_modifier(player.constitution_base)
        player.modifier_intelligence = player.calculate_modifier(player.intelligence_base)
        player.modifier_wisdom = player.calculate_modifier(player.wisdom_base)
        player.modifier_charisma = player.calculate_modifier(player.charisma_base)
        
        # Set position
        if "position" in data and isinstance(data["position"], list) and len(data["position"]) >= 2:
            player.x, player.y = data["position"]
        else:
            player.x = data.get("x", 0)
            player.y = data.get("y", 0)
            
        player.current_map = data.get("current_map")
        
        # Restore other attributes
        player.skill_proficiencies = data.get("skill_proficiencies", {})
        player.proficiency_bonus = data.get("proficiency_bonus", 2)
        player.gold = data.get("gold", 0)
        player.experience = data.get("experience", 0)
        player.level = data.get("level", 1)
        player.mana = data.get("mana", getattr(player, "mana", 0))
        player.mana_max = data.get("mana_max", getattr(player, "mana_max", 0))
        player.conditions = dict(data.get("conditions", {}))
        player.allies = list(data.get("allies", []))
        player.defeats = int(data.get("defeats", 0) or 0)

        # Achievement progress (absent in saves written before the feature).
        from core.achievements import coerce_stats

        saved_achievements = data.get("achievements", [])
        if not isinstance(saved_achievements, list):
            saved_achievements = []
        player.achievements = [
            achievement_id
            for achievement_id in saved_achievements
            if isinstance(achievement_id, str)
        ]
        saved_timestamps = data.get("achievement_timestamps", {})
        if not isinstance(saved_timestamps, dict):
            saved_timestamps = {}
        player.achievement_timestamps = {
            achievement_id: timestamp
            for achievement_id, timestamp in saved_timestamps.items()
            if isinstance(achievement_id, str)
        }
        player.achievement_stats = coerce_stats(data.get("achievement_stats"))

        # Handle quests
        player.progress_quests = data.get("progress_quests", {})
        player.active_quests = data.get("active_quests", [])
        player.completed_quests = data.get("completed_quests", [])
        
        # Loading the inventory and equipment requires objects
        # This is done externally or in a more complex way
        from items.item import Item
        
        # Handle inventory
        inventory_raw = data.get("inventory", [])
        inventory = []
        
        for item in inventory_raw:
            if isinstance(item, dict):
                inventory.append(Item.from_dict(item))
            elif isinstance(item, str):
                # Create a generic object if only the name is available
                inventory.append(Item(item, "common"))
                
        player.inventory = inventory
        
        # Rebuild equipment first so its bonuses can be applied to the base stats.
        weapon_data = data.get("weapon")
        if isinstance(weapon_data, dict):
            weapon = Item.from_dict(weapon_data)
        elif isinstance(weapon_data, str):
            weapon = Item(weapon_data, "weapon")
        else:
            weapon = None

        armor_data = data.get("armor")
        if isinstance(armor_data, dict):
            armor = Item.from_dict(armor_data)
        elif isinstance(armor_data, str):
            armor = Item(armor_data, "armor")
        else:
            armor = None

        accessories = []
        for acc in data.get("accessories", []):
            if isinstance(acc, dict):
                accessories.append(Item.from_dict(acc))
            elif isinstance(acc, str):
                accessories.append(Item(acc, "accessory"))

        armor_defense = (
            int(armor.effect.get("defense", 0) or 0) if armor else 0
        )
        accessory_defense = sum(
            int(accessory.effect.get("defense", 0) or 0)
            for accessory in accessories
        )
        accessory_initiative = sum(
            int(accessory.effect.get("initiative", 0) or 0)
            for accessory in accessories
        )

        saved_defense = int(data.get("defense", 2) or 0)
        saved_initiative = int(
            data.get("initiative", player.modifier_dexterity) or 0
        )

        # New saves store the non-equipment base explicitly. Older saves stored
        # only the effective value, so remove gear bonuses to recover the base.
        player.defense_base = int(
            data.get(
                "defense_base",
                max(0, saved_defense - armor_defense - accessory_defense),
            )
            or 0
        )
        player.initiative_base = int(
            data.get(
                "initiative_base",
                saved_initiative - accessory_initiative,
            )
            or 0
        )
        player.defense = player.defense_base
        player.initiative = player.initiative_base

        player.weapon = weapon
        player.armor = armor
        player.accessories = accessories
        for item in (weapon, armor, *accessories):
            if item is not None:
                Item._apply_effect(player, item.effect)
        player.recalculate_initiative()

        return player
