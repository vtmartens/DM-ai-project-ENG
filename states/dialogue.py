from states.base_state import BaseState
from entities.npc import NPC
from util.helpers import press_enter

class DialogueState(BaseState):
    """State that manages dialogue with an NPC"""
    
    def __init__(self, npc=None, return_state=None):
        """
        Constructor of the dialogue state
        
        Args:
            npc (NPC, optional): The NPC to talk to
            return_state (str, optional): Name of the state to return to after the dialogue
        """
        self.phase = "conversation"
        self.last_input = None
        self.npc = npc
        self.current_state = "start"
        self.return_state = return_state
        self.contextual_data = {}  # To store data across multiple phases
        self.last_effect_state = None
        
    def _quest_status(self, quest_id, game=None):
        player = (game or self.game).player
        for quest in getattr(player, "active_quests", []):
            if isinstance(quest, dict) and quest.get("id") == quest_id:
                return quest.get("status", "active")
        for quest in getattr(player, "completed_quests", []):
            if isinstance(quest, dict) and quest.get("id") == quest_id:
                return "completed"
        return None

    def _condition_met(self, condition, game=None):
        if not isinstance(condition, dict):
            return True

        all_conditions = condition.get("all")
        if isinstance(all_conditions, list):
            return all(
                self._condition_met(item, game) for item in all_conditions
            )

        any_conditions = condition.get("any")
        if isinstance(any_conditions, list):
            return any(
                self._condition_met(item, game) for item in any_conditions
            )

        reputation = condition.get("reputation")
        if isinstance(reputation, dict):
            player = (game or self.game).player
            from core.factions import reputation_value

            value = reputation_value(player, reputation.get("faction"))
            if "min" in reputation and value < int(reputation["min"]):
                return False
            if "max" in reputation and value > int(reputation["max"]):
                return False

        quest_id = condition.get("quest")
        if not quest_id:
            return True
        expected = condition.get("status")
        status = self._quest_status(quest_id, game)
        if expected in {"not_started", "none"}:
            return status is None
        return status == expected

    def _option_visible(self, option, game=None):
        if len(option) < 3 or not isinstance(option[2], dict):
            return True
        return self._condition_met(option[2], game)

    def visible_options(self, game=None, conversation_data=None):
        """Returns the options whose optional quest conditions currently hold."""
        game = game or self.game
        if conversation_data is None:
            conversation_data = self.npc.get_conversation(self.current_state) or {}
        options = []
        for option in conversation_data.get("options", []):
            if len(option) < 2:
                continue
            if self._option_visible(option, game):
                options.append((option[0], option[1]))
        return options

    def run(self, game):
        """
        Run the dialogue phase
        
        Args:
            game (Game): The game in which the dialogue is taking place
            
        Returns:
            str: the next state
        """
        # Check whether there is a valid NPC
        if not self.npc:
            game.io.show_message("There is no one to talk to here.")
            press_enter(game, "\nPress Enter to continue...")
            game.pop_state()  # Exit the current state
            return self.return_state or "map"
        
        # Get the input/output interface
        io = game.io
        
        # Get the conversation data for the current state
        conversation_data = self.npc.get_conversation(self.current_state)
        
        # If the data does not exist, return to the main menu
        if not conversation_data:
            io.show_message(f"{self.npc.name} has nothing to tell you.")
            press_enter(game, "\nPress Enter to continue...")
            game.pop_state()  # Exit the current state
            return self.return_state or "map"
        
        # Apply a node's effect once when we enter that node, not every time
        # the state re-renders while waiting for the next choice.
        if "effect" in conversation_data and getattr(
            self, "last_effect_state", None
        ) != self.current_state:
            self._manage_effect(conversation_data["effect"], game)
            self.last_effect_state = self.current_state
        
        # Show the conversation text
        io.show_message(f"{self.npc.name}: {conversation_data['text']}")
        
        options = self.visible_options(game, conversation_data)

        # If the conversation has no visible options, return to the return state
        if not options:
            press_enter(game, "\nPress Enter to continue...")
            game.pop_state()  # Exit the current state
            return self.return_state or "map"

        # The web client draws these as buttons in its dialogue card; only
        # terminal-style clients also need the numbered copy in the log.
        options_in_log = getattr(io, "dialogue_options_in_log", True)
        if options_in_log:
            io.show_message("\nOptions:")
            for i, (text, _) in enumerate(options, 1):
                io.show_message(f"{i}. {text}")

        # Get the user's choice
        selection_input = io.request_input(
            "\nChoose an option: " if options_in_log else ""
        )

        # Convert the input to a number
        try:
            selection = int(selection_input)
            if selection < 1 or selection > len(options):
                io.show_message("Invalid choice.")
                press_enter(game, "\nPress Enter to continue...")
                return "dialogue"  # Stay in the same state

            # Get the destination (next state) of the choice
            _, destination = options[selection - 1]
            
            # If the destination is None, return to the return state
            if destination is None:
                # Add a pause to read the message
                press_enter(game, "\nPress Enter to continue...")
                game.pop_state()  # Exit the current state
                return self.return_state or "map"
            
            # Otherwise, move to the next state of the conversation
            self.current_state = destination
            return "dialogue"
        except ValueError:
            io.show_message("Please enter a valid number.")
            press_enter(game, "\nPress Enter to continue...")
            return "dialogue"
    
    def _manage_effect(self, effect, game):
        """Apply special effects based on the effect type"""
        if isinstance(effect, list):
            for item in effect:
                self._manage_effect(item, game)
            return

        if isinstance(effect, str):
            # Handle simple effects
            if effect == "rest":
                game.player.heal(5, game)
                game.io.show_message("\n*You rested and recovered 5 HP*")
            elif effect == "light_heal":
                game.player.heal(3, game)
                game.io.show_message("\n*Violetta's ointment heals you for 3 HP*")
        elif isinstance(effect, dict):
            # Handle complex effects
            type = effect.get("type", "")
            
            if type == "give_gold":
                quantity = effect.get("quantity", 10)
                self.npc.transfer_gold(game.player, quantity, game)
                game.io.show_message(f"\n*{self.npc.name} gave you {quantity} gold coins*")
                
            elif type == "add_item":
                item_name = effect.get("item")
                found = None
                for npc_item in getattr(self.npc, "inventory", []):
                    if getattr(npc_item, "name", npc_item) == item_name:
                        found = npc_item
                        break
                if found is not None and self.npc.remove_item(item_name):
                    game.player.add_item(found)
                    game.io.show_message(
                        f"\n*You received {item_name} from {self.npc.name}*"
                    )
                    
            elif type == "remove_item":
                item = effect.get("item")
                if item and game.player.remove_item(item):
                    self.npc.add_item(item)
                    game.io.show_message(f"\n*You gave {item} to {self.npc.name}*")
                    
            elif type == "start_quest":
                from core.quests import start_quest

                start_quest(game.player, effect.get("quest"), game)

            elif type == "complete_quest":
                from core.quests import complete_quest

                complete_quest(game.player, effect.get("quest"), game)

            elif type == "recruit_ally":
                from core.quests import recruit_ally

                recruit_ally(game.player, effect.get("npc"), game)

            elif type == "adjust_reputation":
                from core.factions import adjust_reputation

                adjust_reputation(
                    game.player,
                    effect.get("faction"),
                    int(effect.get("amount", 0) or 0),
                    game,
                )

            elif type == "trade":
                item_name = effect.get("item")
                cost = effect.get("cost", 0)
                
                # Find the item in the NPC's inventory
                found_item = None
                for npc_item in self.npc.inventory:
                    if npc_item.name == item_name:
                        found_item = npc_item
                        break
                
                if game.player.gold >= cost and found_item is not None:
                    game.player.gold -= cost
                    self.npc.gold += cost
                    self.npc.remove_item(item_name)
                    game.player.add_item(found_item)
                    game.io.show_message(f"\n*You bought {item_name} from {self.npc.name} for {cost} gold coins*")
                else:
                    if game.player.gold < cost:
                        game.io.show_message(f"\n*You do not have enough gold to buy {item_name}*")
                    else:
                        game.io.show_message(f"\n*{self.npc.name} no longer has {item_name} available*")

    def pause(self, game):
        """
        When the dialogue is paused
        we save the current state of the dialogue
        """
        game.io.show_message(f"\nThe dialogue with {self.npc.name} remains suspended...")
        
    def resume(self, game):
        """
        When the dialogue resumes after a pause
        we show a resume message
        """
        game.io.show_message(f"\nYou resume the dialogue with {self.npc.name}...")
        
    def exit(self, game):
        """
        When exiting the dialogue
        we clean up the state
        """
        self.phase = "conversation"
        game.io.show_message(f"\nYou conclude the dialogue with {self.npc.name}...")
        
    def has_made_choice(self, state, selection=None):
        """
        Check whether the player made a particular choice during the dialogue
        
        Args:
            state (str): The dialogue state
            selection (int, optional): The specific choice to check
            
        Returns:
            bool: True if the choice was made, False otherwise
        """
        if state not in self.contextual_data:
            return False
            
        if selection is None:
            return True
            
        return self.contextual_data[state] == selection

    def to_dict(self):
        """
        Convert the dialogue state into a dictionary for serialization.
        
        Returns:
            dict: Dictionary representation of the state
        """
        # Get the base dictionary
        data = super().to_dict()
        
        # Add specific attributes
        data.update({
            "current_state": self.current_state,
            "return_state": self.return_state,
            "contextual_data": self.contextual_data,
            "last_input": self.last_input,
            "last_effect_state": getattr(self, "last_effect_state", None),
        })
        
        # Save the NPC information
        if self.npc:
            if hasattr(self.npc, 'to_dict'):
                data["npc"] = self.npc.to_dict()
            else:
                data["npc"] = {"name": self.npc.name}
        
        return data
    
    @classmethod
    def from_dict(cls, data):
        """
        Create an instance of DialogueState from a dictionary.
        
        Args:
            data (dict): Dictionary with the state data
            
        Returns:
            DialogueState: New instance of DialogueState
        """
        # Creating a dialogue requires an NPC
        from entities.npc import NPC
        
        # Retrieve or create the NPC
        npc_data = data.get("npc", {})
        if isinstance(npc_data, dict):
            if hasattr(NPC, 'from_dict'):
                npc = NPC.from_dict(npc_data)
            else:
                npc = NPC(npc_data.get("name", "Unknown NPC"))
        else:
            npc = NPC("Unknown NPC")
            
        # Create the state with the NPC
        state = cls(npc, return_state=data.get("return_state"))
        
        # Restore attributes
        state.current_state = data.get("current_state", "start")
        state.contextual_data = data.get("contextual_data", {})
        state.last_input = data.get("last_input")
        state.last_effect_state = data.get(
            "last_effect_state", state.current_state
        )

        return state
        
    def __getstate__(self):
        """
        Special method for serialization with pickle.
        
        Returns:
            dict: Serializable state of the object
        """
        state = self.__dict__.copy()
        
        # Remove any circular or non-serializable references
        # The dialogue-specific variables are already primitive
        
        return state
    
    def __setstate__(self, state):
        """
        Special method for deserialization with pickle.
        
        Args:
            state (dict): Object state to restore
        """
        self.__dict__.update(state)
