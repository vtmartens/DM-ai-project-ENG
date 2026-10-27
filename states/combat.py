from states.base_state import BaseState
from core.checks import contested_check, contested_skill_check
from core.conditions import (
    apply_condition,
    condition_blocks_abilities,
    condition_incoming_roll_flags,
    condition_stand_up,
    remove_condition,
    tick_conditions,
)
from core.enemy_abilities import choose_ability, load_abilities
from core.maneuvers import get_maneuver, maneuver_definitions
from entities.enemy import Enemy
from entities.player import Player
from entities.npc import NPC
from util.dice import Dice

class CombatState(BaseState):
    DEFEAT_GOLD_LOSS = 20
    ENEMY_MANEUVER_COOLDOWN = 2
    DEFAULT_MANEUVER_CHANCE = 35

    def __init__(
        self,
        enemy=None,
        hostile_npc=None,
        enemies=None,
        allies=None,
        encounter=None,
        surprised=False,
    ):
        """
        Initialize the combat state.

        Args:
            enemy (Enemy, optional): A traditional enemy
            hostile_npc (NPC, optional): An NPC that has become hostile
            enemies (list, optional): Several hostile enemies
            allies (list, optional): Friendly combatants
            encounter (dict, optional): Curated encounter metadata and reward
            surprised (bool): Enemies lose their first turn and the opening
                weapon attack has advantage
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
        # Set when combat ends, so enclosing states can distinguish victory,
        # defeat and a successful escape.
        self.outcome = None
        # New Cycle scaling is applied once when combat first runs.
        self.cycle_scaled = False
        # A stealth opening skips the enemies' first turn; the opening weapon
        # attack also has advantage.
        self.surprised = bool(surprised)
        if self.surprised:
            self.effects["surprise_attack"] = True
        # Result of the most recent ability attempt (used by POST /use_ability)
        self.last_ability_used = None
        # Whether initiative has already decided who acts first
        self._initiative_checked = False
        # Which enemy currently carries poison, if any
        self.poison_target_index = None
        # Enemy ability state, keyed by the enemy's index in self.enemies
        self.ability_cooldowns = {}
        self.enemy_guard = {}
        # Curated encounter metadata (never includes the enemy objects themselves)
        metadata = dict(encounter) if isinstance(encounter, dict) else None
        if metadata is not None:
            metadata.pop("enemies", None)
        self.encounter = metadata or None
        self.encounter_rewarded = False
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

    def _flanking_bonus(self):
        """A living ally gives the player +2 to weapon attacks."""
        return (
            2
            if any(
                getattr(ally, "hp", 0) > 0
                for ally in getattr(self, "allies", [])
            )
            else 0
        )

    def _apply_cycle_scaling(self, player):
        """Scales enemies once for the current New Cycle."""
        if getattr(self, "cycle_scaled", False):
            return
        self.cycle_scaled = True

        from core.cycles import cycle_number, enemy_scaling

        scaling = enemy_scaling(cycle_number(player))
        hp_percent = int(scaling.get("hp_percent", 0) or 0)
        damage_bonus = int(scaling.get("damage_bonus", 0) or 0)
        ac_bonus = int(scaling.get("ac_bonus", 0) or 0)
        if not (hp_percent or damage_bonus or ac_bonus):
            return

        for enemy in self.enemies:
            if hp_percent:
                bonus = max(
                    1, int(round(enemy.hp_max * hp_percent / 100))
                )
                enemy.hp_max += bonus
                enemy.hp = min(enemy.hp_max, enemy.hp + bonus)
            if damage_bonus:
                enemy.damage_bonus = int(
                    getattr(enemy, "damage_bonus", 0) or 0
                ) + damage_bonus
            if ac_bonus:
                enemy.armor_class_value = (
                    int(self._armor_class_for(enemy)) + ac_bonus
                )

    def cover_available(self, game=None):
        """Whether the player has a nearby wall or cover object."""
        game = game or getattr(self, "game", None)
        player = getattr(game, "player", None) if game else None
        if player is None or not getattr(player, "current_map", None):
            return False
        map_manager = getattr(game, "map_manager", None)
        current_map = (
            map_manager.get_map(player.current_map)
            if map_manager is not None
            else None
        )
        if current_map is None:
            return False
        return current_map.has_cover_near(player.x, player.y)

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

        self._apply_cycle_scaling(player)

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

    def _maneuvers(self):
        return maneuver_definitions()

    def _parse_cover_command(self, command):
        """Matches the Take Cover combat action."""
        text = str(command or "").strip().casefold()
        return text in {"9", "cover", "take cover", "take_cover"}

    def _parse_stand_command(self, command):
        """Matches the dynamic Stand Up menu option or its text aliases."""
        text = str(command or "").strip().casefold()
        if not text:
            return False
        stand_number = str(10 + len(self._maneuvers()))
        return text in {stand_number, "stand", "stand up", "rise"}

    def _parse_maneuver_command(self, command):
        """Matches a maneuver id/name or its menu number (10 onward)."""
        text = str(command or "").strip().casefold()
        if not text:
            return None

        maneuvers = self._maneuvers()
        if text.isdigit():
            index = int(text) - 10
            if 0 <= index < len(maneuvers):
                return maneuvers[index]
            return None

        for maneuver in maneuvers:
            names = {
                str(maneuver.get("id", "")).casefold(),
                str(maneuver.get("name", "")).casefold(),
            }
            for name in names:
                if name and (text == name or text.startswith(f"{name} ")):
                    return maneuver
        return None

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
        game.io.show_message("7. Defend")
        game.io.show_message("8. Aim")
        if self.cover_available(game):
            game.io.show_message("9. Take cover")
        for offset, maneuver in enumerate(maneuver_definitions(), start=10):
            game.io.show_message(
                f"{offset}. {maneuver.get('name', 'Maneuver')} — "
                f"{maneuver.get('description', '')}"
            )
        if condition_stand_up(player):
            stand_number = 10 + len(maneuver_definitions())
            game.io.show_message(f"{stand_number}. Stand up")

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
            if cmd.isdigit():
                return cmd

            # Mapping of text commands to actions
            if any(x in cmd for x in ["attack", "hit", "1"]):
                return "1"
            elif any(x in cmd for x in ["ability", "spell", "cast", "5"]):
                return "5"
            elif any(x in cmd for x in ["use", "item", "potion", "2"]):
                return "2"
            elif any(x in cmd for x in ["change", "equipment", "weapon", "3"]):
                return "3"
            elif any(x in cmd for x in ["flee", "escape", "run", "4"]):
                return "4"
            elif any(x in cmd for x in ["defend", "dodge", "block", "7"]):
                return "7"
            elif any(x in cmd for x in ["aim", "focus", "8"]):
                return "8"
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

        if self._parse_cover_command(selection_input):
            self._manage_cover(player, game)
            return

        if condition_stand_up(player) and self._parse_stand_command(
            selection_input
        ):
            self._manage_stand(player, game)
            return

        maneuver = self._parse_maneuver_command(selection_input)
        if maneuver is not None:
            self._manage_maneuver(player, game, maneuver)
            return

        # Process the textual or numeric command
        if selection_input.isdigit() and selection_input in [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
        ]:
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
        elif selection == "7":
            self._manage_defend(player, game)
        elif selection == "8":
            self._manage_aim(player, game)
        else:
            game.io.show_message(f"Invalid action: '{selection_input}'!")
            self.phase = "selection"  # Return to the selection phase
    
    def _phase_attack_enemy(self, player, game):
        """Each living opponent attacks once."""
        if getattr(self, "surprised", False):
            self.surprised = False
            game.io.show_message(
                "\nThe enemies are caught off guard and lose their first turn."
            )
            if player.hp > 0:
                self._allies_attack(player, game)
            self.phase = "end_turn"
            return

        self._tick_enemy_ability_cooldowns()
        for index, enemy in enumerate(list(self.enemies)):
            if getattr(enemy, "hp", 0) <= 0:
                continue
            self._attack_enemy(player, game, enemy, index=index)
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
            ally_name = getattr(ally, "name", "Your ally")
            hit, critical = self._roll_attack(ally, target, game)
            if not hit:
                game.io.show_message(f"{ally_name} misses {target.name}.")
                continue
            damage = max(1, int(getattr(ally, "strength", 1) or 1))
            if critical:
                damage *= 2
            target.hp = max(0, target.hp - damage)
            game.io.show_message(
                f"{ally_name} attacks {target.name} for {damage} damage!"
            )
    
    def _phase_end_turn(self, player, game):
        """End turn phase"""
        self._tick_poison(game)
        self._tick_player_poison(player, game)

        tick_conditions(player, game)
        for enemy in self._alive_enemies():
            tick_conditions(enemy, game)

        # Defending lasts through the enemy phase of this round. Aim persists
        # until the next weapon attack consumes it.
        if isinstance(getattr(self, "effects", None), dict):
            self.effects.pop("defend", None)
            self.effects.pop("cover", None)

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

        if condition_blocks_abilities(player):
            game.io.show_message(
                "\nYou are staggered and cannot use special abilities."
            )
            self.last_ability_used = False
            self.phase = "selection"
            return

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
            f"Armor Class: {player.armor_class} | "
            f"Attack: {player.attack_bonus:+d}"
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
                f"{getattr(enemy, 'hp_max', getattr(enemy, 'hp', 0))} | "
                f"AC {getattr(enemy, 'armor_class', 10)}"
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
            self.ability_cooldowns.pop(str(index), None)
            self.enemy_guard.pop(str(index), None)
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

            if isinstance(self.encounter, dict) and self.encounter.get("loot"):
                from core.loot import roll_loot

                for loot_item in roll_loot(enemy, self.dice_d100):
                    player.add_item(loot_item)
                    game.io.show_message(f"You loot {loot_item.name}.")

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

            record_enemy_defeat(
                player,
                getattr(enemy, "name", ""),
                game,
                monster_type=getattr(enemy, "monster_type", None),
            )

        alive = self._alive_enemies()
        if alive and (
            not (0 <= self._target_index < len(self.enemies))
            or getattr(self.enemies[self._target_index], "hp", 0) <= 0
        ):
            self._target_index = self.enemies.index(alive[0])

    def _grant_encounter_reward(self, game):
        """Grants a curated encounter's completion bonus once."""
        if self.encounter_rewarded or not isinstance(self.encounter, dict):
            return False
        if game is None or getattr(game, "player", None) is None:
            return False

        self.encounter_rewarded = True
        reward = self.encounter.get("reward", {})
        if not isinstance(reward, dict):
            reward = {}
        gold = int(reward.get("gold", 0) or 0)
        experience = int(reward.get("experience", 0) or 0)
        from core.cycles import reward_multiplier

        multiplier = reward_multiplier(
            getattr(game.player, "cycle", 1)
        )
        gold = int(gold * multiplier)
        experience = int(experience * multiplier)

        if gold:
            game.player.add_gold(gold, game)
        if experience:
            game.player.gain_experience(experience, game)

        title = self.encounter.get("title", "Encounter")
        game.io.show_message(f"\nEncounter complete: {title}")
        bonus = []
        if gold:
            bonus.append(f"{gold} gold")
        if experience:
            bonus.append(f"{experience} XP")
        if bonus:
            game.io.show_message(f"Encounter bonus: {', '.join(bonus)}.")

        from core.achievements import record_event

        if self.encounter.get("source") == "road":
            record_event(game.player, "road_victory", game=game)

        area = self.encounter.get("clears_area")
        if isinstance(area, str) and area:
            cleared = getattr(game.player, "cleared_areas", None)
            if not isinstance(cleared, list):
                cleared = []
                game.player.cleared_areas = cleared
            if area not in cleared:
                cleared.append(area)
                label = area.replace("_", " ").title()
                game.io.show_message(f"The {label} is clear.")
                record_event(
                    game.player,
                    "area_cleared",
                    game=game,
                    area=area,
                )
        return True

    def _handle_defeat(self, game, enemy_name):
        """Moves a defeated player back to the tavern with a recovery cost."""
        player = game.player
        game.io.show_message(
            f"\n{enemy_name} strikes you down. The world goes dark..."
        )

        lost = min(
            int(getattr(player, "gold", 0) or 0), self.DEFEAT_GOLD_LOSS
        )
        if lost:
            player.gold -= lost

        player.defeats = int(getattr(player, "defeats", 0) or 0) + 1

        hp_max = int(getattr(player, "hp_max", 1) or 1)
        mana_max = int(getattr(player, "mana_max", 0) or 0)
        player.hp = max(1, hp_max // 2)
        player.mana = max(0, mana_max // 2)

        conditions = getattr(player, "conditions", None)
        if isinstance(conditions, dict):
            conditions.clear()

        tavern_map = game.map_manager.get_map("tavern")
        if tavern_map:
            game.map_manager.set_current_map("tavern")
            x, y = tavern_map.player_start_position
            player.set_position("tavern", x, y)

        game.io.show_message(
            "You wake in a bed at the Yawning Portal, battered but alive."
        )
        if lost:
            game.io.show_message(
                "The healers' bill and the room cost you "
                f"{lost} gold."
            )
        else:
            game.io.show_message("The innkeeper waves off the cost of the room.")
        game.io.show_message("You have recovered half your health and mana.")

        if not getattr(self, "_outcome_recorded", False):
            from core.achievements import record_event

            record_event(player, "combat_defeat", game=game)
            self._outcome_recorded = True

        from states.tavern import TavernState

        tavern = TavernState(game)
        tavern.first_visit = False
        game.reset_to_state(tavern)

    def _check_end_combat(self, game):
        """Check whether the combat is over."""
        player = game.player

        if player.hp <= 0:
            self.outcome = "defeat"
            last_enemy = self.opponent
            enemy_name = getattr(last_enemy, "name", "Your enemy")
            self._handle_defeat(game, enemy_name)
            return True

        self._process_defeated_enemies(game)

        if not self._alive_enemies():
            self.outcome = "victory"
            if len(self.enemies) > 1:
                game.io.show_message("\nYou have defeated all your enemies!")
            self._grant_encounter_reward(game)
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

        if getattr(self, "surprised", False):
            return False

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

    def _attack_bonus_for(self, attacker):
        """Returns the attacker's d20 bonus, including SimpleNamespace allies."""
        bonus = getattr(attacker, "attack_bonus", None)
        if bonus is not None:
            return int(bonus)
        strength = int(getattr(attacker, "strength", 0) or 0)
        proficiency = int(getattr(attacker, "proficiency_bonus", 2) or 2)
        return strength + proficiency

    @staticmethod
    def _attack_ability_for(attacker):
        ability = getattr(attacker, "attack_ability", None)
        if callable(ability):
            try:
                return str(ability())
            except Exception:
                pass
        return "strength"

    @staticmethod
    def _armor_class_for(target):
        """Returns the target's AC, with a fallback for simple combatants."""
        armor_class = getattr(target, "armor_class", None)
        if armor_class is not None:
            return int(armor_class)
        dexterity = int(getattr(target, "dexterity", 0) or 0)
        defense = int(getattr(target, "defense", 0) or 0)
        return 10 + dexterity + defense

    def _roll_attack(
        self,
        attacker,
        target,
        game,
        *,
        player_attacker=False,
        target_is_player=False,
        critical_allowed=True,
        advantage=False,
        disadvantage=False,
        bonus_modifier=0,
    ):
        """Rolls d20 + attack bonus against AC and logs the result."""
        advantage_flag = bool(advantage)
        disadvantage_flag = bool(disadvantage)
        roll_flags = getattr(attacker, "roll_flags", None)
        if callable(roll_flags):
            condition_advantage, condition_disadvantage = roll_flags("attack")
            advantage_flag = advantage_flag or condition_advantage
            disadvantage_flag = disadvantage_flag or condition_disadvantage
        incoming_advantage, incoming_disadvantage = (
            condition_incoming_roll_flags(target, "attack")
        )
        advantage_flag = advantage_flag or incoming_advantage
        disadvantage_flag = disadvantage_flag or incoming_disadvantage
        if advantage_flag and disadvantage_flag:
            advantage_flag = disadvantage_flag = False

        if advantage_flag:
            first = self.dice_d20.roll()
            second = self.dice_d20.roll()
            roll = max(first, second)
            roll_text = f"{first} / {second} (advantage)"
        elif disadvantage_flag:
            first = self.dice_d20.roll()
            second = self.dice_d20.roll()
            roll = min(first, second)
            roll_text = f"{first} / {second} (disadvantage)"
        else:
            roll = self.dice_d20.roll()
            roll_text = str(roll)

        bonus = self._attack_bonus_for(attacker) + int(
            bonus_modifier or 0
        )
        ability = self._attack_ability_for(attacker)
        ability_label = ability[:3].upper()
        total = roll + bonus
        target_ac = self._armor_class_for(target)
        defense_notes = []
        effects = getattr(self, "effects", {}) or {}
        if target_is_player and effects.get("defend"):
            target_ac += 4
            defense_notes.append("defending")
        if target_is_player and effects.get("cover"):
            target_ac += 2
            defense_notes.append("in cover")
        defense_note = (
            f" ({', '.join(defense_notes)})" if defense_notes else ""
        )
        critical = critical_allowed and roll == 20
        hit = roll == 20 or (roll != 1 and total >= target_ac)

        subject = (
            "You" if player_attacker else getattr(attacker, "name", "Attacker")
        )
        verb = "roll" if player_attacker else "rolls"
        target_label = (
            "your AC"
            if target_is_player
            else f"{getattr(target, 'name', 'the target')}'s AC"
        )
        if critical:
            result = "critical hit (natural 20)"
        elif roll == 1:
            result = "miss (natural 1)"
        else:
            result = "hit" if hit else "miss"
        game.io.show_message(
            f"{subject} {verb} {roll_text} + {bonus} ({ability_label}) = "
            f"{total} vs {target_label} {target_ac}{defense_note}: {result}."
        )
        return hit, critical

    def _manage_attack(self, player, game):
        """Handle the player's attack."""
        if self.opponent is None:
            return
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}

        aiming = bool(
            self.effects.pop("aim", False)
            or self.effects.pop("surprise_attack", False)
        )
        hit, critical = self._roll_attack(
            player,
            self.opponent,
            game,
            player_attacker=True,
            advantage=aiming,
            bonus_modifier=self._flanking_bonus(),
        )
        if not hit:
            game.io.show_message("Your attack misses.")
            return

        # Use the player's effective strength, which includes weapon and accessory bonuses
        blessing = int(self.effects.pop("bless_attack", 0) or 0)
        damage = player.attack_damage_modifier + blessing
        if blessing:
            game.io.show_message(f"Your blessing adds {blessing} damage.")

        if critical:
            damage *= 2

        from core.conditions import condition_damage_modifier

        modifier = condition_damage_modifier(player)
        if modifier:
            damage = max(1, damage + modifier)
            game.io.show_message(
                f"Your weakened state reduces the damage by {abs(modifier)}."
            )

        # An enemy ability can raise a guard that absorbs the next hit.
        if not isinstance(getattr(self, "enemy_guard", None), dict):
            self.enemy_guard = {}
        index = self._enemy_index(self.opponent)
        guard = int(self.enemy_guard.pop(str(index), 0) or 0)
        if guard:
            absorbed = min(guard, damage)
            damage = max(1, damage - absorbed)
            game.io.show_message(
                f"{self.opponent.name}'s guard absorbs {absorbed} damage."
            )

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

    def _manage_defend(self, player, game):
        """Spends the turn defending: +4 AC until the end of the round."""
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}
        self.effects["defend"] = True
        game.io.show_message(
            "\nYou raise your guard. Your AC increases by 4 until your next turn."
        )
        self.phase = "enemy_attack" if self._alive_enemies() else "end_turn"

    def _manage_aim(self, player, game):
        """Spends the turn aiming: the next weapon attack has advantage."""
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}
        self.effects["aim"] = True
        game.io.show_message(
            "\nYou steady your aim. Your next attack has advantage."
        )
        self.phase = "enemy_attack" if self._alive_enemies() else "end_turn"

    def _manage_cover(self, player, game):
        """Spends the turn taking cover until the next round."""
        if not self.cover_available(game):
            game.io.show_message(
                "\nThere is no wall or sturdy object nearby to take cover behind."
            )
            self.phase = "selection"
            return
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}
        self.effects["cover"] = True
        game.io.show_message(
            "\nYou take cover. You gain +2 AC and advantage on Dexterity "
            "saves until your next turn."
        )
        self.phase = "enemy_attack" if self._alive_enemies() else "end_turn"

    def _manage_stand(self, player, game):
        """Spends the turn standing up from a prone condition."""
        condition_id = condition_stand_up(player)
        if not condition_id:
            game.io.show_message("\nYou are already on your feet.")
            self.phase = "selection"
            return
        remove_condition(player, condition_id)
        game.io.show_message("\nYou climb back to your feet.")
        self.phase = "enemy_attack" if self._alive_enemies() else "end_turn"

    def _manage_maneuver(self, player, game, maneuver):
        """Resolves a contested maneuver and applies its condition."""
        target = self.opponent
        if target is None:
            self.phase = "selection"
            return

        name = str(maneuver.get("name", "maneuver"))
        player_skill = str(maneuver.get("skill", "athletics"))
        target_skill = str(maneuver.get("defense_skill", "acrobatics"))
        result = contested_skill_check(
            player, player_skill, target, target_skill, game
        )

        if result["success"]:
            condition_id = str(maneuver.get("condition", "") or "")
            condition_name = condition_id.replace("_", " ").title()
            message = str(
                maneuver.get(
                    "message",
                    f"{target.name} is {condition_name.lower()}.",
                )
            ).format(target=target.name)
            if condition_id and apply_condition(
                target,
                condition_id,
                turns=maneuver.get("turns"),
                game=game,
                message=message,
            ):
                game.io.show_message(
                    f"\n{name} succeeds "
                    f"({result['player_total']} vs {result['target_total']})."
                )
            else:
                game.io.show_message(
                    f"\n{name} succeeds, but {target.name} is unaffected."
                )
        else:
            game.io.show_message(
                f"\n{name} fails "
                f"({result['player_total']} vs {result['target_total']})."
            )

        self.phase = "enemy_attack" if self._alive_enemies() else "end_turn"

    def _enemy_index(self, enemy):
        try:
            return self.enemies.index(enemy)
        except ValueError:
            return 0

    def _tick_enemy_ability_cooldowns(self):
        """Reduces every active enemy ability cooldown by one round."""
        for cooldowns in self.ability_cooldowns.values():
            for ability_id, remaining in list(cooldowns.items()):
                if remaining > 0:
                    cooldowns[ability_id] = remaining - 1

    def _poison_player(self, player, game, poison):
        """Applies or refreshes poison on the player."""
        if not isinstance(poison, dict):
            return
        poison_damage = int(poison.get("damage", 0) or 0)
        poison_turns = int(
            poison.get("turns", poison.get("duration", 0)) or 0
        )
        if poison_damage <= 0 or poison_turns <= 0:
            return

        conditions = getattr(player, "conditions", None)
        if not isinstance(conditions, dict):
            conditions = {}
            player.conditions = conditions
        current = conditions.get("poison")
        if isinstance(current, dict):
            current["damage"] = max(
                int(current.get("damage", 0) or 0), poison_damage
            )
            current["turns"] = max(
                int(current.get("turns", 0) or 0), poison_turns
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

    def _apply_incoming_damage(self, player, game, damage):
        """Applies damage after the attack has hit and guard effects resolve."""
        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}
        effects = self.effects

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
        return effective_damage

    def _choose_enemy_maneuver(self, enemy, player, index):
        """Returns a useful off-cooldown maneuver after the chance roll."""
        cooldowns = self.ability_cooldowns.setdefault(str(index), {})
        conditions = getattr(player, "conditions", None)
        conditions = conditions if isinstance(conditions, dict) else {}

        options = []
        for maneuver_id in getattr(enemy, "maneuvers", []) or []:
            if int(
                cooldowns.get(f"maneuver:{maneuver_id}", 0) or 0
            ) > 0:
                continue
            maneuver = get_maneuver(maneuver_id)
            if maneuver is None:
                continue
            condition_id = maneuver.get("condition")
            if condition_id and condition_id in conditions:
                continue
            options.append(maneuver)

        if not options:
            return None

        chance = int(
            getattr(enemy, "maneuver_chance", self.DEFAULT_MANEUVER_CHANCE)
            or 0
        )
        if chance <= 0 or self.dice_d100.roll() > chance:
            return None
        return options[0]

    def _use_enemy_maneuver(self, player, game, enemy, maneuver, index):
        """Resolves an enemy Trip/Shove against the player."""
        name = str(maneuver.get("name", "maneuver"))
        telegraph = maneuver.get("telegraph")
        if telegraph:
            game.io.show_message(f"\n{telegraph}")
        game.io.show_message(
            f"\n{enemy.name} tries to {name.lower()} you!"
        )

        result = contested_check(
            enemy,
            str(maneuver.get("skill", "athletics")),
            player,
            str(maneuver.get("defense_skill", "acrobatics")),
            game,
        )
        cooldowns = self.ability_cooldowns.setdefault(str(index), {})
        cooldowns[f"maneuver:{maneuver.get('id', name)}"] = (
            self.ENEMY_MANEUVER_COOLDOWN
        )

        if result["success"]:
            condition_id = str(maneuver.get("condition", "") or "")
            apply_condition(
                player,
                condition_id,
                turns=maneuver.get("turns"),
                game=game,
            )
            game.io.show_message(
                f"{name} succeeds "
                f"({result['attacker_total']} vs {result['defender_total']})."
            )
        else:
            game.io.show_message(
                f"{name} fails "
                f"({result['attacker_total']} vs {result['defender_total']})."
            )

    def _enemy_stands_up(self, enemy, game):
        """Spends a prone enemy's action standing up; returns True if it did."""
        condition_id = condition_stand_up(enemy)
        if not condition_id:
            return False
        remove_condition(enemy, condition_id)
        game.io.show_message(
            f"\n{enemy.name} spends its turn standing up."
        )
        return True

    def _attack_enemy(self, player, game, enemy=None, index=None):
        """Handle one opponent's action: ability when ready, else basic attack."""
        enemy = enemy or self.opponent
        if enemy is None:
            return
        if index is None:
            index = self._enemy_index(enemy)

        if not isinstance(getattr(self, "effects", None), dict):
            self.effects = {}

        if self._enemy_stands_up(enemy, game):
            return

        maneuver = self._choose_enemy_maneuver(enemy, player, index)
        if maneuver is not None:
            self._use_enemy_maneuver(
                player, game, enemy, maneuver, index
            )
            return

        if self.effects.pop("evade", False):
            game.io.show_message(f"\nYou evade {enemy.name}'s attack!")
            return

        abilities = getattr(enemy, "abilities", None)
        if abilities is None:
            abilities = load_abilities(getattr(enemy, "ability_ids", []))
        cooldowns = self.ability_cooldowns.setdefault(str(index), {})
        if condition_blocks_abilities(enemy):
            ability = None
            if abilities:
                game.io.show_message(
                    f"\n{enemy.name} is staggered and cannot use "
                    "special abilities."
                )
        else:
            ability = choose_ability(abilities, cooldowns, enemy)
        if ability is not None:
            self._use_enemy_ability(player, game, enemy, ability, index)
            return

        damage = max(1, int(enemy.attack_damage_modifier))

        # Attack description
        if hasattr(enemy, 'weapons') and enemy.weapons:
            import random
            weapon = random.choice(enemy.weapons)
            game.io.show_message(f"\n{enemy.name} attacks you with {weapon}!")
        else:
            game.io.show_message(f"\n{enemy.name} attacks you!")

        hit, critical = self._roll_attack(
            enemy, player, game, target_is_player=True
        )
        if not hit:
            return
        if critical:
            damage *= 2

        effective_damage = self._apply_incoming_damage(player, game, damage)

        attack_effect = getattr(enemy, "attack_effect", None)
        if (
            effective_damage > 0
            and isinstance(attack_effect, dict)
            and attack_effect.get("type") == "poison"
        ):
            self._poison_player(player, game, attack_effect)

    def _use_enemy_ability(self, player, game, enemy, ability, index):
        """Applies one enemy ability and starts its cooldown."""
        name = ability.get("name", "an ability")
        telegraph = ability.get("telegraph")
        if telegraph:
            game.io.show_message(f"\n{telegraph}")
        game.io.show_message(f"\n{enemy.name} uses {name}!")

        effect = ability.get("effect", {}) or {}
        kind = effect.get("type", "attack")

        if kind == "heal":
            amount = int(effect.get("amount", 0) or 0)
            before = getattr(enemy, "hp", 0)
            enemy.hp = min(getattr(enemy, "hp_max", before), before + amount)
            game.io.show_message(f"{enemy.name} recovers {enemy.hp - before} HP.")
        else:
            save_data = ability.get("save")
            saved = False
            save_success = "half"
            if isinstance(save_data, dict):
                save_success = str(
                    save_data.get("success", "half")
                ).casefold()
                save_ability = str(
                    save_data.get("ability", "dexterity")
                ).casefold()
                cover_advantage = (
                    bool(self.effects.get("cover"))
                    and save_ability == "dexterity"
                )
                saved = player.saving_throw(
                    save_ability,
                    int(save_data.get("dc", 10) or 10),
                    game,
                    advantage=True if cover_advantage else None,
                )
                if saved:
                    game.io.show_message(
                        "You avoid the effect entirely."
                        if save_success == "negate"
                        else "You shrug off the worst of it."
                    )

            attack_hit = True
            attack_critical = False
            if kind == "attack" and not isinstance(save_data, dict):
                attack_hit, attack_critical = self._roll_attack(
                    enemy,
                    player,
                    game,
                    target_is_player=True,
                    critical_allowed=False,
                )

            damage = effect.get("damage")
            if "multiplier" in effect:
                damage = max(
                    1,
                    int(getattr(enemy, "attack_damage_modifier", 1))
                    * int(effect.get("multiplier", 1) or 1),
                )
            elif damage is None:
                damage = getattr(enemy, "attack_damage_modifier", 1)
            damage = max(1, int(damage)) + int(effect.get("bonus", 0) or 0)

            if attack_critical:
                damage *= 2
            if not attack_hit:
                damage = 0
            elif saved and save_success == "negate":
                damage = 0
            elif saved:
                damage = max(1, damage // 2)

            effective_damage = 0
            if damage > 0:
                effective_damage = self._apply_incoming_damage(
                    player, game, damage
                )

            poison = effect.get("poison")
            if (
                not saved
                and effective_damage > 0
                and isinstance(poison, dict)
            ):
                self._poison_player(player, game, poison)

            condition = ability.get("condition")
            if (
                not saved
                and effective_damage > 0
                and isinstance(condition, dict)
                and condition.get("id")
            ):
                from core.conditions import apply_condition

                apply_condition(
                    player,
                    condition["id"],
                    turns=condition.get("turns"),
                    game=game,
                )

            self_heal = int(effect.get("self_heal", 0) or 0)
            if attack_hit and self_heal:
                before = getattr(enemy, "hp", 0)
                enemy.hp = min(
                    getattr(enemy, "hp_max", before), before + self_heal
                )
                if enemy.hp > before:
                    game.io.show_message(
                        f"{enemy.name} drains life and recovers "
                        f"{enemy.hp - before} HP."
                    )

            guard = int(effect.get("guard", 0) or 0)
            if attack_hit and guard:
                key = str(index)
                self.enemy_guard[key] = max(
                    int(self.enemy_guard.get(key, 0) or 0), guard
                )
                game.io.show_message(f"{enemy.name} raises its guard.")

        cooldown = int(ability.get("cooldown", 0) or 0)
        ability_id = ability.get("id") or name
        self.ability_cooldowns.setdefault(str(index), {})[
            ability_id
        ] = cooldown
    
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
            self.outcome = "fled"
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
        if not hasattr(self, "surprised"):
            self.surprised = False
        if not hasattr(self, "outcome"):
            self.outcome = None
        if not hasattr(self, "cycle_scaled"):
            self.cycle_scaled = False
        if not hasattr(self, "_initiative_checked"):
            self._initiative_checked = True
        if not hasattr(self, "last_ability_used"):
            self.last_ability_used = None
        if not isinstance(getattr(self, "ability_cooldowns", None), dict):
            self.ability_cooldowns = {}
        if not isinstance(getattr(self, "enemy_guard", None), dict):
            self.enemy_guard = {}
        if not hasattr(self, "encounter"):
            self.encounter = None
        if not hasattr(self, "encounter_rewarded"):
            self.encounter_rewarded = False

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
        state.surprised = bool(data.get("surprised", False))
        state.outcome = data.get("outcome")
        state.cycle_scaled = bool(data.get("cycle_scaled", False))
        state._initiative_checked = data.get("initiative_checked", True)
        state.damage_taken = int(data.get("damage_taken", 0) or 0)
        state.ability_cooldowns = {
            str(index): {
                str(ability_id): int(remaining or 0)
                for ability_id, remaining in cooldowns.items()
            }
            for index, cooldowns in (
                data.get("ability_cooldowns", {}) or {}
            ).items()
            if isinstance(cooldowns, dict)
        }
        state.enemy_guard = {
            str(index): int(value or 0)
            for index, value in (data.get("enemy_guard", {}) or {}).items()
        }
        encounter = data.get("encounter")
        state.encounter = dict(encounter) if isinstance(encounter, dict) else None
        state.encounter_rewarded = bool(data.get("encounter_rewarded", False))

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
            "surprised": bool(getattr(self, "surprised", False)),
            "outcome": getattr(self, "outcome", None),
            "cycle_scaled": bool(getattr(self, "cycle_scaled", False)),
            "initiative_checked": bool(
                getattr(self, "_initiative_checked", False)
            ),
            "damage_taken": int(getattr(self, "damage_taken", 0) or 0),
            "ability_cooldowns": {
                str(index): dict(cooldowns)
                for index, cooldowns in getattr(
                    self, "ability_cooldowns", {}
                ).items()
            },
            "enemy_guard": {
                str(index): int(value or 0)
                for index, value in getattr(self, "enemy_guard", {}).items()
            },
            "encounter": dict(self.encounter) if isinstance(self.encounter, dict) else None,
            "encounter_rewarded": bool(
                getattr(self, "encounter_rewarded", False)
            ),
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
