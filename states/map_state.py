from states.base_state import BaseState
from states.commands import handle_targeted_command, parse_targeted_command
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
        self.phase = "main_menu"
        
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

        if self.phase == "move":
            self._move_player(game)
        elif self.phase == "interact":
            self._interact_environment(game)
        else:
            self._main_menu(game)

    def _main_menu(self, game):
        current_map = game.map_manager.get_map(game.player.current_map)
        map_name = game.player.current_map.upper()

        game.io.show_message(f"\n=== MAP OF {map_name} ===")
        game.io.show_map(
            current_map.generate_ascii_representation(
                (game.player.x, game.player.y)
            )
        )

        if self.show_legend:
            self._show_legend(game, current_map)

        game.io.show_message(f"\nCurrent position: ({game.player.x}, {game.player.y})")
        game.io.show_message("\nWhat do you want to do?")
        game.io.show_message("1. Move")
        game.io.show_message("2. Interact with the environment")
        game.io.show_message("3. Show nearby elements")
        game.io.show_message("4. Show/hide legend")
        game.io.show_message("5. Go back")

        selection = str(game.io.request_input("\nChoice: ") or "").strip()
        low = selection.casefold()

        if not selection.isdigit():
            parts = low.split()
            direction = None
            if len(parts) == 1 and parts[0] in self.directions:
                direction = parts[0]
            elif (
                len(parts) == 2
                and parts[0] in {"move", "go", "walk", "head"}
                and parts[1] in self.directions
            ):
                direction = parts[1]

            if direction is not None:
                self._move_player_position(game, direction)
                self.phase = "main_menu"
                press_enter(game)
                return

            targeted = parse_targeted_command(selection)
            if targeted is not None:
                action, target = targeted
                if handle_targeted_command(game, action, target):
                    self.phase = "main_menu"
                    return
                # Unresolved target: stay on the map and show the menu again.
                self.phase = "main_menu"
                press_enter(game)
                return

        if selection == "1":
            self.phase = "move"
            return
        if selection == "2":
            self.phase = "interact"
            return
        if selection == "3":
            self._nearby_show_elements(game)
            self.phase = "main_menu"
            press_enter(game)
            return
        if selection == "4":
            self.show_legend = not self.show_legend
            game.io.system_message(
                "Legend " + ("activated" if self.show_legend else "deactivated")
            )
            self.phase = "main_menu"
            press_enter(game)
            return
        if selection == "5":
            if game.current_state():
                game.pop_state()
            return

        game.io.error_message("Invalid choice.")
        self.phase = "main_menu"
        press_enter(game)
    
    def _show_legend(self, game, current_map=None):
        game.io.show_message("\nLegend:")
        game.io.show_message("P = Player")
        game.io.show_message("# = Wall")
        game.io.show_message(". = Empty space")

        if current_map is not None:
            for entry in current_map.token_legend():
                names = ", ".join(
                    name[:1].upper() + name[1:] for name in entry["names"]
                )
                game.io.show_message(f"{entry['token']} = {names}")
    
    def _move_player(self, game):
        """Handle the player's movement on the map"""
        game.io.show_message("\n=== MOVEMENT ===")
        game.io.show_message("1. North")
        game.io.show_message("2. South")
        game.io.show_message("3. East")
        game.io.show_message("4. West")
        game.io.show_message("5. Back")

        selection = str(
            game.io.request_input("\nChoose a direction: ") or ""
        ).strip().casefold()

        mapping = {
            "1": "north",
            "north": "north",
            "n": "north",
            "2": "south",
            "south": "south",
            "s": "south",
            "3": "east",
            "east": "east",
            "e": "east",
            "4": "west",
            "west": "west",
            "w": "west",
        }

        if selection in mapping:
            self._move_player_position(game, mapping[selection])
        elif selection not in {"5", "back"}:
            game.io.error_message("Invalid choice.")

        self.phase = "main_menu"
        press_enter(game)
    
    def _manage_change_map(self, game, origin_map, destination_map):
        """Handle the state change based on the map change"""
        # Web sessions do not need the extra y/n pause; stay in MapState on
        # the destination map and let the player continue.
        if not getattr(game.io, "pause_for_confirmation", True):
            return

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

        selection = str(game.io.request_input("\nChoose: ") or "").strip()

        if selection == "1":
            if not game.player.interact_with_adjacent_item(game.map_manager, game):
                game.io.show_message("There are no objects to interact with nearby.")
        elif selection == "2":
            if not game.player.interact_with_adjacent_npc(game.map_manager, game):
                game.io.show_message("There are no characters to talk to nearby.")
        elif selection == "3":
            self._examine_area(game)
        elif selection != "4":
            game.io.error_message("Invalid choice.")

        self.phase = "main_menu"
        press_enter(game)
    
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
            "show_legend": self.show_legend,
            "phase": self.phase,
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
        state.phase = data.get("phase", "main_menu")
        
        # Note: origin_state will be handled after the complete loading
        # of the state stack, since it might require circular references
        
        return state
