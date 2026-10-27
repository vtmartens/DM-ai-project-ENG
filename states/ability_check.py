from states.base_state import BaseState
from util.dice import Dice
from util.helpers import press_enter
from entities.npc import NPC
from items.interactive_object import InteractiveObject
from items.item import Item
from entities.player import Player
from entities.entity import ASSOCIATED_SKILLS


class AbilityCheckState(BaseState):
    def __init__(self, context=None):
        """
        Initialize the ability check state.
        
        Args:
            context (dict, optional): Optional context for the check (e.g. associated object)
        """
        self.context = context or {}
        self.phase = "choose_ability"  # Initial phase
        self.last_input = None  # To store the user's last input
        self.chosen_ability = None  # The ability chosen by the user
        self.contextual_data = {}  # To store data across multiple phases

    def _consume_guidance(self, game):
        """Returns and clears the Guidance bonus for the next check."""
        conditions = getattr(game.player, "conditions", None)
        if not isinstance(conditions, dict):
            return 0

        guidance = conditions.pop("guidance", None)
        if isinstance(guidance, dict):
            try:
                return int(guidance.get("bonus", 0) or 0)
            except (TypeError, ValueError):
                return 0
        try:
            return int(guidance or 0)
        except (TypeError, ValueError):
            return 0

    def _roll_with_guidance(self, game):
        """Rolls d20 and applies (consuming) any active Guidance bonus."""
        roll = Dice(20).roll()
        bonus = self._consume_guidance(game)
        if bonus:
            game.io.show_message(f"Guidance adds {bonus} to the check.")
        return roll, bonus

    def run(self, game):
        game.io.show_message("\n=== ABILITY CHECK ===")
        
        # Handling based on the current phase
        if self.phase == "choose_ability":
            self._show_menu_ability(game)
        elif self.phase == "process_ability_selection":
            self._process_selection_ability(game)
        elif self.phase == "choose_mode":
            self._show_menu_mode(game)
        elif self.phase == "process_mode":
            self._process_mode(game)
        elif self.phase == "check_base":
            self._run_check_base(game)
        elif self.phase == "check_npc":
            self._run_check_npc(game)
        elif self.phase == "check_item":
            self._run_check_item(game)
        elif self.phase == "specific_ability":
            self._specific_run_check_ability(game)
        elif self.phase == "process_specific_ability_selection":
            self._specific_process_selection_ability(game)
        elif self.phase == "conclusion":
            self._conclude_check(game)
        else:
            # Unrecognized phase, return to the main menu
            self.phase = "choose_ability"
            self.run(game)
    
    def _show_menu_ability(self, game):
        game.io.show_message("Which ability do you want to test?")
        game.io.show_message("1. Strength")
        game.io.show_message("2. Dexterity")
        game.io.show_message("3. Constitution")
        game.io.show_message("4. Intelligence")
        game.io.show_message("5. Wisdom")
        game.io.show_message("6. Charisma")
        game.io.show_message("7. Check a specific skill (e.g. Perception, Persuasion)")
        game.io.show_message("8. Go back")
        
        self.last_input = game.io.request_input("\nChoose: ")
        self.phase = "process_ability_selection"
    
    def _process_selection_ability(self, game):
        ability = {
            "1": "strength",
            "2": "dexterity",
            "3": "constitution",
            "4": "intelligence",
            "5": "wisdom",
            "6": "charisma"
        }
        
        selection = self.last_input
        
        if selection in ability:
            self.chosen_ability = ability[selection]
            self.phase = "choose_mode"
        elif selection == "7":
            self.phase = "specific_ability"
        elif selection == "8":
            if game.current_state():
                game.pop_state()
        else:
            game.io.error_message("Invalid choice.")
            self.phase = "choose_ability"
    
    def _show_menu_mode(self, game):
        game.io.show_message("\nChoose the check mode:")
        game.io.show_message("1. Basic check (against difficulty)")
        game.io.show_message("2. Check against a non-player character (NPC)")
        game.io.show_message("3. Check with an interactive object")
        game.io.show_message("4. Go back")
        
        self.last_input = game.io.request_input("\nChoose mode: ")
        self.phase = "process_mode"
    
    def _process_mode(self, game):
        mode = self.last_input
        
        if mode == "1":
            # Basic check
            self.phase = "check_base"
        elif mode == "2":
            # Check against an NPC
            self.phase = "check_npc"
        elif mode == "3":
            # Check with an interactive object
            self.phase = "check_item"
        elif mode == "4":
            # Return to the ability menu
            self.phase = "choose_ability"
        else:
            game.io.error_message("Invalid choice.")
            self.phase = "choose_mode"
    
    def _run_check_base(self, game):
        if "difficulty" not in self.contextual_data:
            try:
                difficulty_input = game.io.request_input("Enter the difficulty (5-20): ")
                difficulty = int(difficulty_input)
                difficulty = max(5, min(20, difficulty))  # Clamp between 5 and 20
                self.contextual_data["difficulty"] = difficulty
            except ValueError:
                game.io.error_message("You must enter a number for the difficulty.")
                self.phase = "choose_mode"
                return
        
        # Perform the check
        difficulty = self.contextual_data["difficulty"]

        # Get the modifier based on the ability type
        if self.chosen_ability in ASSOCIATED_SKILLS:
            # For specific skills, use the ability_modifier method
            modifier = game.player.ability_modifier(self.chosen_ability, game)
        else:
            # For base attributes, use the attribute directly
            modifier = getattr(game.player, self.chosen_ability)

        roll, guidance = self._roll_with_guidance(game)
        result = roll + modifier + guidance

        # If available, also show the ability's base value
        if hasattr(game.player, f"{self.chosen_ability}_base"):
            base_value = getattr(game.player, f"{self.chosen_ability}_base")
            game.io.show_message(f"\n{game.player.name} has {self.chosen_ability.capitalize()} {base_value} (modifier: {modifier})")

        bonus_text = f" + {guidance} (guidance)" if guidance else ""
        game.io.show_message(f"{game.player.name} rolls a {roll} + {modifier}{bonus_text} ({self.chosen_ability}) = {result}")
        
        if result >= difficulty:
            game.io.show_message(f"You passed the {self.chosen_ability} check!")
            self._manage_success(game, self.chosen_ability)
        else:
            game.io.show_message(f"You failed the {self.chosen_ability} check.")
            self._manage_failure(game, self.chosen_ability)
            
        # Wait for confirmation and return to the main menu
        press_enter(game, "\nPress Enter to continue...")
        if game.current_state():
            game.pop_state()
    
    def _run_check_npc(self, game):
        """Run a check against an NPC"""
        # Phase: NPC list
        if "phase_npc" not in self.contextual_data:
            # Get the second-to-last state in the stack (the state that invoked this one)
            previous_state = game.state_stack[-2] if len(game.state_stack) > 1 else None
            
            if not previous_state or not hasattr(previous_state, 'present_npcs'):
                game.io.show_message("There are no non-player characters nearby.")
                self.phase = "choose_mode"
                return
            
            game.io.show_message("\nChoose the character to make the check against:")
            
            # Handle both dictionaries and lists
            if isinstance(previous_state.present_npcs, dict):
                for i, name in enumerate(previous_state.present_npcs.keys(), 1):
                    game.io.show_message(f"{i}. {name}")
                
                self.contextual_data["phase_npc"] = "selection_npc"
                self.contextual_data["type_list"] = "dictionary"
                self.contextual_data["previous_state"] = previous_state
                self.last_input = game.io.request_input("\nChoose NPC: ")
                return
            else:
                # Handle lists
                for i, npc in enumerate(previous_state.present_npcs, 1):
                    game.io.show_message(f"{i}. {npc.name}")
                
                self.contextual_data["phase_npc"] = "selection_npc"
                self.contextual_data["type_list"] = "list"
                self.contextual_data["previous_state"] = previous_state
                self.last_input = game.io.request_input("\nChoose NPC: ")
                return
        
        # Phase: process the NPC choice
        if self.contextual_data["phase_npc"] == "selection_npc":
            try:
                selection = int(self.last_input)
                previous_state = self.contextual_data["previous_state"]
                
                if self.contextual_data["type_list"] == "dictionary":
                    if 1 <= selection <= len(previous_state.present_npcs):
                        npc_name = list(previous_state.present_npcs.keys())[selection - 1]
                        npc = previous_state.present_npcs[npc_name]
                        self.contextual_data["npc"] = npc
                        self.contextual_data["phase_npc"] = "perform_check"
                    else:
                        game.io.error_message("Invalid choice.")
                        self.phase = "choose_mode"
                        return
                else:  # list
                    if 1 <= selection <= len(previous_state.present_npcs):
                        npc = previous_state.present_npcs[selection - 1]
                        self.contextual_data["npc"] = npc
                        self.contextual_data["phase_npc"] = "perform_check"
                    else:
                        game.io.error_message("Invalid choice.")
                        self.phase = "choose_mode"
                        return
            except ValueError:
                game.io.error_message("You must enter a number.")
                self.phase = "choose_mode"
                return
        
        # Phase: perform the check
        npc = self.contextual_data["npc"]
        
        # Get the modifier based on the ability type
        if self.chosen_ability in ASSOCIATED_SKILLS:
            # For specific skills, use the ability_modifier method
            modifier = game.player.ability_modifier(self.chosen_ability, game)
        else:
            # For base attributes, use the attribute directly
            modifier = getattr(game.player, self.chosen_ability)

        if hasattr(game.player, f"{self.chosen_ability}_base") and hasattr(npc, f"{self.chosen_ability}_base"):
            g_value = getattr(game.player, f"{self.chosen_ability}_base")
            n_value = getattr(npc, f"{self.chosen_ability}_base")
            game.io.show_message(f"{game.player.name}: {self.chosen_ability.capitalize()} {g_value} (mod: {modifier})")

        # Determine the difficulty based on the ability
        if self.chosen_ability in ["strength", "dexterity", "constitution"]:
            # Physical check - compare with the NPC's same attribute
            difficulty = getattr(npc, self.chosen_ability, 3) + 10  # Base 10 + NPC mod
        elif self.chosen_ability in ["intelligence", "wisdom", "charisma"]:
            # Social/mental check
            difficulty = getattr(npc, self.chosen_ability, 3) + 8   # Base 8 + NPC mod
        else:
            # Specific skills - standard difficulty
            difficulty = 12

        roll, guidance = self._roll_with_guidance(game)
        result = roll + modifier + guidance

        bonus_text = f" + {guidance} (guidance)" if guidance else ""
        game.io.show_message(f"\n{game.player.name} rolls a {roll} + {modifier}{bonus_text} ({self.chosen_ability}) = {result}")
        game.io.show_message(f"Difficulty against {npc.name}: {difficulty}")
        
        if result >= difficulty:
            game.io.show_message(f"You passed the {self.chosen_ability} check against {npc.name}!")
            self._manage_success_npc(game, self.chosen_ability, npc)
        else:
            game.io.show_message(f"You failed the {self.chosen_ability} check against {npc.name}.")
            self._manage_failure_npc(game, self.chosen_ability, npc)
        
        # Wait for confirmation and return to the main menu
        press_enter(game, "\nPress Enter to continue...")
        if game.current_state():
            game.pop_state()
    
    def _run_check_item(self, game):
        """Run a check with an interactive object"""
        # Phase: object list
        if "phase_item" not in self.contextual_data:
            # Get the second-to-last state in the stack (the state that invoked this one)
            previous_state = game.state_stack[-2] if len(game.state_stack) > 1 else None
            
            if not previous_state or not hasattr(previous_state, 'interactive_objects'):
                game.io.show_message("There are no interactive objects nearby.")
                self.phase = "choose_mode"
                return
            
            game.io.show_message("\nChoose the object to interact with:")
            
            # Handle both dictionaries and lists
            if isinstance(previous_state.interactive_objects, dict):
                for i, name in enumerate(previous_state.interactive_objects.keys(), 1):
                    item = previous_state.interactive_objects[name]
                    game.io.show_message(f"{i}. {item.name} [{item.state}]")
                
                # Add the "Go back" option AFTER the objects
                num_option_return = len(previous_state.interactive_objects) + 1
                game.io.show_message(f"{num_option_return}. Go back")
                
                self.contextual_data["phase_item"] = "selection_item"
                self.contextual_data["type_list"] = "dictionary"
                self.contextual_data["previous_state"] = previous_state
                self.last_input = game.io.request_input("\nChoose object: ")
                return
            else:
                # Handle lists
                for i, item in enumerate(previous_state.interactive_objects, 1):
                    game.io.show_message(f"{i}. {item.name} [{item.state}]")
                
                # Add the "Go back" option
                num_option_return = len(previous_state.interactive_objects) + 1
                game.io.show_message(f"{num_option_return}. Go back")
                
                self.contextual_data["phase_item"] = "selection_item"
                self.contextual_data["type_list"] = "list"
                self.contextual_data["previous_state"] = previous_state
                self.last_input = game.io.request_input("\nChoose object: ")
                return
        
        # Phase: process the object choice
        if self.contextual_data["phase_item"] == "selection_item":
            try:
                selection = int(self.last_input)
                previous_state = self.contextual_data["previous_state"]
                
                if self.contextual_data["type_list"] == "dictionary":
                    num_option_return = len(previous_state.interactive_objects) + 1
                    if 1 <= selection <= len(previous_state.interactive_objects):
                        item_name = list(previous_state.interactive_objects.keys())[selection - 1]
                        item = previous_state.interactive_objects[item_name]
                        self.contextual_data["item"] = item
                        self.contextual_data["phase_item"] = "perform_check"
                    elif selection == num_option_return:
                        self.phase = "choose_mode"
                        return
                    else:
                        game.io.error_message("Invalid choice.")
                        self.phase = "choose_mode"
                        return
                else:  # list
                    num_option_return = len(previous_state.interactive_objects) + 1
                    if 1 <= selection <= len(previous_state.interactive_objects):
                        item = previous_state.interactive_objects[selection - 1]
                        self.contextual_data["item"] = item
                        self.contextual_data["phase_item"] = "perform_check"
                    elif selection == num_option_return:
                        self.phase = "choose_mode"
                        return
                    else:
                        game.io.error_message("Invalid choice.")
                        self.phase = "choose_mode"
                        return
            except ValueError:
                game.io.error_message("You must enter a number.")
                self.phase = "choose_mode"
                return
        
        # Phase: perform the check
        item = self.contextual_data["item"]
        
        # Get the modifier based on the ability type
        if self.chosen_ability in ASSOCIATED_SKILLS:
            # For specific skills, use the ability_modifier method
            modifier = game.player.ability_modifier(self.chosen_ability, game)
        else:
            # For base attributes, use the attribute directly
            modifier = getattr(game.player, self.chosen_ability)

        # Display the base values if available
        if hasattr(game.player, f"{self.chosen_ability}_base"):
            base_value = getattr(game.player, f"{self.chosen_ability}_base")
            game.io.show_message(f"\n{game.player.name} has {self.chosen_ability.capitalize()} {base_value} (modifier: {modifier})")

        # Determine the difficulty based on the object type and the ability
        if isinstance(item, InteractiveObject):
            if self.chosen_ability == "strength" and hasattr(item, "required_strength"):
                difficulty = item.required_strength + 8
            elif self.chosen_ability == "dexterity" and hasattr(item, "saving_throw_difficulty"):
                difficulty = item.saving_throw_difficulty
            else:
                difficulty = 12  # Standard difficulty
        else:
            difficulty = 10  # Generic object

        roll, guidance = self._roll_with_guidance(game)
        result = roll + modifier + guidance

        bonus_text = f" + {guidance} (guidance)" if guidance else ""
        game.io.show_message(f"\n{game.player.name} rolls a {roll} + {modifier}{bonus_text} ({self.chosen_ability}) = {result}")
        game.io.show_message(f"Difficulty for {item.name}: {difficulty}")
        
        self.context["type"] = "item"
        self.context["item"] = item
        
        if result >= difficulty:
            game.io.show_message(f"You passed the {self.chosen_ability} check with {item.name}!")
            self._manage_success(game, self.chosen_ability)
            
            # Activate the specific interaction with the object
            if self.chosen_ability == "strength" and hasattr(item, "state") and item.state == "intact":
                game.io.show_message(f"Thanks to your strength, you can interact effectively with {item.name}!")
                item.interact(game.player)
        else:
            game.io.show_message(f"You failed the {self.chosen_ability} check with {item.name}.")
            self._manage_failure(game, self.chosen_ability)
        
        # Wait for confirmation and return to the main menu
        press_enter(game, "\nPress Enter to continue...")
        if game.current_state():
            game.pop_state()
    
    def _specific_run_check_ability(self, game):
        """Handle the check for a specific skill such as Perception, Persuasion, etc."""
        game.io.show_message("\nChoose the skill to test:")
        for i, ability in enumerate(ASSOCIATED_SKILLS.keys(), 1):
            # Show whether the player has proficiency
            proficiency = " [Proficient]" if game.player.skill_proficiencies.get(ability.lower()) else ""
            game.io.show_message(f"{i}. {ability.capitalize()}{proficiency}")
        
        self.last_input = game.io.request_input("\nChoose: ")
        self.phase = "process_specific_ability_selection"
    
    def _specific_process_selection_ability(self, game):
        try:
            idx = int(self.last_input) - 1
            if 0 <= idx < len(ASSOCIATED_SKILLS):
                self.chosen_ability = list(ASSOCIATED_SKILLS.keys())[idx].lower()
                self.contextual_data["chosen_ability"] = self.chosen_ability
                self.phase = "choose_mode"
            else:
                game.io.error_message("Invalid choice.")
                self.phase = "specific_ability"
        except (IndexError, ValueError):
            game.io.error_message("Invalid choice.")
            self.phase = "specific_ability"
    
    def _conclude_check(self, game):
        press_enter(game, "\nPress Enter to continue...")
        if game.current_state():
            game.pop_state()
            
    # Effect handling methods (remain unchanged)
    
    def _manage_success(self, game, ability):
        """Handle the effects of success in the check"""
        if self.context.get("type") == "item":
            item = self.context.get("item")
            if item:
                game.io.show_message(f"You successfully interacted with {item.name}!")
                
        # Small reward for success
        exp = 5
        if game.player.gain_experience(exp, game):
            game.io.show_message(f"You gained {exp} experience points and leveled up!")
        else:
            game.io.show_message(f"You gained {exp} experience points.")
    
    def _manage_failure(self, game, ability):
        """Handle the effects of failure in the check"""
        if self.context.get("type") == "item":
            item = self.context.get("item")
            if item:
                game.io.show_message(f"You failed to interact with {item.name}.")
                
                # If there is a penalty, apply it
                if self.context.get("penalty"):
                    damage = self.context.get("penalty")
                    game.player.take_damage(damage)
                    game.io.show_message(f"You take {damage} damage!")
    
    def _manage_success_npc(self, game, ability, npc):
        """Handle the effects of success in the check against an NPC"""
        game.io.show_message(f"The interaction with {npc.name} succeeded!")
        
        # Different behavior depending on the ability
        if ability in ASSOCIATED_SKILLS:
            # Specific skills
            if ability == "persuasion":
                game.io.show_message(f"You managed to persuade {npc.name}!")
                if hasattr(npc, "current_state"):
                    npc.change_state("persuaded")
            elif ability == "intimidation":
                game.io.show_message(f"You managed to intimidate {npc.name}!")
                if hasattr(npc, "current_state"):
                    npc.change_state("intimidated")
            elif ability == "deception":
                game.io.show_message(f"You managed to deceive {npc.name}!")
                if hasattr(npc, "current_state"):
                    npc.change_state("deceived")
            elif ability == "perception" or ability == "investigation":
                game.io.show_message(f"You noticed something important about {npc.name}!")
        else:
            # Base attributes (existing code)
            if ability == "strength":
                game.io.show_message(f"You impressed {npc.name} with your strength!")
            elif ability == "dexterity":
                game.io.show_message(f"{npc.name} is impressed by your agility!")
            elif ability == "charisma":
                game.io.show_message(f"{npc.name} is charmed by your presence!")
                if hasattr(npc, "current_state"):
                    npc.change_state("friendly")
        
        # Base reward
        exp = 8
        if game.player.gain_experience(exp, game):
            game.io.show_message(f"You gained {exp} experience points and leveled up!")
        else:
            game.io.show_message(f"You gained {exp} experience points.")
    
    def _manage_failure_npc(self, game, ability, npc):
        """Handle the failure of a check against an NPC"""
        # Determine the effects of the failure based on the ability
        if ability == "strength":
            game.io.show_message(f"{npc.name} proved stronger and knocked you down!")
            game.player.take_damage(1)
        elif ability == "dexterity":
            game.io.show_message(f"{npc.name} is too fast for you!")
        elif ability == "constitution":
            game.io.show_message(f"Your endurance is no match for {npc.name}.")
            game.player.take_damage(1)
        elif ability == "intelligence":
            game.io.show_message(f"{npc.name} outsmarted you!")
        elif ability == "wisdom":
            game.io.show_message(f"{npc.name} is more perceptive than you.")
        elif ability == "charisma":
            game.io.show_message(f"{npc.name} ignores you completely after your failed attempt.")
        else:  # Failure of a specific skill
            game.io.show_message(f"Your attempt at {ability} against {npc.name} fails miserably!")

    def to_dict(self):
        """
        Convert the state into a dictionary for serialization.
        
        Returns:
            dict: Dictionary representation of the state
        """
        # Get the base dictionary
        data = super().to_dict()
        
        # Add specific attributes
        data.update({
            "phase": self.phase,
            "last_input": self.last_input,
            "chosen_ability": self.chosen_ability
        })
        
        # Handle context and contextual_data
        # Filter only the serializable data
        serializable_context = {}
        for k, v in self.context.items():
            if isinstance(v, (str, int, float, bool, list, dict, tuple, type(None))):
                serializable_context[k] = v
            elif hasattr(v, 'to_dict') and callable(getattr(v, 'to_dict')):
                serializable_context[k] = v.to_dict()
        
        contextual_serializable_data = {}
        for k, v in self.contextual_data.items():
            if isinstance(v, (str, int, float, bool, list, dict, tuple, type(None))):
                contextual_serializable_data[k] = v
            elif hasattr(v, 'to_dict') and callable(getattr(v, 'to_dict')):
                contextual_serializable_data[k] = v.to_dict()
                
        data["context"] = serializable_context
        data["contextual_data"] = contextual_serializable_data
        
        return data

    @classmethod
    def from_dict(cls, data):
        """
        Create an instance of AbilityCheckState from a dictionary.
        
        Args:
            data (dict): Dictionary with the state data
            
        Returns:
            AbilityCheckState: New instance of the state
        """
        context = data.get("context", {})
        state = cls(context)
        
        # Restore attributes
        state.phase = data.get("phase", "choose_ability")
        state.last_input = data.get("last_input")
        state.chosen_ability = data.get("chosen_ability")
        state.contextual_data = data.get("contextual_data", {})
        
        return state
