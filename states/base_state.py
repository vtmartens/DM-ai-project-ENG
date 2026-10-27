class BaseState:
    """
    Base class for all game states.
    Every specific state must inherit from this class and implement the run() method.
    """
    def __init__(self):
        """Initialize the base state"""
        # Game context
        self.game = None
        
    def set_game_context(self, game):
        """
        Set the game context for this state.
        
        Args:
            game: The game instance
        """
        self.game = game
    
    def run(self, game=None):
        """
        Main method called when the state is active.
        Must be implemented by every child class.
        
        Args:
            game: The game instance containing the current state and the player
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx:
            raise ValueError("Game context not available. Use set_game_context() before running.")
            
        raise NotImplementedError("Every state must implement run()")
    
    def enter(self, game=None):
        """
        Method called when entering the state.
        Can be overridden to initialize the state.
        
        Args:
            game: The game instance
        """
        # Store the context if provided
        if game:
            self.set_game_context(game)
    
    def exit(self, game=None):
        """
        Method called when exiting the state.
        Can be overridden to clean up or save data.
        
        Args:
            game: The game instance
        """
        pass

    def pause(self, game=None):
        """
        Method called when the state is temporarily suspended
        because a new state is pushed on top of it.
        Can be overridden to handle the temporary suspension.
        
        Args:
            game: The game instance
        """
        pass

    def resume(self, game=None):
        """
        Method called when the state becomes active again
        after being paused.
        Can be overridden to handle the resumption of the state.
        
        Args:
            game: The game instance
        """
        pass
        
    # Utility methods for maps
    
    def get_current_map(self, game=None):
        """
        Get the current map where the player is located.
        
        Args:
            game: The game instance (optional if the context is already stored)
            
        Returns:
            Map: The current map object, or None if not available
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx or not game_ctx.player.current_map:
            return None
            
        return game_ctx.map_manager.get_map(game_ctx.player.current_map)
    
    def get_nearby_items(self, game=None, radius=1):
        """
        Get the items near the player within a certain radius.
        
        Args:
            game: The game instance (optional if the context is already stored)
            radius (int): Search radius
            
        Returns:
            dict: Dictionary of nearby items, or an empty dict if not available
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx or not game_ctx.player.current_map:
            return {}
            
        return game_ctx.player.get_nearby_items(game_ctx.map_manager, radius)
    
    def get_nearby_npcs(self, game=None, radius=1):
        """
        Get the NPCs near the player within a certain radius.
        
        Args:
            game: The game instance (optional if the context is already stored)
            radius (int): Search radius
            
        Returns:
            dict: Dictionary of nearby NPCs, or an empty dict if not available
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx or not game_ctx.player.current_map:
            return {}
            
        return game_ctx.player.get_nearby_npcs(game_ctx.map_manager, radius)
    
    def move_player(self, direction, game=None):
        """
        Move the player in a direction.
        
        Args:
            direction (str): One of the directions "north", "south", "east", "west"
            game: The game instance (optional if the context is already stored)
            
        Returns:
            bool: True if the movement happened, False otherwise
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx:
            return False
            
        return game_ctx.move_player(direction)
    
    def interact_with_adjacent_item(self, game=None):
        """
        Make the player interact with an adjacent object.
        
        Args:
            game: The game instance (optional if the context is already stored)
            
        Returns:
            bool: True if the interaction happened, False otherwise
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx or not game_ctx.player.current_map:
            return False
            
        return game_ctx.player.interact_with_adjacent_item(game_ctx.map_manager, game_ctx)
    
    def interact_with_adjacent_npc(self, game=None):
        """
        Make the player interact with an adjacent NPC.
        
        Args:
            game: The game instance (optional if the context is already stored)
            
        Returns:
            bool: True if the interaction happened, False otherwise
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx or not game_ctx.player.current_map:
            return False
            
        return game_ctx.player.interact_with_adjacent_npc(game_ctx.map_manager, game_ctx)
    
    def display_map(self, game=None):
        """
        Display the current map.
        
        Args:
            game: The game instance (optional if the context is already stored)
            
        Returns:
            str: ASCII representation of the map, or None if not available
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx:
            return None
            
        map = self.get_current_map(game_ctx)
        if map:
            return map.generate_ascii_representation((game_ctx.player.x, game_ctx.player.y))
        return None
    
    def change_map(self, map_dest, x=None, y=None, game=None):
        """
        Change the player's current map.
        
        Args:
            map_dest (str): Name of the destination map
            x, y (int, optional): Destination coordinates
            game: The game instance (optional if the context is already stored)
            
        Returns:
            bool: True if the map change happened, False otherwise
        """
        # Use the stored context if available
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx:
            return False
            
        return game_ctx.change_map(map_dest, x, y)

    def to_dict(self):
        """
        Convert the state into a dictionary for serialization.
        Automatically saves the base attributes and allows extension in subclasses.
        
        Returns:
            dict: Dictionary representation of the state
        """
        # Save the state type for reconstruction
        data = {
            "type": self.__class__.__name__
        }
        
        # Automatically add all serializable attributes
        for attr_name, attr_value in self.__dict__.items():
            # Ignore private attributes or functions
            if attr_name.startswith('_') or callable(attr_value):
                continue
                
            # Handle serializable base types
            if isinstance(attr_value, (str, int, float, bool, type(None))):
                data[attr_name] = attr_value
            # Handle objects with to_dict()
            elif hasattr(attr_value, 'to_dict') and callable(getattr(attr_value, 'to_dict')):
                try:
                    data[attr_name] = attr_value.to_dict()
                except:
                    # If to_dict() fails, ignore this attribute
                    pass
            # Handle lists of objects
            elif isinstance(attr_value, list):
                serialized_list = []
                try:
                    for item in attr_value:
                        if hasattr(item, 'to_dict') and callable(getattr(item, 'to_dict')):
                            serialized_list.append(item.to_dict())
                        elif isinstance(item, (str, int, float, bool, type(None))):
                            serialized_list.append(item)
                        # Ignore elements that cannot be serialized
                    if serialized_list:  # Add only if the list is not empty
                        data[attr_name] = serialized_list
                except:
                    # If there is a serialization error, ignore this attribute
                    pass
            # Handle dictionaries of objects
            elif isinstance(attr_value, dict):
                serialized_dict = {}
                try:
                    for key, value in attr_value.items():
                        # Convert the key to a string to ensure JSON compatibility
                        str_key = str(key)
                        if hasattr(value, 'to_dict') and callable(getattr(value, 'to_dict')):
                            serialized_dict[str_key] = value.to_dict()
                        elif isinstance(value, (str, int, float, bool, type(None))):
                            serialized_dict[str_key] = value
                        # Ignore values that cannot be serialized
                    if serialized_dict:  # Add only if the dict is not empty
                        data[attr_name] = serialized_dict
                except:
                    # If there is a serialization error, ignore this attribute
                    pass
            # Handle tuples (converting them to lists)
            elif isinstance(attr_value, tuple):
                try:
                    data[attr_name] = list(attr_value)
                except:
                    pass
        
        return data
        
    @classmethod
    def from_dict(cls, data):
        """
        Create a state instance from a dictionary.
        
        Args:
            data (dict): Dictionary with the state data
            
        Returns:
            BaseState: New state instance, or base instance in case of error
        """
        # If there is a specific type, create the appropriate instance
        state_type = data.get("type")
        if state_type != cls.__name__:
            # Dynamic import of the correct state
            import importlib
            import traceback
            
            try:
                # Search in all states modules
                # Fix: explicit mapping of class names to modules
                state_module_map = {
                    "TavernState": "tavern",
                    "MarketState": "market",
                    "WaystationState": "waystation",
                    "BountyBoardState": "bounty_board",
                    "CombatState": "combat",
                    "DialogueState": "dialogue",
                    "InventoryManagementState": "inventory_management",
                    "AbilityCheckState": "ability_check",
                    "MapState": "map_state",
                    "MapSelectionState": "map_selection_state",
                    "MenuState": "menu"
                }
                
                # Use the mapping if available, otherwise fall back to the lowercase name
                module_suffix = state_module_map.get(state_type, state_type.lower())
                module_name = f"states.{module_suffix}"
                
                module = importlib.import_module(module_name)
                state_class = getattr(module, state_type)
                
                # Create the instance using the class's from_dict method
                if hasattr(state_class, 'from_dict'):
                    return state_class.from_dict(data)
                else:
                    # If it has no from_dict method, create a default instance
                    return state_class()
            except (ImportError, AttributeError) as e:
                # Log the error for debugging
                print(f"Error while loading state {state_type}: {e}")
                print(traceback.format_exc())
                # Fall back to a base instance instead of None
                return cls()
            except Exception as e:
                # Catch any other unexpected error
                print(f"Unexpected error while loading state: {e}")
                print(traceback.format_exc())
                return cls()
        
        # Base instance
        return cls()

class BaseGameState(BaseState):
    """
    Base class for game states that require advanced functionality.
    Extends BaseState by adding game-specific functionality.
    """
    def __init__(self, game=None):
        """
        Initialize the base game state.
        
        Args:
            game: The game instance (optional)
        """
        super().__init__()
        if game:
            self.set_game_context(game)
        
        # Attributes specific to the game state
        self.state_name = "base_game_state"
        self.is_active = False
        self.last_action = None
        
    def _init_commands(self):
        """
        Method to initialize the state's commands and mappings.
        This is an empty base implementation that subclasses can override.
        """
        # Empty base implementation
        pass
        
    def enter(self, game=None):
        """
        Method called when entering the game state.
        
        Args:
            game: The game instance (optional)
        """
        super().enter(game)
        self.is_active = True
        
    def exit(self, game=None):
        """
        Method called when exiting the game state.
        
        Args:
            game: The game instance (optional)
        """
        super().exit(game)
        self.is_active = False
        
    def run(self, game=None):
        """
        Main method called when the state is active.
        Base implementation that can be overridden by child classes.
        
        Args:
            game: The game instance containing the current state and the player
        """
        game_ctx = game if game else getattr(self, 'game', None)
        if not game_ctx:
            raise ValueError("Game context not available for BaseGameState")
        
        # Base implementation
        game_ctx.io.show_message(f"State {self.state_name} active.")
        
    def to_dict(self):
        """
        Convert the state into a dictionary for serialization.
        
        Returns:
            dict: Dictionary representation of the state
        """
        # Base dictionary containing the state information
        return {
            "type": self.__class__.__name__,
            "state_name": self.state_name
        }
        
    @classmethod
    def from_dict(cls, data, game=None):
        """
        Create a state instance from a dictionary.
        Base implementation; subclasses should extend it.
        
        Args:
            data (dict): Dictionary with the state data
            game: Game instance (optional)
            
        Returns:
            BaseGameState: New instance of the state
        """
        if game is not None:
            state = cls(game)
        else:
            # Create an object without calling __init__ to avoid errors
            state = object.__new__(cls)
            state.game = None  # It will be set later
            state.state_name = data.get("state_name", "unknown")
            
        return state