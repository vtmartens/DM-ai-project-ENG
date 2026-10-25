from states.base_state import BaseGameState
from states.tavern import TavernState
from states.market import MarketState
from states.map_state import MapState
from util.helpers import press_enter

class MapSelectionState(BaseGameState):
    """
    State that allows the player to choose among several available maps.
    It works as a central hub for navigating between the game's different areas.
    """
    
    def __init__(self, game=None):
        """
        Initialize the map selection state.
        
        Args:
            game: The game instance (optional)
        """
        super().__init__(game)
        self.state_name = "map_selection"
        self.previous_state = None
        
        # Flag indicating whether this is the first run after loading the game
        self.first_execution = True
        
    def enter(self, game=None):
        """
        Method called when entering the state.
        
        Args:
            game: The game instance (optional)
        """
        super().enter(game)
        # Save the current map state so we can go back if needed
        if game:
            self.current_map = game.player.current_map
    
    def run(self, game):
        """
        Run the state's main logic.
        
        Args:
            game: The game instance
        """
        # Show the map selection menu
        game.io.show_message("\n=== DESTINATION SELECTION ===")
        
        # Get the list of available maps from the map manager
        available_maps = list(game.map_manager.maps.keys())
        
        # Show the options
        game.io.show_message("Where do you want to go?")
        
        # Show the available maps
        for i, map_name in enumerate(available_maps, 1):
            # Capitalize the map name for a better presentation
            formatted_name = map_name.capitalize()
            # Highlight the current map
            if map_name == game.player.current_map:
                game.io.show_message(f"{i}. {formatted_name} (current position)")
            else:
                game.io.show_message(f"{i}. {formatted_name}")
                
        # Add the option to go back
        game.io.show_message(f"{len(available_maps) + 1}. Go back")
        
        # Get the user's choice
        selection = game.io.request_input("\nChoose a destination: ")
        
        try:
            selection_num = int(selection)
            
            # Check whether the user chose to go back
            if selection_num == len(available_maps) + 1:
                if game.current_state():
                    game.pop_state()  # Return to the previous state
                return
                
            # Check that the choice is valid
            if 1 <= selection_num <= len(available_maps):
                selected_map = available_maps[selection_num - 1]
                
                # Check whether the chosen map differs from the current one
                if selected_map != game.player.current_map:
                    game.io.show_message(f"You head toward {selected_map.capitalize()}...")
                    press_enter(game)
                    
                    # Perform the map change
                    self._change_map(game, selected_map)
                    return  # Stop execution here after the map change
                else:
                    # If this is the first run after loading, we enter the map anyway
                    if self.first_execution:
                        self.first_execution = False  # Reset the flag
                        game.io.show_message(f"You enter {selected_map.capitalize()}...")
                        press_enter(game)
                        
                        # Perform the map change as if it were a new map
                        self._change_map(game, selected_map)
                        return
                    else:
                        # Normal behavior when already in the map
                        game.io.show_message("You are already in this position.")
                        press_enter(game)
                        
                        # Instead of returning to the previous state, we stay in the current state
                        # Ask the user for input again
                        self.run(game)
                        return
            else:
                game.io.error_message("Invalid choice.")
                press_enter(game)
                # Ask for input again
                self.run(game)
                return
                
        except ValueError:
            game.io.error_message("Enter a valid number.")
            press_enter(game)
            # Ask for input again
            self.run(game)
            return
            
    def _change_map(self, game, destination_map):
        """
        Handle the map and state change.
        
        Args:
            game: The game instance
            destination_map: Name of the destination map
        """
        # Change the player's current map
        map = game.map_manager.get_map(destination_map)
        if map:
            # Prepare the new state based on the chosen map
            new_state = None
            if destination_map == "tavern":
                new_state = TavernState(game)
                # Set first_visit to False if the player already had an active map
                # (this means it is not the first time they enter the game)
                if hasattr(self, 'current_map') and self.current_map:
                    new_state.first_visit = False
            elif destination_map == "market":
                new_state = MarketState(game)
            else:
                # For other maps, use MapState with the correct state as origin
                new_state = MapState()
            
            # Check that the new state was created correctly
            if new_state:
                # Change the current map
                game.map_manager.set_current_map(destination_map)
                x, y = map.player_start_position
                game.player.set_position(destination_map, x, y)
                
                # Instead of removing this state and then adding the new one,
                # we directly replace the current state using change_state
                new_state.set_game_context(game)
                game.change_state(new_state)
                
                # Add a message confirming to the user that they have arrived
                game.io.show_message(f"You have arrived at {destination_map.capitalize()}.")
                
                # Run the state immediately to avoid flow interruptions
                new_state.run(game)
            else:
                game.io.error_message(f"Error creating the state for {destination_map}.")
        else:
            game.io.error_message(f"Map {destination_map} not found.")
            
    def to_dict(self):
        """
        Convert the state into a dictionary for serialization.
        
        Returns:
            dict: Dictionary representation of the state
        """
        data = super().to_dict()
        data.update({
            "current_map": getattr(self, 'current_map', None),
            "first_execution": getattr(self, 'first_execution', False)
        })
        return data
        
    @classmethod
    def from_dict(cls, data, game=None):
        """
        Create an instance of MapSelectionState from a dictionary.
        
        Args:
            data (dict): Dictionary with the state data
            game: Game instance (optional)
            
        Returns:
            MapSelectionState: New instance of the state
        """
        state = cls(game)
        state.current_map = data.get("current_map")
        state.first_execution = data.get("first_execution", False)
        return state 