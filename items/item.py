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

    @staticmethod
    def _combat_context(game):
        """Returns the active combat state, if the item is being used in combat."""
        if not game or not hasattr(game, "current_state"):
            return None
        current = game.current_state()
        if current is not None and type(current).__name__ == "CombatState":
            return current
        return None

    def use(self, player, game=None):
        if self.type in ("heal", "light_heal", "grave_heal"):
            defaults = {"heal": 0, "light_heal": 5, "grave_heal": 15}
            amount = self.effect.get(self.type, defaults[self.type])
            player.heal(amount, game)
            if game:
                game.io.show_message(f"You use {self.name} and recover {amount} HP.")
            player.remove_item(self.name)
        elif self.type == "buff":
            # There is no timed-effect system in the engine yet, so the bonus is
            # applied immediately rather than for a fixed number of turns.
            applied = {}
            for stat, value in self.effect.items():
                if isinstance(value, (int, float)) and hasattr(player, stat):
                    setattr(player, stat, getattr(player, stat) + value)
                    applied[stat] = value
            if not applied:
                if game:
                    game.io.show_message(f"The item {self.name} has no usable effect.")
                return False
            if game:
                bonuses = ", ".join(f"{stat} +{value}" for stat, value in applied.items())
                game.io.show_message(f"You use {self.name} and gain {bonuses}.")
            player.remove_item(self.name)
        elif self.type == "poison":
            combat = self._combat_context(game)
            if combat is None or getattr(combat, "opponent", None) is None:
                if game:
                    game.io.show_message(f"{self.name} can only be used in combat.")
                return False
            damage = self.effect.get("damage", 5)
            combat.opponent.wound(damage, game)
            if game:
                game.io.show_message(
                    f"You apply {self.name} to your weapon and deal {damage} damage to {combat.opponent.name}."
                )
            player.remove_item(self.name)
        elif self.type == "bomb":
            combat = self._combat_context(game)
            if combat is None:
                if game:
                    game.io.show_message(f"{self.name} can only be used in combat.")
                return False
            if game:
                game.io.show_message(f"You throw {self.name} and slip away in the smoke...")
            if hasattr(combat, "_attempt_escape"):
                combat._attempt_escape(game, bonus=5)
            player.remove_item(self.name)
        elif self.type in ("weapon", "armor", "accessory"):
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
    
    
