from states.base_state import BaseState
from util.helpers import press_enter

class MapState(BaseState):
    def __init__(self, origin_state=None):
        """
        Initialize the map state.
        
        Args:
            origin_state: The state it comes from (e.g. TavernState or MarketState)
        """
        self.origin_state = origin_state
        self.show_legend = True
        
        # Movement directions
        self.directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0)
        }
    
    def run(self, game):
        if not game.player.current_map:
            game.io.show_message("Map system not available!")
            if game.current_state():
                game.pop_state()
            return
            
        current_map = game.map_manager.get_map(game.player.current_map)
        map_name = game.player.current_map.upper()
        
        game.io.show_message(f"\n=== MAP OF {map_name} ===")
        
        # Display the map
        representation = current_map.generate_ascii_representation(
            (game.player.x, game.player.y))
        game.io.show_message(representation)
        
        if self.show_legend:
            self._show_legend(game)
        
        # Show information about the player's position
        game.io.show_message(f"\nCurrent position: ({game.player.x}, {game.player.y})")
        
        # Show interactive menu
        game.io.show_message("\nWhat do you want to do?")
        game.io.show_message("1. Move")
        game.io.show_message("2. Interact with the environment")
        game.io.show_message("3. Show nearby elements")
        game.io.show_message("4. Show/hide legend")
        game.io.show_message("5. Go back")
        
        selection = game.io.request_input("\nChoice: ")
        
        if selection == "1":
            self._move_player(game)
        elif selection == "2":
            self._interact_environment(game)
        elif selection == "3":
            self._nearby_show_elements(game)
        elif selection == "4":
            self.show_legend = not self.show_legend
            game.io.system_message("Legend " + ("activated" if self.show_legend else "deactivated"))
        elif selection == "5":
            if game.current_state():
                game.pop_state()
        else:
            game.io.error_message("Invalid choice.")
        
        press_enter(game)
    
    def _show_legend(self, game):
        game.io.show_message("\nLegend:")
        game.io.show_message("P = Player")
        game.io.show_message("N = Generic NPC")
        game.io.show_message("O = Generic object")
        game.io.show_message("D = Door")
        game.io.show_message("C = Chest")
        game.io.show_message("L = Lever")
        game.io.show_message("T = Trap")
        game.io.show_message("M = Monster/Enemy")
        game.io.show_message("# = Wall")
        game.io.show_message(". = Empty space")
        # Add other special tokens if needed
    
    def _move_player(self, game):
        """Handle the player's movement on the map"""
        game.io.show_message("\n=== MOVEMENT ===")
        game.io.show_message("1. North")
        game.io.show_message("2. South")
        game.io.show_message("3. East")
        game.io.show_message("4. West")
        game.io.show_message("5. Back")
        
        selection = game.io.request_input("\nChoose a direction: ")
        
        if selection == "1":
            self._move_player_position(game, "north")
        elif selection == "2":
            self._move_player_position(game, "south")
        elif selection == "3":
            self._move_player_position(game, "east")
        elif selection == "4":
            self._move_player_position(game, "west")
        elif selection == "5":
            return
        else:
            game.io.error_message("Invalid choice.")
    
    def _manage_change_map(self, game, origin_map, destination_map):
        """Handle the state change based on the map change"""
        # If the map change implies a state change
        if (self.origin_state is not None and 
            hasattr(self.origin_state, '__class__') and
            self.origin_state.__class__.__name__ == "TavernState" and 
            destination_map == "market"):
            
            # Ask whether to continue exploring the new map
            proceed = game.io.request_input("Do you want to continue exploring the map? (y/n): ").lower()
            if proceed != "y":
                # Exit the map state
                if game.current_state():
                    game.pop_state()
                # Go directly to the market state
                from states.market import MarketState
                game.push_state(MarketState(game))
                
        elif (self.origin_state is not None and 
              hasattr(self.origin_state, '__class__') and 
              self.origin_state.__class__.__name__ == "MarketState" and 
              destination_map == "tavern"):
              
            # Ask whether to continue exploring the new map
            proceed = game.io.request_input("Do you want to continue exploring the map? (y/n): ").lower()
            if proceed != "y":
                # Exit the map state and the market state
                if game.current_state():
                    game.pop_state()  # Removes MapState
                if game.current_state():
                    game.pop_state()  # Removes MarketState
    
    def _interact_environment(self, game):
        """Allow the player to interact with the surrounding environment"""
        game.io.show_message("\n=== INTERACTION ===")
        game.io.show_message("1. Interact with a nearby object")
        game.io.show_message("2. Talk to a nearby character")
        game.io.show_message("3. Examine the area")
        game.io.show_message("4. Go back")
        
        selection = game.io.request_input("\nChoose: ")
        
        if selection == "1":
            if game.player.interact_with_adjacent_item(game.map_manager, game):
                pass  # The interaction is already handled in the method
            else:
                game.io.show_message("There are no objects to interact with nearby.")
        elif selection == "2":
            if game.player.interact_with_adjacent_npc(game.map_manager, game):
                pass  # The interaction is already handled in the method
            else:
                game.io.show_message("There are no characters to talk to nearby.")
        elif selection == "3":
            self._examine_area(game)
        elif selection == "4":
            return
        else:
            game.io.error_message("Invalid choice.")
    
    def _examine_area(self, game):
        """Examine the area to find objects or characters"""
        game.io.show_message("You carefully examine the surrounding area...")
        
        # A mechanic for discovering hidden objects could be implemented here
        nearby_items = game.player.get_nearby_items(game.map_manager, 2)
        nearby_npcs = game.player.get_nearby_npcs(game.map_manager, 2)
        
        if nearby_items or nearby_npcs:
            game.io.show_message("You notice some interesting things:")
            
            if nearby_items:
                game.io.show_message("\nObjects:")
                for pos, obj in nearby_items.items():
                    x, y = pos
                    game.io.show_message(f"- {obj.name} at ({x}, {y}) from you")
            
            if nearby_npcs:
                game.io.show_message("\nCharacters:")
                for pos, npc in nearby_npcs.items():
                    x, y = pos
                    game.io.show_message(f"- {npc.name} at ({x}, {y}) from you")
        else:
            game.io.show_message("You notice nothing out of the ordinary.")
    
    def _nearby_show_elements(self, game):
        """Show nearby objects and NPCs"""
        nearby_items = game.player.get_nearby_items(game.map_manager)
        nearby_npcs = game.player.get_nearby_npcs(game.map_manager)
        
        if not nearby_items and not nearby_npcs:
            game.io.show_message("There are no elements nearby.")
            return
            
        game.io.show_message("\n=== NEARBY ELEMENTS ===")
        
        if nearby_items:
            game.io.show_message("\nItems:")
            for pos, obj in nearby_items.items():
                x, y = pos
                game.io.show_message(f"- {obj.name} [{obj.state}] at ({x}, {y})")
        
        if nearby_npcs:
            game.io.show_message("\nPersonaggi:")
            for pos, npc in nearby_npcs.items():
                x, y = pos
                game.io.show_message(f"- {npc.name} at ({x}, {y})")

    def save_map_state(self, game):
        """Save the current state of the map"""
        # Implementation for saving

    def _move_player_position(self, game, direction):
        """
        Move the player in the specified direction
        
        Args:
            game: Game object
            direction: String with the direction (north, south, east, west)
        """
        # Get the offset from the direction
        dx, dy = self.directions[direction]
        
        # Current map before the movement
        previous_map = game.player.current_map
        
        # Try to move the player
        if game.player.move(dx, dy, game.map_manager):
            game.io.show_message(f"You moved toward {direction}")
            
            # Check whether there is a door to change maps
            map = game.map_manager.get_map(game.player.current_map)
            
            # If the map changed after the movement
            if previous_map != game.player.current_map:
                game.io.show_message(f"You passed through a door to {game.player.current_map}!")
                
                # State handling based on the map change
                self._manage_change_map(game, previous_map, game.player.current_map)
        else:
            game.io.error_message("You cannot move in that direction!")
            
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
            "show_legend": self.show_legend
        })
        
        # Save the origin state if present
        if self.origin_state and hasattr(self.origin_state, "__class__"):
            data["origin_state_type"] = self.origin_state.__class__.__name__
        
        return data

    @classmethod
    def from_dict(cls, data):
        """
        Create an instance of MapState from a dictionary.
        
        Args:
            data (dict): Dictionary with the state data
            
        Returns:
            MapState: New instance of the state
        """
        state = cls()
        
        # Restore attributes
        state.show_legend = data.get("show_legend", True)
        
        # Note: origin_state will be handled after the complete loading
        # of the state stack, since it might require circular references
        
        return state
