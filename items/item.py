class Item:
    def __init__(self, name, type, effect=None, value=0, description=""):
        self.name = name
        self.type = type
        self.effect = effect or {}
        self.value = value
        self.description = description
        
    def __str__(self):
        return f"{self.name} ({self.description})"
    
    def __repr__(self):
        return f"Item(name={self.name}, type={self.type}, effect={self.effect}, value={self.value}, description={self.description})"

    def use(self, player, game=None):
        if self.type == "heal":
            player.heal(self.effect.get("heal", 0), game)
            if game:
                game.io.show_message(f"You use {self.name} and recover {self.effect.get('heal', 0)} HP.")
            player.remove_item(self.name)
        elif self.type == "light_heal":
            player.heal(self.effect.get("light_heal", 5), game)
            if game:
                game.io.show_message(f"You use {self.name} and recover {self.effect.get('light_heal', 5)} HP.")
            player.remove_item(self.name)
        elif self.type == "grave_heal":
            player.heal(self.effect.get("grave_heal", 15), game)
            if game:
                game.io.show_message(f"You use {self.name} and recover {self.effect.get('grave_heal', 15)} HP.")
            player.remove_item(self.name)
        elif self.type == "weapon":
            self.equip(player, game)
        elif self.type == "armor":
            self.equip(player, game)
        elif self.type == "key":
            if game:
                game.io.show_message(f"You use the key {self.name}, but nothing happens... for now.")
        else:
            if game:
                game.io.show_message(f"The item {self.name} cannot be used directly.")
            return False
        return True

    def sell(self, player, game):
        player.add_gold(self.value, game)
        player.remove_item(self.name)
        game.io.show_message(f"You sold {self.name} for {self.value} gold coins")
    
    def equip(self, player, game=None):
        # Silent version if no game is provided
        if self.type == "weapon":
            # Remove the previous weapon's effects if present
            if player.weapon:
                player.strength -= player.weapon.effect.get("strength", 0)
            player.weapon = self
            player.strength += self.effect.get("strength", 0)
            if game:
                game.io.show_message(f"You equipped {self.name}. Your strength increases by {self.effect.get('strength', 0)}!")
        elif self.type == "armor":
            # Remove the previous armor's effects if present
            if player.armor:
                player.defense -= player.armor.effect.get("defense", 0)
            player.armor = self
            player.defense += self.effect.get("defense", 0)
            if game:
                game.io.show_message(f"You put on {self.name}. Your defense increases by {self.effect.get('defense', 0)}!")
        elif self.type == "accessory":
            player.accessories.append(self)
            # Apply any accessory effects
            for stat, value in self.effect.items():
                if hasattr(player, stat):
                    setattr(player, stat, getattr(player, stat) + value)
            if game:
                game.io.show_message(f"You equipped {self.name} as an accessory.")

    def remove(self, player, game=None):
        # Silent version if no game is provided
        if self.type == "weapon":
            if player.weapon:
                player.strength -= player.weapon.effect.get("strength", 0)
            player.weapon = None
            if game:
                game.io.show_message(f"You removed the weapon {self.name}.")
        elif self.type == "armor":
            if player.armor:
                player.defense -= player.armor.effect.get("defense", 0)
            player.armor = None
            if game:
                game.io.show_message(f"You removed the armor {self.name}.")
        elif self.type == "accessory":
            if self in player.accessories:
                # Remove any accessory effects
                for stat, value in self.effect.items():
                    if hasattr(player, stat):
                        setattr(player, stat, getattr(player, stat) - value)
                player.accessories.remove(self)
            if game:
                game.io.show_message(f"You removed the accessory {self.name}.")
    
    def to_dict(self):
        """
        Converts the item into a dictionary for serialization.

        Returns:
            dict: Dictionary representation of the item
        """
        return {
            "name": self.name,
            "type": self.type,
            "effect": self.effect,
            "value": self.value,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Creates an Item instance from a dictionary.

        Args:
            data (dict): Dictionary with the item's data

        Returns:
            Item: New Item instance
        """
        return cls(
            name=data["name"],
            type=data["type"],
            effect=data.get("effect", {}),
            value=data.get("value", 0),
            description=data.get("description", "")
        )
        
    # Compatibility method with the previous name
    @classmethod 
    def from_dictionary(cls, data):
        """Alias for backward compatibility"""
        return cls.from_dict(data)
    
    
