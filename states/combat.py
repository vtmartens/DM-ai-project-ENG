from states.base_state import BaseState
from entities.enemy import Enemy
from entities.player import Player
from entities.npc import NPC
from util.dice import Dice

class CombatState(BaseState):
    def __init__(self, enemy=None, hostile_npc=None, enemies=None, allies=None):
        """
        Initialize the combat state.

        Args:
            enemy (Enemy, optional): A traditional enemy
            hostile_npc (NPC, optional): An NPC that has become hostile
            enemies (list, optional): Several hostile enemies
            allies (list, optional): Friendly combatants
        """
        if enemies is not None:
            self.enemies = list(enemies)
        elif enemy is not None:
            self.enemies = [enemy]
        elif hostile_npc is not None:
            self.enemies = [hostile_npc]
        else:
            self.enemies = []

        self._target_index = 0
        self.allies = list(allies or [])
        self.rewarded_enemies = set()
        self.enemy = self.enemies[0] if self.enemies else enemy
        self.hostile_npc = self.enemies[0] if self.enemies else hostile_npc
        self.turn = 1

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
        # Which enemy currently carries poison, if any
        self.poison_target_index = None
        # Damage the player has taken in this fight (for the "no damage" achievement)
        self.damage_taken = 0
        # Achievement bookkeeping, so a fight is only counted once
        self._quest_combat_recorded = False
        self._outcome_recorded = False

    def _alive_enemies(self):
        """Returns the enemies still standing."""
        return [
            enemy for enemy in self.enemies if getattr(enemy, "hp", 0) > 0
        ]

    @property
    def opponent(self):
        """The current target, falling back to the first living enemy."""
        alive = self._alive_enemies()
        if self.enemies and 0 <= self._target_index < len(self.enemies):
            target = self.enemies[self._target_index]
            if getattr(target, "hp", 0) > 0:
                return target
        if alive:
            return alive[0]
        return self.enemies[0] if self.enemies else None

    @opponent.setter
    def opponent(self, value):
        """Compatibility setter for single-opponent saves and callers."""
        self.enemies = [value] if value is not None else []
        self._target_index = 0
        self.enemy = value
        self.hostile_npc = value
        
    def run(self, game):
        player = game.player

        # A fight counts against "complete a quest without fighting" even if the
        # player flees, so record it once when combat actually starts.
        if not getattr(self, "_quest_combat_recorded", False):
            from core.quests import record_combat

            record_combat(player)
            self._quest_combat_recorded = True

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
        elif self.phase == "choose_target":
            self._phase_choose_target(player, game)

    def _parse_target_command(self, command):
        """Returns (target name, should_attack) for target/attack commands."""
        text = str(command or "").strip()
        lower = text.casefold()
        if lower.startswith("target "):
            return text[len("target ") :].strip(), False
        if lower.startswith("attack "):
            return text[len("attack ") :].strip(), True
        return None, False

    def select_target(self, name):
        """Selects a living enemy by name. Returns False if it is not found."""
        wanted = str(name or "").strip().casefold()
        if not wanted:
            return False
        for index, enemy in enumerate(self.enemies):
            if getattr(enemy, "hp", 0) <= 0:
                continue
            enemy_name = str(getattr(enemy, "name", "")).casefold()
            if (
                enemy_name == wanted
                or wanted in enemy_name
                or enemy_name in wanted
            ):
                self._target_index = index
                return True
        return False

    def _phase_choose_target(self, player, game):
        """Lets the player choose which living enemy to attack."""
        living = self._alive_enemies()
        if not living:
            self.phase = "selection"
            return

        options = self.temporary_data.get("target_options")
        if options is None:
            options = [self.enemies.index(enemy) for enemy in living]
            self.temporary_data["target_options"] = options
            game.io.show_message("\nChoose a target:")
            for number, enemy in enumerate(living, 1):
                game.io.show_message(
                    f"{number}. {enemy.name} "
                    f"({getattr(enemy, 'hp', 0)}/"
                    f"{getattr(enemy, 'hp_max', getattr(enemy, 'hp', 0))})"
                )
            game.io.show_message(f"{len(living) + 1}. Cancel")
            game.io.request_input("Choice: ")
            return

        selection = str(game.io.last_input or "").strip()
        self.temporary_data.pop("target_options", None)
        if selection == str(len(options) + 1) or selection.casefold() in {
            "cancel",
            "back",
        }:
            self.phase = "selection"
            return

        chosen_index = None
        if selection.isdigit():
            position = int(selection) - 1
            if 0 <= position < len(options):
                chosen_index = options[position]
        else:
            for index in options:
                enemy_name = str(getattr(self.enemies[index], "name", "")).casefold()
                if selection.casefold() in enemy_name:
                    chosen_index = index
                    break

        if chosen_index is None:
            game.io.show_message("Invalid target.")
            self.phase = "selection"
            return

        self._target_index = chosen_index
        game.io.show_message(f"Target: {self.opponent.name}.")
        self.phase = "selection"

    def _phase_selection(self, player, game):
        """Action selection phase"""
        # Ask the player for their action
        game.io.show_message("\nWhat do you want to do?")
        game.io.show_message("1. Attack")
        game.io.show_message("2. Use item")
        game.io.show_message("3. Change equipment")
        game.io.show_message("4. Flee")
        game.io.show_message("5. Use ability")
        if len(self._alive_enemies()) > 1:
            game.io.show_message("6. Choose target")
        
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
        
        target_name, attack_target = self._parse_target_command(selection_input)
        if target_name is not None:
            if self.select_target(target_name):
                game.io.show_message(f"Target: {self.opponent.name}.")
                if attack_target:
                    self._manage_attack(player, game)
                    self.phase = (
                        "enemy_attack" if self._alive_enemies() else "end_turn"
                    )
                else:
                    self.phase = "selection"
            else:
                game.io.show_message("Invalid target.")
                self.phase = "selection"
            return

        ability_name = self._parse_ability_command(player, selection_input)
        if ability_name:
            self._manage_ability(player, game, ability_name)
            return

        # Process the textual or numeric command
        if selection_input.isdigit() and selection_input in ["1", "2", "3", "4", "5", "6"]:
            selection = selection_input
        else:
            selection = process_command_combat(selection_input)

        if selection == "1":
            self._manage_attack(player, game)
            # Move to the enemy attack phase if the opponent is still alive
            if self._alive_enemies():
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
                if self._alive_enemies():
                    self.phase = "enemy_attack"
                else:
                    self.phase = "end_turn"
        elif selection == "5":
            self.phase = "use_ability"
            self.temporary_data.clear()
            return
        elif selection == "6":
            self.phase = "choose_target"
            self.temporary_data.clear()
            return
        else:
            game.io.show_message(f"Invalid action: '{selection_input}'!")
            self.phase = "selection"  # Return to the selection phase
    
    def _phase_attack_enemy(self, player, game):
        """Each living opponent attacks once."""
        for enemy in list(self.enemies):
            if getattr(enemy, "hp", 0) <= 0:
                continue
            self._attack_enemy(player, game, enemy)
            if player.hp <= 0:
                break
        if player.hp > 0:
            self._allies_attack(player, game)
        self.phase = "end_turn"

    def _allies_attack(self, player, game):
        """Each living ally strikes one living enemy."""
        for ally in self.allies:
            if getattr(ally, "hp", 0) <= 0:
                continue
            living = self._alive_enemies()
            if not living:
                break
            target = self.opponent if self.opponent in living else living[0]
            damage = max(1, int(getattr(ally, "strength", 1) or 1))
            target.hp = max(0, target.hp - damage)
            game.io.show_message(
                f"{getattr(ally, 'name', 'Your ally')} attacks {target.name} "
                f"for {damage} damage!"
            )
    
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
        if self._alive_enemies():
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
                    item.equip(player, game)
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
            if self._alive_enemies():
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
            self.phase = "enemy_attack" if self._alive_enemies() else "end_turn"
        else:
            self.phase = "selection"

    def _phase_use_ability(self, player, game):
        """Choose and use a class ability."""
        from core.abilities import player_abilities

        options = self.temporary_data.get("ability_options")
        if options is None:
            options = [
                ability
                for ability in player_abilities(player)
                if ability.get("usable_in_combat", True)
            ]
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
        """Show the current combat state."""
        living = self._alive_enemies()
        shown_enemies = living or self.enemies
        enemy_names = ", ".join(
            getattr(enemy, "name", "Unknown") for enemy in shown_enemies
        )
        game.io.show_message("\n" + "=" * 60)
        game.io.show_message(f"COMBAT: {player.name} vs {enemy_names or 'no enemies'}")
        game.io.show_message(f"Turn: {self.turn}")

        # Also show the player's current equipment
        weapon = (
            player.weapon
            if isinstance(player.weapon, str)
            else (player.weapon.name if player.weapon else "None")
        )
        armor = (
            player.armor
            if isinstance(player.armor, str)
            else (player.armor.name if player.armor else "None")
        )

        accessories_names = []
        for acc in player.accessories:
            accessories_names.append(acc if isinstance(acc, str) else acc.name)
        accessories = ", ".join(accessories_names) if accessories_names else "None"

        game.io.show_message(
            f"{player.name} - Weapon: {weapon} | Armor: {armor} | "
            f"Accessories: {accessories}"
        )
        game.io.show_message(
            f"{player.name} - Strength: {player.strength} | "
            f"Defense: {player.defense}"
        )

        for enemy in shown_enemies:
            target_label = (
                " (target)"
                if len(living) > 1 and enemy is self.opponent
                else ""
            )
            game.io.show_message(
                f"HP {getattr(enemy, 'name', 'Unknown')}: "
                f"{getattr(enemy, 'hp', 0)}/"
                f"{getattr(enemy, 'hp_max', getattr(enemy, 'hp', 0))}"
                f"{target_label}"
            )

        for ally in self.allies:
            if getattr(ally, "hp", 0) > 0:
                game.io.show_message(
                    f"Ally HP {getattr(ally, 'name', 'Unknown')}: "
                    f"{ally.hp}/{getattr(ally, 'hp_max', ally.hp)}"
                )

        for enemy in shown_enemies:
            if hasattr(enemy, "weapons") and enemy.weapons:
                game.io.show_message(
                    f"{enemy.name} - Weapons: {', '.join(enemy.weapons)}"
                )
            if hasattr(enemy, "armor") and enemy.armor:
                game.io.show_message(f"{enemy.name} - Armor: {enemy.armor}")
            if hasattr(enemy, "strength"):
                game.io.show_message(
                    f"{enemy.name} - Strength: {enemy.strength}"
                )

        if self.turn == 1:
            descriptions = [
                getattr(enemy, "description", "")
                for enemy in shown_enemies
                if getattr(enemy, "description", "")
            ]
            for description in descriptions:
                game.io.show_message(f"\n{description}")

        game.io.show_message("=" * 60)

    def _process_defeated_enemies(self, game):
        """Removes and rewards each enemy that has just fallen."""
        player = game.player
        for index, enemy in enumerate(self.enemies):
            if getattr(enemy, "hp", 0) > 0 or index in self.rewarded_enemies:
                continue
            self.rewarded_enemies.add(index)
            game.io.show_message(f"\nYou defeated {enemy.name}!")
            self._remove_defeated_npc(game, enemy)

            gained_gold = min(getattr(enemy, "gold", 0), 20)
            enemy.gold = getattr(enemy, "gold", 0) - gained_gold
            player.gold += gained_gold
            game.io.show_message(f"You gained {gained_gold} gold coins!")

            from core.achievements import record_event

            record_event(player, "gold_changed", game=game)

            if (
                hasattr(enemy, "inventory")
                and enemy.inventory
                and len(enemy.inventory) > 0
            ):
                item = enemy.inventory[0]
                player.add_item(item)
                game.io.show_message(f"You obtained: {item.name}")

            if hasattr(enemy, "experience_value"):
                gained_exp = enemy.experience_value * (
                    1 + getattr(enemy, "level", 0)
                )
            else:
                gained_exp = 25 * (1 + getattr(enemy, "level", 0))

            if player.gain_experience(gained_exp, game):
                game.io.show_message(
                    f"You gained {gained_exp} experience points and leveled up!"
                )
            else:
                game.io.show_message(
                    f"You gained {gained_exp} experience points!"
                )

            from core.quests import record_enemy_defeat

            record_enemy_defeat(player, getattr(enemy, "name", ""), game)

        alive = self._alive_enemies()
        if alive and (
            not (0 <= self._target_index < len(self.enemies))
            or getattr(self.enemies[self._target_index], "hp", 0) <= 0
        ):
            self._target_index = self.enemies.index(alive[0])

    def _check_end_combat(self, game):
        """Check whether the combat is over."""
        player = game.player

        if player.hp <= 0:
            last_enemy = self.opponent
            enemy_name = getattr(last_enemy, "name", "Your enemy")
            game.io.show_message(
                f"\n{enemy_name} defeated you! You are gravely wounded..."
            )
            player.hp = 1
            if not getattr(self, "_outcome_recorded", False):
                from core.achievements import record_event

                record_event(player, "combat_defeat", game=game)
                self._outcome_recorded = True
            if game.current_state():
                game.pop_state()
            return True

        self._process_defeated_enemies(game)

        if not self._alive_enemies():
            if len(self.enemies) > 1:
                game.io.show_message("\nYou have defeated all your enemies!")
            if not getattr(self, "_outcome_recorded", False):
                from core.achievements import record_event

                record_event(
                    player,
                    "combat_victory",
                    game=game,
                    clean=getattr(self, "damage_taken", 0) == 0,
                )
                self._outcome_recorded = True
            if game.current_state():
                game.pop_state()
            return True

        return False

    def _check_initiative(self, player, game):
        """Lets the fastest enemy act before the player's first choice."""
        if getattr(self, "_initiative_checked", False):
            return False
        self._initiative_checked = True

        living = self._alive_enemies()
        if not living:
            return False

        fastest = max(
            living,
            key=lambda enemy: int(getattr(enemy, "dexterity", 0) or 0),
        )
        player_initiative = int(getattr(player, "initiative", 0) or 0)
        if int(getattr(fastest, "dexterity", 0) or 0) > player_initiative:
            game.io.show_message(f"\n{fastest.name} seizes the initiative!")
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
        try:
            self.poison_target_index = self.enemies.index(self.opponent)
        except ValueError:
            self.poison_target_index = None

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
        index = getattr(self, "poison_target_index", None)
        if not isinstance(index, int) or not (0 <= index < len(self.enemies)):
            effects.pop("poison", None)
            self.poison_target_index = None
            return
        target = self.enemies[index]
        if damage <= 0 or turns <= 0 or getattr(target, "hp", 0) <= 0:
            effects.pop("poison", None)
            self.poison_target_index = None
            return

        target.hp = max(0, target.hp - damage)
        game.io.show_message(f"Poison deals {damage} damage to {target.name}.")
        turns -= 1
        if turns <= 0:
            effects.pop("poison", None)
            self.poison_target_index = None
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
        self.damage_taken = getattr(self, "damage_taken", 0) + damage
        game.io.show_message(f"Poison deals {damage} damage to you.")
        turns -= 1
        if turns <= 0:
            conditions.pop("poison", None)
        else:
            poison["turns"] = turns

    def _remove_defeated_npc(self, game, enemy=None):
        """Removes a defeated NPC from the map and from NPC menus."""
        npc = enemy or self.hostile_npc
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
    
    def _attack_enemy(self, player, game, enemy=None):
        """Handle one opponent's attack."""
        enemy = enemy or self.opponent
        if enemy is None:
            return
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}
        effects = self.effects

        if effects.pop("evade", False):
            game.io.show_message(f"\nYou evade {enemy.name}'s attack!")
            return

        strength = getattr(enemy, "strength", None)
        if strength is None:
            strength = getattr(enemy, "damage", 1)
        damage = max(1, int(strength))

        # Attack description
        if hasattr(enemy, 'weapons') and enemy.weapons:
            import random
            weapon = random.choice(enemy.weapons)
            game.io.show_message(f"\n{enemy.name} attacks you with {weapon}!")
        else:
            game.io.show_message(f"\n{enemy.name} attacks you!")

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
            self.damage_taken = getattr(self, "damage_taken", 0) + effective_damage
            game.io.show_message(f"You take {effective_damage} damage!")
        else:
            game.io.show_message("You take no damage.")

        attack_effect = getattr(enemy, "attack_effect", None)
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
        
    def __setstate__(self, state):
        """Restores older pickled combat states into the multi-enemy shape."""
        old_opponent = state.pop("opponent", None)
        self.__dict__.update(state)

        if not hasattr(self, "enemies"):
            if old_opponent is not None:
                self.enemies = [old_opponent]
            elif getattr(self, "enemy", None) is not None:
                self.enemies = [self.enemy]
            elif getattr(self, "hostile_npc", None) is not None:
                self.enemies = [self.hostile_npc]
            else:
                self.enemies = []
        if not hasattr(self, "_target_index"):
            self._target_index = 0
        if not hasattr(self, "allies"):
            self.allies = []
        if not hasattr(self, "rewarded_enemies"):
            self.rewarded_enemies = set()
        if not hasattr(self, "poison_target_index"):
            self.poison_target_index = None
        if not hasattr(self, "effects") or not isinstance(self.effects, dict):
            self.effects = {}
        if not hasattr(self, "_initiative_checked"):
            self._initiative_checked = True
        if not hasattr(self, "last_ability_used"):
            self.last_ability_used = None

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

        def restore_combatant(combatant_data):
            if not isinstance(combatant_data, dict):
                return None
            if combatant_data.get("type") == "NPC":
                return NPC.from_dict(combatant_data)
            return Enemy.from_dict(combatant_data)

        state = cls()
        state.enemies = []
        for enemy_data in data.get("enemies", []) or []:
            enemy = restore_combatant(enemy_data)
            if enemy is not None:
                state.enemies.append(enemy)

        # Compatibility with saves made before multi-enemy combat.
        if not state.enemies and isinstance(data.get("opponent"), dict):
            enemy = restore_combatant(data["opponent"])
            if enemy is not None:
                state.enemies = [enemy]

        state._target_index = int(data.get("target_index", 0) or 0)
        state.allies = [
            ally
            for ally in (
                restore_combatant(ally_data)
                for ally_data in data.get("allies", []) or []
            )
            if ally is not None
        ]
        state.rewarded_enemies = set(data.get("rewarded_enemies", []) or [])
        state.poison_target_index = data.get("poison_target_index")
        state.enemy = state.enemies[0] if state.enemies else None
        state.hostile_npc = (
            state.enemies[0]
            if state.enemies and isinstance(state.enemies[0], NPC)
            else None
        )

        # Restore the other attributes
        state.turn = data.get("turn", 1)
        state.phase = data.get("phase", "selection")
        state.temporary_data = data.get("temporary_data", {})
        state.effects = data.get("effects", {})
        state._initiative_checked = data.get("initiative_checked", True)
        state.damage_taken = int(data.get("damage_taken", 0) or 0)

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
            "damage_taken": int(getattr(self, "damage_taken", 0) or 0),
        }
        
        from entities.npc import NPC

        def serialize_combatant(combatant):
            if not hasattr(combatant, "to_dict"):
                return None
            combatant_data = combatant.to_dict()
            combatant_data["type"] = (
                "NPC" if isinstance(combatant, NPC) else "Enemy"
            )
            return combatant_data

        data["enemies"] = [
            combatant_data
            for combatant_data in (
                serialize_combatant(enemy) for enemy in self.enemies
            )
            if combatant_data is not None
        ]
        data["target_index"] = getattr(self, "_target_index", 0)
        data["allies"] = [
            combatant_data
            for combatant_data in (
                serialize_combatant(ally) for ally in self.allies
            )
            if combatant_data is not None
        ]
        data["rewarded_enemies"] = sorted(
            getattr(self, "rewarded_enemies", set())
        )
        data["poison_target_index"] = getattr(
            self, "poison_target_index", None
        )

        return data
