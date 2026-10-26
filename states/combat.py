from states.base_state import BaseState
from entities.enemy import Enemy
from entities.player import Player
from entities.npc import NPC
from util.dice import Dice

class CombatState(BaseState):
    def __init__(self, enemy=None, hostile_npc=None):
        """
        Initialize the combat state.
        
        Args:
            enemy (Enemy, optional): A traditional enemy
            hostile_npc (NPC, optional): An NPC that has become hostile
        """
        self.enemy = enemy
        self.hostile_npc = hostile_npc
        self.turn = 1
        self.opponent = enemy if enemy else hostile_npc
        # Initialize the dice for the various rolls during combat
        self.dice_d20 = Dice(20)
        self.dice_d100 = Dice(100)
        # Add the phase to handle the asynchronous flow
        self.phase = "selection"
        # To store any temporary data between phases
        self.temporary_data = {}
        # Ability effects that persist across turns (guard, shield, evade, bless)
        self.effects = {}
        # Result of the most recent ability attempt (used by POST /use_ability)
        self.last_ability_used = None
        # Whether initiative has already decided who acts first
        self._initiative_checked = False
        
    def run(self, game):
        player = game.player
        
        # Show the combat stats in every phase
        self._show_state_combat(player, game)
        
        # Check whether the combat is over
        if self._check_end_combat(game):
            return

        if self._check_initiative(player, game):
            return

        # Handle the flow based on the current phase
        if self.phase == "selection":
            self._phase_selection(player, game)
        elif self.phase == "run_action":
            self._phase_run_action(player, game)
        elif self.phase == "enemy_attack":
            self._phase_attack_enemy(player, game)
        elif self.phase == "end_turn":
            self._phase_end_turn(player, game)
        elif self.phase == "use_item":
            self._phase_use_item(player, game)
        elif self.phase == "change_equipment":
            self._phase_change_equipment(player, game)
        elif self.phase == "use_ability":
            self._phase_use_ability(player, game)

    def _phase_selection(self, player, game):
        """Action selection phase"""
        # Ask the player for their action
        game.io.show_message("\nWhat do you want to do?")
        game.io.show_message("1. Attack")
        game.io.show_message("2. Use item")
        game.io.show_message("3. Change equipment")
        game.io.show_message("4. Flee")
        game.io.show_message("5. Use ability")
        
        # Get the command from the input (already set by the web system)
        game.io.request_input("Choice: ")
        
        # Move to the next phase
        self.phase = "run_action"
    
    def _phase_run_action(self, player, game):
        """Execution phase of the chosen action"""
        selection_input = game.io.last_input
        
        # Function to process the textual commands
        def process_command_combat(cmd):
            cmd = cmd.lower().strip()
            
            # Mapping of text commands to actions
            if any(x in cmd for x in ["attack", "hit", "1"]):
                return "1"
            elif any(x in cmd for x in ["use", "item", "potion", "2"]):
                return "2"
            elif any(x in cmd for x in ["change", "equipment", "weapon", "3"]):
                return "3"
            elif any(x in cmd for x in ["flee", "escape", "run", "4"]):
                return "4"
            else:
                return None
        
        ability_name = self._parse_ability_command(player, selection_input)
        if ability_name:
            self._manage_ability(player, game, ability_name)
            return

        # Process the textual or numeric command
        if selection_input.isdigit() and selection_input in ["1", "2", "3", "4", "5"]:
            selection = selection_input
        else:
            selection = process_command_combat(selection_input)

        if selection == "1":
            self._manage_attack(player, game)
            # Move to the enemy attack phase if the opponent is still alive
            if self.opponent.hp > 0:
                self.phase = "enemy_attack"
            else:
                self.phase = "end_turn"
        elif selection == "2":
            self.phase = "use_item"
            self.temporary_data.clear()
            return
        elif selection == "3":
            self.phase = "change_equipment"
            self.temporary_data.clear()
            return
        elif selection == "4":
            self._attempt_escape(game)
            if game.current_state() == self:  # If we have not exited the state
                # Move to the enemy attack phase if the opponent is still alive
                if self.opponent.hp > 0:
                    self.phase = "enemy_attack"
                else:
                    self.phase = "end_turn"
        elif selection == "5":
            self.phase = "use_ability"
            self.temporary_data.clear()
            return
        else:
            game.io.show_message(f"Invalid action: '{selection_input}'!")
            self.phase = "selection"  # Return to the selection phase
    
    def _phase_attack_enemy(self, player, game):
        """Opponent attack phase"""
        self._attack_enemy(player, game)
        self.phase = "end_turn"
    
    def _phase_end_turn(self, player, game):
        """End turn phase"""
        self._tick_poison(game)
        self._tick_player_poison(player, game)
        # Increment the turn
        self.turn += 1
        # Return to the selection phase for the next turn
        self.phase = "selection"
        
    def _phase_use_item(self, player, game):
        """Phase for using items"""
        if not player.inventory:
            game.io.show_message("\nYou have no items to use!")
            self.phase = "selection"
            return
            
        if "show_inventory" not in self.temporary_data:
            # First call: show the inventory
            game.io.show_message("\nWhich item do you want to use?")
            for i, item in enumerate(player.inventory, 1):
                game.io.show_message(f"{i}. {item}")
            game.io.show_message(f"{len(player.inventory) + 1}. Cancel")
            
            self.temporary_data["show_inventory"] = True
            game.io.request_input("\nChoose: ")
            return
        
        # Second call: process the choice
        try:
            selection = int(game.io.last_input)
            if 1 <= selection <= len(player.inventory):
                item = player.inventory[selection - 1]
                
                # Use the item's use method
                if hasattr(item, 'use'):
                    item.use(player, game)
                else:
                    # Backward compatibility with strings
                    self._apply_effect_item(player, item, game)
            elif selection == len(player.inventory) + 1:
                # Cancel
                self.phase = "selection"
                self.temporary_data.clear()
                return
            else:
                game.io.show_message("Invalid choice.")
                self.phase = "selection"
                self.temporary_data.clear()
                return
        except ValueError:
            game.io.show_message("You must enter a number.")
            self.phase = "selection"
            self.temporary_data.clear()
            return
            
        # Clear the temporary data
        self.temporary_data.clear()
        
        # Move to the enemy attack phase if the opponent is still alive
        if self.opponent.hp > 0:
            self.phase = "enemy_attack"
        else:
            self.phase = "end_turn"
    
    def _phase_change_equipment(self, player, game):
        """Phase for changing equipment"""
        if "phase_equip" not in self.temporary_data:
            # First call: show the options
            game.io.show_message("\nWhat do you want to change?")
            game.io.show_message("1. Weapon")
            game.io.show_message("2. Armor")
            game.io.show_message("3. Accessory")
            game.io.show_message("4. Cancel")
            
            self.temporary_data["phase_equip"] = "selection_type"
            game.io.request_input("Choice: ")
            return
        
        if self.temporary_data["phase_equip"] == "selection_type":
            # Process the equipment type choice
            selection = game.io.last_input
            
            if selection == "1":
                self.temporary_data["type_equip"] = "weapon"
                # Filter the weapons from the inventory
                weapons = [item for item in player.inventory 
                       if not isinstance(item, str) and hasattr(item, 'type') and item.type == "weapon"]
                
                if not weapons:
                    game.io.show_message("\nYou have no other weapons in your inventory!")
                    self.temporary_data.clear()
                    self.phase = "selection"
                    return
                
                game.io.show_message("\nWhich weapon do you want to equip?")
                for i, weapon in enumerate(weapons, 1):
                    bonus = f" (Strength +{weapon.effect.get('strength', 0)})" if hasattr(weapon, 'effect') else ""
                    game.io.show_message(f"{i}. {weapon.name}{bonus}")
                game.io.show_message(f"{len(weapons) + 1}. Cancel")
                
                self.temporary_data["items"] = weapons
                self.temporary_data["phase_equip"] = "selection_item"
                game.io.request_input("\nChoose: ")
                return
                
            elif selection == "2":
                self.temporary_data["type_equip"] = "armor"
                # Filter the armor from the inventory
                armor_items = [item for item in player.inventory 
                           if not isinstance(item, str) and hasattr(item, 'type') and item.type == "armor"]
                
                if not armor_items:
                    game.io.show_message("\nYou have no other armor in your inventory!")
                    self.temporary_data.clear()
                    self.phase = "selection"
                    return
                
                game.io.show_message("\nWhich armor do you want to equip?")
                for i, armor in enumerate(armor_items, 1):
                    bonus = f" (Defense +{armor.effect.get('defense', 0)})" if hasattr(armor, 'effect') else ""
                    game.io.show_message(f"{i}. {armor.name}{bonus}")
                game.io.show_message(f"{len(armor_items) + 1}. Cancel")
                
                self.temporary_data["items"] = armor_items
                self.temporary_data["phase_equip"] = "selection_item"
                game.io.request_input("\nChoose: ")
                return
                
            elif selection == "3":
                self.temporary_data["type_equip"] = "accessory"
                # Filter the accessories from the inventory
                accessories = [item for item in player.inventory 
                            if not isinstance(item, str) and hasattr(item, 'type') and item.type == "accessory"]
                
                if not accessories:
                    game.io.show_message("\nYou have no other accessories in your inventory!")
                    self.temporary_data.clear()
                    self.phase = "selection"
                    return
                
                game.io.show_message("\nWhich accessory do you want to equip?")
                for i, accessory in enumerate(accessories, 1):
                    bonus = ""
                    if hasattr(accessory, 'effect'):
                        bonus = " ("
                        for stat, val in accessory.effect.items():
                            bonus += f"{stat.capitalize()} +{val}, "
                        bonus = bonus[:-2] + ")"
                    game.io.show_message(f"{i}. {accessory.name}{bonus}")
                game.io.show_message(f"{len(accessories) + 1}. Cancel")
                
                self.temporary_data["items"] = accessories
                self.temporary_data["phase_equip"] = "selection_item"
                game.io.request_input("\nChoose: ")
                return
                
            elif selection == "4":
                # Cancel
                self.temporary_data.clear()
                self.phase = "selection"
                return
            else:
                game.io.show_message("Invalid choice.")
                self.temporary_data.clear()
                self.phase = "selection"
                return
                
        elif self.temporary_data["phase_equip"] == "selection_item":
            # Process the item choice
            items = self.temporary_data.get("items", [])
            
            try:
                selection = int(game.io.last_input)
                if 1 <= selection <= len(items):
                    item = items[selection - 1]
                    item.equip(player)
                    game.io.show_message(f"\nYou equipped {item.name}!")
                elif selection == len(items) + 1:
                    # Cancel
                    pass
                else:
                    game.io.show_message("Invalid choice.")
            except ValueError:
                game.io.show_message("You must enter a number.")
            
            # Clear the temporary data and move to the next phase
            self.temporary_data.clear()
            
            # Move to the enemy attack phase if the opponent is still alive
            if self.opponent.hp > 0:
                self.phase = "enemy_attack"
            else:
                self.phase = "end_turn"
                
    def _parse_ability_command(self, player, command):
        """Returns an ability name for 'use ability X', 'cast X' or a bare name."""
        text = str(command or "").strip()
        if not text:
            return None

        from core.abilities import resolve_ability

        lowered = text.casefold()
        for prefix in ("use ability ", "cast spell ", "cast ", "ability "):
            if lowered.startswith(prefix):
                name, _ = resolve_ability(player, text[len(prefix) :].strip())
                return name

        name, _ = resolve_ability(player, text)
        return name

    def _manage_ability(self, player, game, ability_name):
        from core.abilities import resolve_ability, use_ability

        name, definition = resolve_ability(player, ability_name)
        if not name:
            game.io.show_message(f"You don't know an ability called {ability_name}.")
            self.phase = "selection"
            return

        used = use_ability(game, name, definition)
        self.last_ability_used = used
        if used:
            self.phase = "enemy_attack" if self.opponent.hp > 0 else "end_turn"
        else:
            self.phase = "selection"

    def _phase_use_ability(self, player, game):
        """Choose and use a class ability."""
        from core.abilities import player_abilities

        options = self.temporary_data.get("ability_options")
        if options is None:
            options = player_abilities(player)
            if not options:
                game.io.show_message("\nYou have no abilities to use.")
                self.phase = "selection"
                return

            self.temporary_data["ability_options"] = options
            game.io.show_message("\nWhich ability?")
            for index, ability in enumerate(options, 1):
                cost = ability.get("mana_cost", 0)
                game.io.show_message(
                    f"{index}. {ability['name']} ({cost} mana) - "
                    f"{ability.get('description', '')}"
                )
            game.io.show_message(f"{len(options) + 1}. Cancel")
            game.io.request_input("Choice: ")
            return

        selection = str(game.io.last_input or "").strip()
        self.temporary_data.pop("ability_options", None)
        if selection == str(len(options) + 1) or selection.casefold() in {"cancel", "back"}:
            self.phase = "selection"
            return

        chosen = None
        if selection.isdigit():
            index = int(selection) - 1
            if 0 <= index < len(options):
                chosen = options[index]["name"]
        else:
            chosen = self._parse_ability_command(player, selection)

        if not chosen:
            game.io.show_message("Invalid ability.")
            self.phase = "selection"
            return

        self._manage_ability(player, game, chosen)

    def _show_state_combat(self, player, game):
        """Show the current combat state"""
        game.io.show_message("\n" + "="*60)
        game.io.show_message(f"COMBAT: {player.name} vs {self.opponent.name}")
        game.io.show_message(f"Turn: {self.turn}")
        game.io.show_message(f"HP {player.name}: {player.hp}/{player.hp_max} | HP {self.opponent.name}: {self.opponent.hp}/{self.opponent.hp_max}")
        
        # Also show the player's current equipment
        weapon = player.weapon if isinstance(player.weapon, str) else (player.weapon.name if player.weapon else "None")
        armor = player.armor if isinstance(player.armor, str) else (player.armor.name if player.armor else "None")
        
        # Handle accessories
        accessories_names = []
        for acc in player.accessories:
            if isinstance(acc, str):
                accessories_names.append(acc)
            else:
                accessories_names.append(acc.name)
        accessories = ", ".join(accessories_names) if accessories_names else "None"
        
        # Show the player's equipment
        game.io.show_message(f"{player.name} - Weapon: {weapon} | Armor: {armor} | Accessories: {accessories}")
        game.io.show_message(f"{player.name} - Strength: {player.strength} | Defense: {player.defense}")
        
        # Show information about the enemy if available
        if hasattr(self.opponent, 'weapons') and self.opponent.weapons:
            game.io.show_message(f"{self.opponent.name} - Weapons: {', '.join(self.opponent.weapons)}")
        
        if hasattr(self.opponent, 'armor') and self.opponent.armor:
            game.io.show_message(f"{self.opponent.name} - Armor: {self.opponent.armor}")
            
        if hasattr(self.opponent, 'strength'):
            game.io.show_message(f"{self.opponent.name} - Strength: {self.opponent.strength}")
            
        if hasattr(self.opponent, 'description') and self.turn == 1:
            # Show the description only on the first turn
            game.io.show_message(f"\n{self.opponent.description}")
            
        game.io.show_message("="*60)
        
    def _check_end_combat(self, game):
        """Check whether the combat is over"""
        player = game.player
        
        if player.hp <= 0:
            game.io.show_message(f"\n{self.opponent.name} defeated you! You are gravely wounded...")
            player.hp = 1  # Instead of dying, the player stays at 1 HP
            if game.current_state():
                game.pop_state()
            return True
            
        if self.opponent.hp <= 0:
            game.io.show_message(f"\nYou defeated {self.opponent.name}!")
            self._remove_defeated_npc(game)

            # Handle the reward
            gained_gold = min(self.opponent.gold, 20)  # Max 20 coins
            self.opponent.gold -= gained_gold
            player.gold += gained_gold
            
            game.io.show_message(f"You gained {gained_gold} gold coins!")
            
            # Check whether there is an item to loot
            if hasattr(self.opponent, 'inventory') and self.opponent.inventory and len(self.opponent.inventory) > 0:
                item = self.opponent.inventory[0]  # Take the first item
                player.add_item(item)
                game.io.show_message(f"You obtained: {item.name}")
            
            # Gain experience - Fixed to use experience_value
            if hasattr(self.opponent, 'experience_value'):
                gained_exp = self.opponent.experience_value * (1 + getattr(self.opponent, 'level', 0))
            else:
                # Default value if the enemy does not have the experience_value attribute
                gained_exp = 25 * (1 + getattr(self.opponent, 'level', 0))
                
            if player.gain_experience(gained_exp, game):
                game.io.show_message(f"You gained {gained_exp} experience points and leveled up!")
            else:
                game.io.show_message(f"You gained {gained_exp} experience points!")
            
            if game.current_state():
                game.pop_state()
            return True
            
        return False

    def _check_initiative(self, player, game):
        """Lets a faster opponent act before the player's first choice."""
        if getattr(self, "_initiative_checked", False):
            return False
        self._initiative_checked = True

        player_initiative = int(getattr(player, "initiative", 0) or 0)
        opponent_initiative = int(getattr(self.opponent, "dexterity", 0) or 0)
        if opponent_initiative > player_initiative:
            game.io.show_message(f"\n{self.opponent.name} seizes the initiative!")
            self.phase = "enemy_attack"
            return True
        return False

    def apply_poison(self, damage, turns, game=None):
        """Applies (or refreshes) poison on the opponent."""
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}
        damage = int(damage)
        turns = int(turns)
        if damage <= 0 or turns <= 0:
            return

        poison = self.effects.get("poison")
        if isinstance(poison, dict):
            poison["damage"] = max(int(poison.get("damage", 0) or 0), damage)
            poison["turns"] = max(int(poison.get("turns", 0) or 0), turns)
        else:
            self.effects["poison"] = {"damage": damage, "turns": turns}

        if game:
            game.io.show_message(
                f"You poison {self.opponent.name}: {damage} damage for {turns} turns."
            )

    def _tick_poison(self, game):
        """Deals one round of poison damage and expires it when spent."""
        effects = getattr(self, "effects", None)
        if not isinstance(effects, dict):
            return
        poison = effects.get("poison")
        if not isinstance(poison, dict):
            return

        damage = int(poison.get("damage", 0) or 0)
        turns = int(poison.get("turns", 0) or 0)
        if damage <= 0 or turns <= 0:
            effects.pop("poison", None)
            return

        self.opponent.hp = max(0, self.opponent.hp - damage)
        game.io.show_message(f"Poison deals {damage} damage to {self.opponent.name}.")
        turns -= 1
        if turns <= 0:
            effects.pop("poison", None)
        else:
            poison["turns"] = turns

    def _tick_player_poison(self, player, game):
        """Deals one round of poison damage to the player."""
        conditions = getattr(player, "conditions", None)
        if not isinstance(conditions, dict):
            return
        poison = conditions.get("poison")
        if not isinstance(poison, dict):
            return

        damage = int(poison.get("damage", 0) or 0)
        turns = int(poison.get("turns", 0) or 0)
        if damage <= 0 or turns <= 0:
            conditions.pop("poison", None)
            return

        player.hp = max(0, player.hp - damage)
        game.io.show_message(f"Poison deals {damage} damage to you.")
        turns -= 1
        if turns <= 0:
            conditions.pop("poison", None)
        else:
            poison["turns"] = turns

    def _remove_defeated_npc(self, game):
        """Removes a defeated NPC from the map and from NPC menus."""
        npc = self.hostile_npc
        if npc is None:
            return

        game.map_manager.remove_npc(game.player.current_map, npc)

        name = str(getattr(npc, "name", "")).casefold()
        if not name:
            return

        for state in game.state_stack:
            if state is self:
                continue
            present = getattr(state, "present_npcs", None)
            if not isinstance(present, dict):
                continue
            for key, candidate in list(present.items()):
                candidate_name = str(getattr(candidate, "name", key)).casefold()
                if candidate is npc or candidate_name == name:
                    present.pop(key, None)

    def _manage_attack(self, player, game):
        """Handle the player's attack"""
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}

        # Use the player's effective strength, which includes weapon and accessory bonuses
        blessing = int(self.effects.pop("bless_attack", 0) or 0)
        damage = player.strength + blessing
        if blessing:
            game.io.show_message(f"Your blessing adds {blessing} damage.")

        # Calculate criticals and special bonuses using the dice instead of direct random
        critical = False
        if self.dice_d100.roll() <= 10:  # 10% chance of a critical hit
            damage *= 2
            critical = True
        
        # Apply the damage to the opponent
        self.opponent.wound(damage, game)
        
        # Attack message
        if hasattr(player, 'weapon') and player.weapon:
            weapon_name = player.weapon.name if hasattr(player.weapon, 'name') else str(player.weapon)
            if critical:
                game.io.show_message(f"\nCRITICAL HIT! You attack {self.opponent.name} with {weapon_name} and deal {damage} damage!")
            else:
                game.io.show_message(f"\nYou attack {self.opponent.name} with {weapon_name} and deal {damage} damage!")
        else:
            if critical:
                game.io.show_message(f"\nCRITICAL HIT! You attack {self.opponent.name} and deal {damage} damage!")
            else:
                game.io.show_message(f"\nYou attack {self.opponent.name} and deal {damage} damage!")
    
    def _attack_enemy(self, player, game):
        """Handle the opponent's attack."""
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}
        effects = self.effects

        if effects.pop("evade", False):
            game.io.show_message(f"\nYou evade {self.opponent.name}'s attack!")
            return

        # For NPCs we use their strength, otherwise we use the enemy's damage
        if self.hostile_npc:
            damage = max(1, self.hostile_npc.strength if hasattr(self.hostile_npc, 'strength') else 3)
        else:
            damage = self.enemy.strength if hasattr(self.enemy, 'strength') else self.enemy.damage

        # Attack description
        if hasattr(self.opponent, 'weapons') and self.opponent.weapons:
            import random
            weapon = random.choice(self.opponent.weapons)
            game.io.show_message(f"\n{self.opponent.name} attacks you with {weapon}!")
        else:
            game.io.show_message(f"\n{self.opponent.name} attacks you!")

        # Apply defense once here (take_damage() would subtract it again).
        effective_damage = max(1, int(damage) - int(player.defense))

        guard = int(effects.get("guard", 0) or 0)
        if guard and effective_damage > 0:
            absorbed = min(guard, effective_damage)
            effective_damage -= absorbed
            effects.pop("guard", None)
            game.io.show_message(f"Your guard absorbs {absorbed} damage.")

        bless = int(effects.get("bless_defense", 0) or 0)
        if bless and effective_damage > 0:
            absorbed = min(bless, effective_damage)
            effective_damage -= absorbed
            effects.pop("bless_defense", None)
            game.io.show_message(f"Your blessing wards off {absorbed} damage.")

        shield = int(effects.get("shield", 0) or 0)
        if shield and effective_damage > 0:
            absorbed = min(shield, effective_damage)
            effective_damage -= absorbed
            effects["shield"] = shield - absorbed
            if effects["shield"] <= 0:
                effects.pop("shield", None)
            game.io.show_message(f"Your shield absorbs {absorbed} damage.")

        if effective_damage > 0:
            player.hp = max(0, player.hp - effective_damage)
            game.io.show_message(f"You take {effective_damage} damage!")
        else:
            game.io.show_message("You take no damage.")

        attack_effect = getattr(self.opponent, "attack_effect", None)
        if (
            effective_damage > 0
            and isinstance(attack_effect, dict)
            and attack_effect.get("type") == "poison"
        ):
            poison_damage = int(attack_effect.get("damage", 0) or 0)
            poison_turns = int(attack_effect.get("turns", 0) or 0)
            if poison_damage > 0 and poison_turns > 0:
                conditions = getattr(player, "conditions", None)
                if not isinstance(conditions, dict):
                    conditions = {}
                    player.conditions = conditions
                poison = conditions.get("poison")
                if isinstance(poison, dict):
                    poison["damage"] = max(
                        int(poison.get("damage", 0) or 0), poison_damage
                    )
                    poison["turns"] = max(
                        int(poison.get("turns", 0) or 0), poison_turns
                    )
                else:
                    conditions["poison"] = {
                        "damage": poison_damage,
                        "turns": poison_turns,
                    }
                game.io.show_message(
                    f"You are poisoned! {poison_damage} damage for "
                    f"{poison_turns} turns."
                )
    
    def _apply_effect_item(self, player, item, game):
        """Apply the effect of an item"""
        if isinstance(item, str):
            # Handle old items (strings)
            if "Potion" in item:
                # Heal the player
                heal = 10
                player.hp = min(player.hp_max, player.hp + heal)
                game.io.show_message(f"\nYou use {item} and recover {heal} HP!")
                player.inventory.remove(item)
            elif "Poison" in item:
                # Poison the enemy
                damage = 5
                self.opponent.wound(damage, game)
                game.io.show_message(f"\nYou use {item} and deal {damage} damage to {self.opponent.name}!")
                player.inventory.remove(item)
            elif "Bomb" in item:
                # Heavily damage the enemy
                damage = 15
                self.opponent.wound(damage, game)
                game.io.show_message(f"\nYou use {item} and deal {damage} damage to {self.opponent.name}!")
                player.inventory.remove(item)
            else:
                game.io.show_message(f"\nYou do not know how to use {item} in combat!")
    
    def _attempt_escape(self, game, bonus=0):
        """Handle the escape attempt.

        Args:
            game: The game instance
            bonus (int): Modifier added to the d20 roll (e.g. from a smoke bomb)
        """
        # Roll a d20 with DC 10 to escape
        roll_result = self.dice_d20.roll() + bonus
        if roll_result >= 10:
            game.io.show_message(f"\nYou managed to escape! (Roll: {roll_result})")
            if game.current_state():
                game.pop_state()
        else:
            game.io.show_message(f"\nYou failed to escape! (Roll: {roll_result})")
            
    # Obsolete methods, kept for compatibility
    def _use_item(self, player, game):
        """Obsolete method kept for compatibility"""
        game.io.error_message("Obsolete method, use _phase_use_item instead")
        
    def _change_equipment(self, player, game):
        """Obsolete method kept for compatibility"""
        game.io.error_message("Obsolete method, use _phase_change_equipment instead")
        
    def _change_weapon(self, player, game):
        """Obsolete method kept for compatibility"""
        game.io.error_message("Obsolete method, use _phase_change_equipment instead")
        
    def _change_armor(self, player, game):
        """Obsolete method kept for compatibility"""
        game.io.error_message("Obsolete method, use _phase_change_equipment instead")
        
    def _change_accessory(self, player, game):
        """Obsolete method kept for compatibility"""
        game.io.error_message("Obsolete method, use _phase_change_equipment instead")
        
    @classmethod
    def from_dict(cls, data):
        """
        Create an instance of CombatState from a dictionary.
        
        Args:
            data (dict): Dictionary with the state data
            
        Returns:
            CombatState: New instance of CombatState
        """
        from entities.enemy import Enemy
        from entities.npc import NPC
        
        state = cls()
        
        # Restore the opponent
        if "opponent" in data and data["opponent"] is not None:
            if isinstance(data["opponent"], dict):
                # Determine whether the opponent is an enemy or an NPC
                if data["opponent"].get("type") == "NPC":
                    state.hostile_npc = NPC.from_dict(data["opponent"])
                    state.opponent = state.hostile_npc
                    state.enemy = None
                else:
                    state.enemy = Enemy.from_dict(data["opponent"])
                    state.opponent = state.enemy
                    state.hostile_npc = None
        
        # Restore the other attributes
        state.turn = data.get("turn", 1)
        state.phase = data.get("phase", "selection")
        state.temporary_data = data.get("temporary_data", {})
        state.effects = data.get("effects", {})
        state._initiative_checked = data.get("initiative_checked", True)

        return state
        
    def to_dict(self):
        """
        Convert the CombatState instance into a dictionary for saving.
        
        Returns:
            dict: Dictionary with the state data
        """
        data = {
            "turn": self.turn,
            "phase": self.phase,
            "temporary_data": self.temporary_data,
            "effects": dict(getattr(self, "effects", {}) or {}),
            "initiative_checked": bool(
                getattr(self, "_initiative_checked", False)
            ),
        }
        
        # Save the opponent
        if self.opponent is not None:
            if hasattr(self.opponent, 'to_dict'):
                opponent_dict = self.opponent.to_dict()
                # Add a type field to distinguish between NPC and Enemy
                if self.hostile_npc is not None:
                    opponent_dict["type"] = "NPC"
                data["opponent"] = opponent_dict
        
        return data
