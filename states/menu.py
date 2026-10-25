from states.base_state import BaseState
from states.combat import CombatState

class MenuState(BaseState):
    def run(self, game):
        game.io.show_message("\n=== Main Menu ===")
        game.io.show_message("1. Start Game")
        game.io.show_message("2. Exit")
        
        selection = game.io.request_input("Choose an option:")
        
        if selection == "1":
            game.change_state(CombatState())
        elif selection == "2":
            game.running = False
        else:
            game.io.error_message("Invalid choice!") 
            
    def to_dict(self):
        """
        Convert the state into a dictionary for serialization.
        
        Returns:
            dict: Dictionary representation of the state
        """
        # Use the base method because MenuState has no additional attributes
        return super().to_dict()

    @classmethod
    def from_dict(cls, data):
        """
        Create an instance of MenuState from a dictionary.
        
        Args:
            data (dict): Dictionary with the state data
            
        Returns:
            MenuState: New instance of the state
        """
        return cls() 