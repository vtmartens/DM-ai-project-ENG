from entities.player import Player
from items.item import Item
from entities.entity import Entity, ASSOCIATED_SKILLS
from core.enemy_abilities import load_abilities
from util.data_manager import get_data_manager

class NPC(Entity):
    def __init__(self, name, token=None):
        # Load the NPC's data from the JSON file
        self.data_manager = get_data_manager()
        self.npc_data = self.data_manager.get_npc_data(name)
        
        # Use the provided token or the one defined in the data, otherwise use "N" as default
        token = token or self.npc_data.get("token", "N")
        
        # Call the base class constructor
        super().__init__(name, hp=10, hp_max=10, strength_base=13, defense=1, token=token)
        
        # NPC-specific attributes
        self.current_state = "default"
        self.background = ""
        self.profession = ""
        self.group = None
        self.friendly = True
        self.ability_ids = []
        self.abilities = []
        self.ally_ability_ids = []

        # NPC-specific initializations
        self._initialize_attributes()
        
        # Conversations are no longer loaded here, but dynamically when needed
        
    def _initialize_attributes(self):
        """Initializes NPC-specific attributes for each NPC from the external data"""
        # If we have no data for this NPC, keep the default values
        if not self.npc_data:
            return
            
        # Set the attributes from the loaded data
        self.hp_max = self.npc_data.get("hp_max", 10)
        self.hp = self.hp_max
        self.gold = self.npc_data.get("gold", 0)
        self.strength_base = self.npc_data.get("strength_base", 10)
        self.defense = self.npc_data.get("defense", 1)
        ac = self.npc_data.get("ac")
        self.armor_class_value = int(ac) if ac is not None else None
        self.level = self.npc_data.get("level", 1)
        
        # Set optional attributes if present in the data
        if "dexterity_base" in self.npc_data:
            self.dexterity_base = self.npc_data["dexterity_base"]
        if "constitution_base" in self.npc_data:
            self.constitution_base = self.npc_data["constitution_base"]
        if "intelligence_base" in self.npc_data:
            self.intelligence_base = self.npc_data["intelligence_base"]
        if "wisdom_base" in self.npc_data:
            self.wisdom_base = self.npc_data["wisdom_base"]
        if "charisma_base" in self.npc_data:
            self.charisma_base = self.npc_data["charisma_base"]
            
        # Recalculate all the modifiers
        self.modifier_strength = self.calculate_modifier(self.strength_base)
        self.modifier_dexterity = self.calculate_modifier(self.dexterity_base)
        self.modifier_constitution = self.calculate_modifier(self.constitution_base)
        self.modifier_intelligence = self.calculate_modifier(self.intelligence_base)
        self.modifier_wisdom = self.calculate_modifier(self.wisdom_base)
        self.modifier_charisma = self.calculate_modifier(self.charisma_base)
        
        # Set background and profession
        self.background = self.npc_data.get("background", "")
        self.profession = self.npc_data.get("profession", "")
        self.friendly = bool(self.npc_data.get("friendly", True))
        self.ability_ids = list(self.npc_data.get("abilities", []))
        self.abilities = load_abilities(self.ability_ids)
        self.ally_ability_ids = list(
            self.npc_data.get("ally_abilities", [])
        )
        
        # Load the inventory
        self.inventory = []
        self.weapon = None
        self.armor = None
        self.accessories = []
        
        # Populate the inventory
        for item_data in self.npc_data.get("inventory", []):
            item = Item(
                item_data["name"],
                item_data["type"],
                item_data.get("effect", item_data.get("stats", {})),
                item_data.get("value", 0),
                item_data.get("description", ""),
                rarity=item_data.get("rarity", "common"),
            )
            self.inventory.append(item)
            
            # Automatically equip the items marked as equipped
            if item_data.get("equipped", False):
                if item_data["type"] == "weapon" and not self.weapon:
                    self.weapon = item
                elif item_data["type"] == "armor" and not self.armor:
                    self.armor = item
                elif item_data["type"] == "accessory":
                    self.accessories.append(item)

    def change_state(self, new_state):
        """
        Changes the character's state

        Args:
            new_state (str): The character's new state
        """
        self.current_state = new_state

    def get_conversation(self, state=None):
        """
        Gets the conversation data for the specified state

        Args:
            state (str, optional): The conversation state

        Returns:
            dict: Conversation data, or None if it does not exist
        """
        # If no state is specified, use the current state
        state = state or self.current_state
        
        # Load the conversation from the JSON file
        conv_data = self.data_manager.get_npc_conversation(self.name, state)
        
        # Convert the data format from the JSON file to the format used internally
        if conv_data:
            # Work on a copy: DataManager caches this dict. Mutating the cached
            # options in place made the second call see tuples, skip them, and
            # overwrite the options with an empty list.
            conv_data = dict(conv_data)

            # Adapt the options format if necessary
            if "options" in conv_data:
                options = []
                for opt in conv_data["options"]:
                    # Handle array, tuple and object formats, in any call order.
                    # The optional third element carries a visibility condition;
                    # dropping it made every quest-gated option always visible.
                    if isinstance(opt, (list, tuple)) and len(opt) >= 2:
                        options.append(tuple(opt[:3]))
                    elif isinstance(opt, dict):
                        option = (opt.get("text", ""), opt.get("destination"))
                        if opt.get("condition") is not None:
                            option += (opt["condition"],)
                        options.append(option)
                conv_data["options"] = options

            return conv_data
        
        return None
        
    def show_info(self):
        """
        Shows the NPC's information

        Returns:
            str: Formatted NPC information
        """
        info = f"=== {self.name} ===\n"
        info += f"Profession: {self.profession}\n"
        info += f"Background: {self.background}\n"
        info += f"HP: {self.hp}/{self.hp_max}\n"
        info += f"Gold: {self.gold}\n"
        info += "Inventory:\n"
        for item in self.inventory:
            info += f"- {item.name} ({item.type}): {item.description}\n"
        return info

    def attack(self, target, game=None):
        """Attacks a target using the unified method"""
        # Use the base class method to handle the attack
        return super().attack(target, game)

    def transfer_gold(self, player, quantity, game=None):
        """
        Transfers gold from the NPC to the player

        Args:
            player (Player): The player who receives the gold
            quantity (int): Amount of gold to transfer
            game: Reference to the main game object

        Returns:
            bool: True if the transfer succeeded, False if the NPC does not have enough gold
        """
        if self.gold >= quantity:
            self.gold -= quantity
            player.add_gold(quantity, game)
            return True
        return False

    def to_dict(self, already_serialized=None):
        """
        Converts the NPC into a dictionary for serialization.

        Args:
            already_serialized (set, optional): Set of IDs of already serialized objects

        Returns:
            dict: Dictionary representation of the NPC
        """
        # Get the base dictionary from the parent class
        data = super().to_dict(already_serialized)
        
        # Add NPC-specific attributes
        data.update({
            "current_state": self.current_state,
            "background": self.background,
            "profession": self.profession,
            "group": getattr(self, "group", None),
            "ally_ability_ids": list(
                getattr(self, "ally_ability_ids", [])
            ),
            # Conversations are not serialized because they are loaded dynamically
        })
        
        return data
        
    @classmethod
    def from_dict(cls, data):
        """
        Creates an NPC instance from a dictionary.

        Args:
            data (dict): Dictionary with the NPC's data

        Returns:
            NPC: New NPC instance
        """
        # First create an NPC instance with only the name
        npc = cls(
            name=data.get("name", "Unknown"),
            token=data.get("token", "N")
        )
        
        # Manually set the serialized attributes
        npc.hp = data.get("hp", 10)
        npc.hp_max = data.get("hp_max", 10)
        npc.x = data.get("x", 0)
        npc.y = data.get("y", 0)
        npc.current_map = data.get("current_map")
        npc.skill_proficiencies = data.get("skill_proficiencies", {})
        npc.proficiency_bonus = data.get("proficiency_bonus", 2)
        npc.gold = data.get("gold", 0)
        npc.experience = data.get("experience", 0)
        npc.level = data.get("level", 1)
        npc.defense = data.get("defense", 0)
        npc.armor_class_value = data.get("armor_class_value")
        
        # Set the base values that were serialized
        npc.strength_base = data.get("strength_base", 10)
        npc.dexterity_base = data.get("dexterity_base", 10)
        npc.constitution_base = data.get("constitution_base", 10)
        npc.intelligence_base = data.get("intelligence_base", 10)
        npc.wisdom_base = data.get("wisdom_base", 10)
        npc.charisma_base = data.get("charisma_base", 10)
        
        # Recalculate the modifiers
        npc.modifier_strength = npc.calculate_modifier(npc.strength_base)
        npc.modifier_dexterity = npc.calculate_modifier(npc.dexterity_base)
        npc.modifier_constitution = npc.calculate_modifier(npc.constitution_base)
        npc.modifier_intelligence = npc.calculate_modifier(npc.intelligence_base)
        npc.modifier_wisdom = npc.calculate_modifier(npc.wisdom_base)
        npc.modifier_charisma = npc.calculate_modifier(npc.charisma_base)
        
        # Set specific attributes
        npc.current_state = data.get("current_state", "default")
        npc.background = data.get("background", "")
        npc.profession = data.get("profession", "")
        npc.group = data.get("group")
        npc.conditions = dict(data.get("conditions", {}) or {})
        npc.ally_ability_ids = list(
            data.get("ally_ability_ids", npc.ally_ability_ids) or []
        )

        return npc
