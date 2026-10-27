import json
import os
import random
from core.enemy_abilities import load_abilities
from entities.entity import Entity

class Enemy(Entity):
    def __init__(self, name, hp=10, damage=2, token="M", strength_base=None, defense=0, monster_type=None):
        # If a monster_type is provided, load the data from JSON
        if monster_type:
            monster_data = self._load_data_monster(monster_type)
            if monster_data:
                name = monster_data.get("name", name)
                hp = monster_data.get("stats", {}).get("hp", hp)
                strength_base = monster_data.get("stats", {}).get("strength", 10 + damage * 2)
                defense = monster_data.get("stats", {}).get("defense", 0)
                token = monster_data.get("token", token)
                
                # Specific attributes from JSON
                self.description = monster_data.get("description", "")
                self.weapons = monster_data.get("weapons", [])
                self.attack_effect = monster_data.get("attack_effect", {})
                self.armor = monster_data.get("armor", "")
                self.experience_value = monster_data.get("experience", 50)  # Renamed to avoid conflicts
                self.monster_type = monster_type
                self.ability_ids = list(monster_data.get("abilities", []))
                self.abilities = load_abilities(self.ability_ids)
                stats = monster_data.get("stats", {})
                ac = stats.get("ac")
                self.armor_class_value = int(ac) if ac is not None else None
                self.attack_stat = stats.get("attack_stat")
                self.damage_bonus = int(
                    stats.get("damage_bonus", 0) or 0
                )
                
                # DEBUG
                print(f"DEBUG Enemy - Loading {monster_type}: experience={self.experience_value}")
                
                # Other stats from JSON
                dexterity_base = monster_data.get("stats", {}).get("dexterity", 10)
                constitution_base = monster_data.get("stats", {}).get("constitution", 10)
                intelligence_base = monster_data.get("stats", {}).get("intelligence", 6)
                wisdom_base = monster_data.get("stats", {}).get("wisdom", 8)
                charisma_base = monster_data.get("stats", {}).get("charisma", 6)
                
                # Call the constructor with the data loaded from JSON
                super().__init__(name, hp=hp, hp_max=hp, strength_base=strength_base, defense=defense, token=token,
                                 dexterity_base=dexterity_base, constitution_base=constitution_base, 
                                 intelligence_base=intelligence_base, wisdom_base=wisdom_base, 
                                 charisma_base=charisma_base)
                
                # Set the gold based on JSON
                self.gold = monster_data.get("gold", 10)
                return
        
        # If no monster_type is provided or it is not found in JSON, use the default values
        if strength_base is None:
            strength_base = 10 + damage * 2
            
        # Call the base class constructor with the default values
        super().__init__(name, hp=hp, hp_max=hp, strength_base=strength_base, defense=defense, token=token)
        
        # Base attributes
        self.description = ""
        self.weapons = []
        self.attack_effect = {}
        self.armor = ""
        self.experience_value = 50  # Renamed to avoid conflicts
        self.monster_type = None
        self.ability_ids = []
        self.abilities = []
        self.armor_class_value = None
        self.attack_stat = None
        self.damage_bonus = 0

        # Set the base gold
        self.gold = 10
    
    def _load_data_monster(self, monster_type):
        """Loads a monster's data from the JSON file"""
        file_path = os.path.join("data", "monsters", "monsters.json")
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                monsters = json.load(file)
                return monsters.get(monster_type, None)
        except (FileNotFoundError, json.JSONDecodeError):
            # On error, return None
            return None
    
    @classmethod
    def create_random(cls, difficulty=None):
        """
        Creates a random enemy based on the specified difficulty.

        Args:
            difficulty (str, optional): The enemy's difficulty ('easy', 'medium', 'hard').
                                       If None, picks a random enemy of any difficulty.

        Returns:
            Enemy: A random enemy instance.
        """
        file_path = os.path.join("data", "monsters", "monsters.json")
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                monsters = json.load(file)
                
                # Filter the monsters by difficulty
                if difficulty:
                    filtered_monsters = {k: v for k, v in monsters.items() 
                                      if v.get("difficulty", "medium") == difficulty}
                    if not filtered_monsters:
                        filtered_monsters = monsters  # If there are no monsters of the requested difficulty, use all
                else:
                    filtered_monsters = monsters
                
                # Pick a random monster
                if filtered_monsters:
                    monster_type = random.choice(list(filtered_monsters.keys()))
                    return cls(name="", monster_type=monster_type)
                else:
                    # If there are no monsters in JSON, create a generic enemy
                    return cls("Generic Monster", 15, 3)
        except (FileNotFoundError, json.JSONDecodeError):
            # On error, create a generic enemy
            return cls("Generic Monster", 15, 3)
    
    @classmethod
    def get_monster_types(cls):
        """
        Gets the list of monster types available in the JSON file.

        Returns:
            list: List of available monster types.
        """
        file_path = os.path.join("data", "monsters", "monsters.json")
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                monsters = json.load(file)
                return list(monsters.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            # On error, return an empty list
            return []
    
    def attack(self, player, game=None):
        """Attacks the player using the unified method"""
        # The attack is now fully handled in CombatState._attack_enemy
        # This method is kept for backward compatibility
        return super().attack(player, game)
    
    def to_dict(self):
        """
        Converts the enemy into a dictionary for serialization.

        Returns:
            dict: Dictionary representation of the enemy
        """
        data = super().to_dict()
        data.update({
            "description": self.description,
            "weapons": self.weapons,
            "attack_effect": self.attack_effect,
            "armor": self.armor,
            "experience": self.experience_value,
            "monster_type": self.monster_type,
            "ability_ids": list(getattr(self, "ability_ids", [])),
            "armor_class_value": getattr(self, "armor_class_value", None),
            "attack_stat": getattr(self, "attack_stat", None),
            "damage_bonus": int(getattr(self, "damage_bonus", 0) or 0),
        })
        return data
    
    @classmethod
    def from_dict(cls, data):
        """
        Creates an Enemy instance from a dictionary.

        Args:
            data (dict): Dictionary with the enemy's data

        Returns:
            Enemy: New Enemy instance
        """
        # If we have a monster_type, use it to reload the data
        if "monster_type" in data and data["monster_type"]:
            enemy = cls(name="", monster_type=data["monster_type"])
            
            # Update any specific values
            if "hp" in data:
                enemy.hp = data["hp"]
            if "name" in data:
                enemy.name = data["name"]
            enemy.conditions = dict(data.get("conditions", {}) or {})

            return enemy
        
        # Otherwise create an enemy with the data from the dictionary
        name = data.get("name", "Unknown Monster")
        hp = data.get("hp", 10)
        strength_base = data.get("strength_base", 14)
        defense = data.get("defense", 0)
        token = data.get("token", "M")
        
        enemy = cls(name, hp, 2, token, strength_base, defense)  # 2 is a default damage value
        
        # Update other attributes
        enemy.description = data.get("description", "")
        enemy.weapons = data.get("weapons", [])
        enemy.attack_effect = data.get("attack_effect", {})
        enemy.armor = data.get("armor", "")
        enemy.experience_value = data.get("experience", 50)
        enemy.monster_type = data.get("monster_type", None)
        enemy.ability_ids = list(data.get("ability_ids", []) or [])
        enemy.abilities = load_abilities(enemy.ability_ids)
        enemy.armor_class_value = data.get("armor_class_value")
        enemy.attack_stat = data.get("attack_stat")
        enemy.damage_bonus = int(data.get("damage_bonus", 0) or 0)
        enemy.gold = data.get("gold", 10)
        enemy.conditions = dict(data.get("conditions", {}) or {})

        return enemy
