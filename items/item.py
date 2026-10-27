from items.keys import key_opens


class Item:
    def __init__(
        self,
        name,
        type,
        effect=None,
        value=0,
        description="",
        rarity="common",
        properties=None,
    ):
        self.name = name
        self.type = type
        self.effect = effect or {}
        self.value = value
        self.description = description
        # Optional metadata used by achievement conditions and future loot tables.
        self.rarity = rarity
        # Weapon metadata such as finesse, ranged, attack_stat or damage_bonus.
        self.properties = dict(properties or {})
        
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
            if self.effect.get("remove_poison"):
                conditions = getattr(player, "conditions", None)
                if isinstance(conditions, dict):
                    removed = conditions.pop("poison", None)
                    if game:
                        game.io.show_message(
                            "The antidote neutralizes the poison."
                            if removed
                            else "The antidote finds no poison to neutralize."
                        )
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
            damage = int(self.effect.get("damage", 5) or 5)
            duration = int(self.effect.get("duration", 1) or 1)
            if hasattr(combat, "apply_poison"):
                combat.apply_poison(damage, duration, game)
            else:
                combat.opponent.wound(damage, game)
            if game:
                game.io.show_message(f"You apply {self.name} to your weapon.")
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
        elif self.type == "document":
            if game:
                game.io.show_message(
                    f"You read {self.name}. {self.description}"
                )
        elif self.type in ("weapon", "armor", "accessory"):
            self.equip(player, game)
        elif self.type == "key":
            if game and getattr(player, "current_map", None):
                current_map = game.map_manager.get_map(player.current_map)
                if current_map:
                    for (x, y), obj in list(current_map.items.items()):
                        if abs(x - player.x) + abs(y - player.y) != 1:
                            continue
                        if not getattr(obj, "requires_key", False):
                            continue
                        if getattr(obj, "state", "") not in {"closed", "locked"}:
                            continue
                        if not key_opens(self, getattr(obj, "name", "")):
                            continue
                        obj.interact(player, game)
                        return True
            if game:
                game.io.show_message(
                    f"You have no matching lock nearby for {self.name}."
                )
            return False
        else:
            if game:
                game.io.show_message(f"The item {self.name} cannot be used directly.")
            return False
        return True

    def sell(self, player, game):
        player.add_gold(self.value, game)
        player.remove_item(self.name)
        game.io.show_message(f"You sold {self.name} for {self.value} gold coins")
    
    @staticmethod
    def _apply_effect(player, effect, direction=1):
        """Adds or removes every numeric equipment effect on the player."""
        for stat, value in (effect or {}).items():
            if isinstance(value, (int, float)) and hasattr(player, stat):
                setattr(player, stat, getattr(player, stat) + direction * value)

    def equip(self, player, game=None):
        # Silent version if no game is provided
        if self.type == "weapon":
            # Remove the previous weapon's effects if present
            if player.weapon:
                self._apply_effect(player, player.weapon.effect, -1)
            player.weapon = self
            self._apply_effect(player, self.effect)
            if game:
                game.io.show_message(f"You equipped {self.name}.")
        elif self.type == "armor":
            # Remove the previous armor's effects if present
            if player.armor:
                self._apply_effect(player, player.armor.effect, -1)
            player.armor = self
            self._apply_effect(player, self.effect)
            if game:
                game.io.show_message(f"You put on {self.name}.")
        elif self.type == "accessory":
            player.accessories.append(self)
            self._apply_effect(player, self.effect)
            if game:
                game.io.show_message(f"You equipped {self.name} as an accessory.")

        if hasattr(player, "recalculate_initiative"):
            player.recalculate_initiative()

        # Equipment can satisfy the "equip a legendary weapon" achievement.
        from core.achievements import record_event

        record_event(player, "equip", game=game, item=self)

    def remove(self, player, game=None):
        # Silent version if no game is provided
        if self.type == "weapon":
            if player.weapon is self:
                self._apply_effect(player, self.effect, -1)
                player.weapon = None
            if game:
                game.io.show_message(f"You removed the weapon {self.name}.")
        elif self.type == "armor":
            if player.armor is self:
                self._apply_effect(player, self.effect, -1)
                player.armor = None
            if game:
                game.io.show_message(f"You removed the armor {self.name}.")
        elif self.type == "accessory":
            if self in player.accessories:
                self._apply_effect(player, self.effect, -1)
                player.accessories.remove(self)
            if game:
                game.io.show_message(f"You removed the accessory {self.name}.")

        if hasattr(player, "recalculate_initiative"):
            player.recalculate_initiative()
    
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
            "description": self.description,
            "rarity": self.rarity,
            "properties": dict(getattr(self, "properties", {}) or {}),
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
            description=data.get("description", ""),
            rarity=data.get("rarity", "common"),
            properties=data.get("properties", {}),
        )
        
    # Compatibility method with the previous name
    @classmethod 
    def from_dictionary(cls, data):
        """Alias for backward compatibility"""
        return cls.from_dict(data)
    
    
