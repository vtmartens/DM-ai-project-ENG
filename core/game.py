from world.map_manager import MapManager
from core.io_interface import TerminalIO
import json
import ast  # Import ast for literal_eval


class Game:
    def __init__(self, player, initial_state, io_handler, temporary=False):
        """
        Initializes the game with a player and an initial state

        Args:
            player: The player object
            initial_state: The initial state of the game
            io_handler: Mandatory input/output handler
            temporary: If True, indicates this is a temporary instance for loading only
        """
        self.player = player
        self.state_stack = []  # State stack
        self.active = True
        self.io = io_handler

        # Give the player a game context so event hooks (achievements) can emit
        # messages even when they are called from managers that lack one.
        if self.player is not None and hasattr(self.player, "set_game_context"):
            self.player.set_game_context(self)

        # Initialize the map manager
        self.map_manager = MapManager()

        # Set the player's initial map (tavern by default)
        # Only if the player has already been created
        if self.player is not None:
            self.set_initial_map()

        # Do not add the initial state if it is None or if this is a temporary instance
        if initial_state is not None and not temporary:
            self.push_state(initial_state)

    def set_initial_map(self, map_key=None):
        """
        Sets the initial map for the player

        Args:
            map_key (str, optional): Name of the initial map. If None, sets no map.
        """
        if map_key is None:
            # We do not set a default map, we leave the choice to the player
            return True
            
        map = self.map_manager.get_map(map_key)
        if map:
            self.map_manager.set_current_map(map_key)
            x, y = map.player_start_position
            self.player.set_position(map_key, x, y)
            from core.achievements import record_event

            record_event(self.player, "area_visited", game=self, map=map_key)
            return True
        return False

    def change_map(self, map_key, x=None, y=None):
        """
        Changes the player's current map

        Args:
            map_key (str): Name of the destination map
            x (int, optional): Destination X position
            y (int, optional): Destination Y position

        Returns:
            bool: True if the map change happened, False otherwise
        """
        return self.map_manager.change_player_map(self.player, map_key, x, y)

    def current_state(self):
        """
        Safely returns the current state

        Returns:
            The current state or None if the stack is empty
        """
        try:
            return self.state_stack[-1] if self.state_stack else None
        except IndexError:
            return None

    def _restore_quest_items(self):
        """Grants or upgrades quest items that older saves may predate."""
        player = getattr(self, "player", None)
        if player is None:
            return

        quest_ids = {
            quest.get("id")
            for quest in (
                list(getattr(player, "active_quests", []))
                + list(getattr(player, "completed_quests", []))
            )
            if isinstance(quest, dict)
        }
        if "shadows_of_the_market" not in quest_ids:
            return

        from items.item import Item

        key = next(
            (
                item
                for item in getattr(player, "inventory", [])
                if getattr(item, "name", item) == "Warehouse Key"
            ),
            None,
        )
        if key is None or not hasattr(key, "effect"):
            key = Item(
                "Warehouse Key",
                "key",
                {"opens": ["Warehouse Door", "Sealed Strongbox"]},
                25,
                "An iron key taken from one of the hooded figures",
            )
            player.add_item(key)

        effect = getattr(key, "effect", None)
        if not isinstance(effect, dict):
            effect = {}
            key.effect = effect
        opens = effect.setdefault("opens", [])
        if not isinstance(opens, list):
            opens = [opens]
            effect["opens"] = opens
        for target in ("Warehouse Door", "Sealed Strongbox"):
            if target not in opens:
                opens.append(target)

    def push_state(self, new_state):
        """
        Pushes a new state on top of the current one

        Args:
            new_state: The new state to add
        """
        try:
            # Check that the state is not None
            if new_state is None:
                self.io.show_message("Error: attempt to push a null state.")
                return

            # Set the game context on the state before using it
            if hasattr(new_state, 'set_game_context'):
                new_state.set_game_context(self)

            if self.current_state():
                self.current_state().pause(self)  # Pause the current state
            self.state_stack.append(new_state)
            new_state.enter(self)
        except Exception as e:
            self.io.show_message(f"Error while pushing the state: {e}")
            self.active = False

    def pop_state(self):
        """
        Removes the current state and returns to the previous one
        """
        try:
            if not self.state_stack:
                self.io.show_message("No state to remove.")
                return

            current_state = self.state_stack[-1]
            if current_state is None:
                # Remove the null state without calling methods on it
                self.io.show_message("Removing an invalid state.")
                self.state_stack.pop()
            else:
                # Proceed normally
                current_state.exit(self)
                self.state_stack.pop()
                
            # Resume the previous state if it exists
            if self.current_state():
                if self.current_state() is not None:
                    # Make sure the state has the correct game context
                    if hasattr(self.current_state(), 'set_game_context'):
                        self.current_state().set_game_context(self)
                    self.current_state().resume(self)
                else:
                    # Also remove this state if it is None
                    self.io.show_message("Invalid previous state, it will be removed.")
                    self.state_stack.pop()

            # If there are no more states, terminate the game
            if not self.state_stack:
                self.active = False  # No state left
        except Exception as e:
            self.io.show_message(f"Error while popping the state: {e}")
            # On a critical error, remove the state anyway
            if self.state_stack:
                self.state_stack.pop()
            if not self.state_stack:
                self.active = False

    def reset_to_state(self, new_state):
        """Clears the state stack and enters a fresh state.

        Used for recovery transitions (for example after a defeat) where the
        previous map or combat state should not remain underneath.
        """
        for state in reversed(self.state_stack):
            if state is not None:
                state.exit(self)
        self.state_stack.clear()
        self.active = True
        self.push_state(new_state)

    def change_state(self, new_state):
        """
        Replaces the current state with a new one

        Args:
            new_state: The new state that will replace the current one
        """
        try:
            # Set the game context on the state before using it
            if hasattr(new_state, 'set_game_context'):
                new_state.set_game_context(self)

            if self.current_state():
                self.current_state().exit(self)
                self.state_stack.pop()
            self.state_stack.append(new_state)
            new_state.enter(self)
        except Exception as e:
            self.io.show_message(f"Error while changing state: {e}")
            self.active = False

    def run(self):
        """
        Runs the main game loop
        """
        self.active = True  # Make sure the game is active at the start

        while self.active:
            # Check that there is at least one state on the stack
            if not self.current_state():
                self.io.show_message("No active state. The game will terminate.")
                break

            try:
                # Run the current state
                self.current_state().run(self)
                # Emit buffered output (AI narration, when enabled)
                self.io.flush()
            except Exception as e:
                self.io.show_message(f"Error while running the state: {e}")
                import traceback
                self.io.show_message(traceback.format_exc())
                self.pop_state()  # Automatic error handling

                # If there are no more states, terminate the game
                if not self.state_stack:
                    self.active = False

    def terminate(self):
        """
        Terminates the game cleanly
        """
        while self.state_stack:
            self.pop_state()
            
        self.active = False

    def unlock_area(self, area_id):
        """
        Handles unlocking an area in the world.

        Args:
            area_id (str): Identifier of the area to unlock
        """
        self.io.show_message(f"The area {area_id} has been unlocked!")
        # Logic to unlock the area

        # If the area is a map, we can activate it
        if area_id in self.map_manager.maps:
            self.io.show_message(f"The map {area_id} is now accessible!")
        
    def activate_trap(self, trap_id, damage=0):
        """
        Activates a trap in the world.

        Args:
            trap_id (str): Identifier of the trap
            damage (int): Amount of damage to deal
        """
        self.io.show_message(f"A trap is triggered!")
        if damage > 0:
            self.player.take_damage(damage)
        
    def modify_environment(self, environment_id, new_state):
        """
        Modifies an environment in the world.

        Args:
            environment_id (str): Identifier of the environment
            new_state (str): New state of the environment
        """
        self.io.show_message(f"The environment {environment_id} changes: {new_state}")
        # Logic to modify the environment

    def get_player_position(self):
        """
        Returns information about the player's current position

        Returns:
            dict: Information about the current position
        """
        if not self.player.current_map:
            return None
            
        map = self.map_manager.get_map(self.player.current_map)
        if not map:
            return None
            
        return {
            "map": self.player.current_map,
            "x": self.player.x,
            "y": self.player.y,
            "nearby_items": self.player.get_nearby_items(self.map_manager),
            "nearby_npcs": self.player.get_nearby_npcs(self.map_manager)
        }
        
    def move_player(self, direction):
        """
        Moves the player in a specific direction

        Args:
            direction (str): One of the directions "north", "south", "east", "west"

        Returns:
            bool: True if the movement happened, False otherwise
        """
        directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0)
        }
        
        if direction not in directions:
            return False
            
        dx, dy = directions[direction]
        movement = self.player.move(dx, dy, self.map_manager)
        
        if not movement:
            self.io.show_message("You cannot move in that direction!")
            
        return movement

    def save(self, file_path="save.json"):
        """
        Saves the current game state to a JSON file

        Args:
            file_path (str): Path of the save file

        Returns:
            bool: True if the save succeeded, False otherwise
        """
        try:
            # Import the configuration module
            from util.config import get_save_path, create_backup, SAVE_FORMAT_VERSION
            import logging
            import json

            logger = logging.getLogger("game_rpg")

            # Convert the path using the configuration module
            save_path = get_save_path(file_path)

            # Create a backup if the file already exists
            if save_path.exists():
                backup_path = create_backup(save_path)
                if backup_path:
                    logger.info(f"Created backup of the previous save: {backup_path}")

            # Get the player's serializable data
            if hasattr(self.player, 'to_dict'):
                player_data = self.player.to_dict()
            else:
                # Fallback to the basic save
                inventory_data = []
                for item in self.player.inventory:
                    if hasattr(item, 'to_dict') and callable(getattr(item, 'to_dict')):
                        inventory_data.append(item.to_dict())
                    else:
                        # Save all the object's attributes
                        item_data = {
                            "name": getattr(item, 'name', 'Unknown object'),
                            "type": getattr(item, 'type', 'misc'),
                            "description": getattr(item, 'description', ''),
                            "value": getattr(item, 'value', 0),
                            "effect": getattr(item, 'effect', {}),
                        }
                        inventory_data.append(item_data)
                        
                # Serialize equipped weapon
                weapon_data = None
                if hasattr(self.player, 'weapon') and self.player.weapon:
                    if hasattr(self.player.weapon, 'to_dict'):
                        weapon_data = self.player.weapon.to_dict()
                    else:
                        weapon_data = {
                            "name": getattr(self.player.weapon, 'name', 'Unknown weapon'),
                            "type": "weapon",
                            "description": getattr(self.player.weapon, 'description', ''),
                            "value": getattr(self.player.weapon, 'value', 0),
                            "effect": getattr(self.player.weapon, 'effect', {}),
                        }
                
                # Serialize equipped armor
                armor_data = None
                if hasattr(self.player, 'armor') and self.player.armor:
                    if hasattr(self.player.armor, 'to_dict'):
                        armor_data = self.player.armor.to_dict()
                    else:
                        armor_data = {
                            "name": getattr(self.player.armor, 'name', 'Unknown armor'),
                            "type": "armor",
                            "description": getattr(self.player.armor, 'description', ''),
                            "value": getattr(self.player.armor, 'value', 0),
                            "effect": getattr(self.player.armor, 'effect', {}),
                        }
                        
                # Serialize accessories
                accessories_data = []
                if hasattr(self.player, 'accessories'):
                    for acc in self.player.accessories:
                        if hasattr(acc, 'to_dict'):
                            accessories_data.append(acc.to_dict())
                        else:
                            acc_data = {
                                "name": getattr(acc, 'name', 'Unknown accessory'),
                                "type": "accessory",
                                "description": getattr(acc, 'description', ''),
                                "value": getattr(acc, 'value', 0),
                                "effect": getattr(acc, 'effect', {}),
                            }
                            accessories_data.append(acc_data)
                        
                player_data = {
                    "name": self.player.name,
                    "char_class": self.player.char_class,
                    "hp": self.player.hp,
                    "hp_max": getattr(self.player, 'hp_max', self.player.hp),
                    "map": self.player.current_map,
                    "position": [self.player.x, self.player.y],
                    "gold": getattr(self.player, 'gold', 0),
                    "inventory": inventory_data,
                    "weapon": weapon_data,
                    "armor": armor_data,
                    "accessories": accessories_data,
                    "strength_base": getattr(self.player, 'strength_base', 10),
                    "dexterity_base": getattr(self.player, 'dexterity_base', 10),
                    "constitution_base": getattr(self.player, 'constitution_base', 10),
                    "intelligence_base": getattr(self.player, 'intelligence_base', 10),
                    "wisdom_base": getattr(self.player, 'wisdom_base', 10),
                    "charisma_base": getattr(self.player, 'charisma_base', 10),
                    "level": getattr(self.player, 'level', 1),
                    "experience": getattr(self.player, 'experience', 0),
                }
                
            # Serialize the state stack
            states_data = []
            for state in self.state_stack:
                if hasattr(state, 'to_dict'):
                    states_data.append(state.to_dict())
                else:
                    # Fallback for states that have no to_dict
                    states_data.append({"type": state.__class__.__name__})
            
            # Compose the complete dictionary
            data = {
                "player": player_data,
                "states": states_data,
                "active": self.active,
                "current_map": self.player.current_map,
                "game_version": SAVE_FORMAT_VERSION,  # Use the version from the config module
                "timestamp": __import__('time').time(),  # When the save was made
                "maps": self.map_manager.to_dict()  # Save the complete state of the maps
            }

            # Add all NPCs map by map
            data["npc"] = {
                map_name: {
                    str(position): npc.to_dict() for position, npc in map.npc.items()
                }
                for map_name, map in self.map_manager.maps.items()
            }
            
            # Serialize and save to file
            save_path.parent.mkdir(exist_ok=True, parents=True)  # Ensure the directory exists
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            logger.info(f"Save completed: {save_path}")
            return True

        except Exception as e:
            import traceback
            logging.getLogger("game_rpg").error(f"Error while saving: {e}")
            logging.getLogger("game_rpg").error(traceback.format_exc())
            return False
    
    def load(self, file_path="save.json"):
        """
        Loads a game state from a JSON file

        Args:
            file_path (str): Path of the save file

        Returns:
            bool: True if the load succeeded, False otherwise
        """
        try:
            # Import modules
            from util.config import get_save_path, validate_save_data, migrate_save_data
            import logging
            import json

            logger = logging.getLogger("game_rpg")
            save_path = get_save_path(file_path)

            # Check that the file exists
            if not save_path.exists():
                logger.error(f"Save file not found: {save_path}")
                self.io.show_message(f"Save file not found: {save_path}")
                return False

            # Load and validate data
            try:
                with open(save_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid save file (bad JSON): {e}")
                self.io.show_message("Corrupted save file")
                return False

            # Validate the loaded data
            valid, message = validate_save_data(data)
            if not valid:
                logger.error(message)
                self.io.show_message(message)
                return False
                
            # Migrate data if necessary
            data = migrate_save_data(data)

            # Registry for already loaded objects (avoids circular references)
            # To be used only with classes that support the parameter
            loaded_objects = {}

            # Import all state modules
            from entities.player import Player
            from entities.npc import NPC
            from items.item import Item
            from items.interactive_object import InteractiveObject
            
            # Map of state classes to their modules
            mapping_states = {
                "TavernState": "states.tavern",
                "DialogueState": "states.dialogue", 
                "CombatState": "states.combat",
                "MarketState": "states.market",
                "InventoryManagementState": "states.inventory_management",
                "AbilityCheckState": "states.ability_check",
                "MapState": "states.map_state",
                "MapSelectionState": "states.map_selection_state",
                "MenuState": "states.menu"
            }
            
            # Load the player
            try:
                # Use the standard version directly without loaded_objects for the player
                self.player = Player.from_dict(data["player"])
                if hasattr(self.player, "set_game_context"):
                    self.player.set_game_context(self)
                self._restore_quest_items()
            except KeyError:
                logger.error("Missing or incomplete player data in the save file")
                self.io.show_message("Missing or incomplete player data in the save file")
                return False
            except Exception as e:
                logger.error(f"Error creating the player: {str(e)}")
                self.io.show_message(f"Error creating the player: {str(e)}")
                return False

            # Recreate the state stack
            self.state_stack = []
            for state_data in data.get("states", []):
                # Get the type of the state
                state_type = state_data.get("type")
                if not state_type:
                    continue

                # Dynamically import the state class
                try:
                    # Use the mapping to find the correct module
                    if state_type in mapping_states:
                        module_name = mapping_states[state_type]

                        # Dynamically import the module
                        import importlib
                        module = importlib.import_module(module_name)

                        # Get the class by the same name
                        state_class = getattr(module, state_type)

                        # Rebuild the state using from_dict
                        if hasattr(state_class, 'from_dict'):
                            # Just use the standard version
                            state = state_class.from_dict(state_data)
                            self.state_stack.append(state)
                        else:
                            logger.warning(f"State {state_type} has no from_dict method")
                            self.io.show_message(f"Warning: {state_type} has no from_dict method")
                    else:
                        logger.warning(f"No mapping found for {state_type}")
                        self.io.show_message(f"Warning: no mapping found for {state_type}")
                except Exception as e:
                    logger.error(f"Error loading state {state_type}: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue

            # Load maps and interactive objects if present
            if "maps" in data:
                try:
                    self.map_manager.from_dict(data["maps"])
                    logger.info("Game world loaded successfully!")
                except Exception as e:
                    logger.error(f"Error loading maps: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                # Compatibility with old saves - recreate NPCs in the maps
                for map_key, npcs in data.get("npc", {}).items():
                    map = self.map_manager.get_map(map_key)
                    if map:
                        for pos_str, npc_data in npcs.items():
                            try:
                                import ast
                                pos = ast.literal_eval(pos_str)
                                npc = NPC.from_dict(npc_data)
                                map.npc[pos] = npc
                            except Exception as e:
                                logger.error(f"Error loading NPC at position {pos_str}: {str(e)}")

            # Set the current map
            current_map = data.get("current_map", "tavern")
            self.map_manager.set_current_map(current_map)

            # Set the active state
            self.active = data.get("active", True)

            # Clean up old backups
            from util.config import clean_old_backups
            clean_old_backups()

            logger.info(f"Game for {self.player.name} loaded successfully!")
            self.io.show_message(f"Game for {self.player.name} loaded successfully!")
            return True

        except Exception as e:
            import traceback
            logging.getLogger("game_rpg").error(f"Error while loading: {e}")
            logging.getLogger("game_rpg").error(traceback.format_exc())
            self.io.show_message(f"Error while loading: {e}")
            return False
