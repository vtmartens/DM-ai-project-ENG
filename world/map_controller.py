from world.map import Map
from world.map_manager import MapManager
from entities.player import Player
import random

class MapController:
    def __init__(self, width=80, height=60, cell_size=1):
        """
        Initializes the controller that handles the interaction between the
        interface and the game logic.

        Args:
            width (int): Width of the map in cells
            height (int): Height of the map in cells
            cell_size (int): Size of a cell (for compatibility, not used)
        """
        self.width = width
        self.height = height
        self.cell_size = cell_size
        
        # Initialize the map manager
        self.map_manager = MapManager()

        # Create a player
        self.player = Player("Adventurer", "Fighter")

        # Set the initial map
        self.player.current_map = "tavern"
        self.map_manager.set_current_map(self.player.current_map)
        self.player.x, self.player.y = self.map_manager.current_map.player_start_position
        
        # Interaction state
        self.interaction_activate = False
        self.selected_item = None
        self.selected_npc = None

    def move_player(self, dx, dy):
        """
        Handles the player's movement on the map.

        Args:
            dx (int): Movement along the X axis
            dy (int): Movement along the Y axis

        Returns:
            bool: True if the movement happened, False otherwise
        """
        return self.player.move(dx, dy, self.map_manager)
    
    def interact(self):
        """
        Handles interaction with the element adjacent to the player.

        Returns:
            tuple: (interaction_type, interaction_object) or (None, None) if interaction is not possible
        """
        map = self.map_manager.get_map(self.player.current_map)
        if not map:
            return None, None
        
        # Check in all adjacent directions
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            x, y = self.player.x + dx, self.player.y + dy
            
            # Check whether there is an object
            item = map.get_item_at(x, y)
            if item:
                self.selected_item = item
                return "item", item
            
            # Check whether there is an NPC
            npc = map.get_npc_at(x, y)
            if npc:
                self.selected_npc = npc
                return "npc", npc
        
        return None, None
    
    def get_map_elements(self):
        """
        Retrieves all the elements present on the current map.

        Returns:
            dict: Dictionary with the elements on the map (walls, objects, npcs)
        """
        if not self.map_manager.current_map:
            return {}
            
        map = self.map_manager.current_map
        
        elements = {
            "walls": [],
            "items": {},
            "npc": {},
            "doors": {}
        }
        
        # Add the walls
        for y in range(map.height):
            for x in range(map.width):
                if map.grid[y][x] == 1:
                    elements["walls"].append((x, y))
        
        # Add objects and NPCs
        elements["items"] = map.items
        elements["npc"] = map.npc
        elements["doors"] = map.doors
        
        return elements
    
    def get_nearby_items(self, radius=1):
        """
        Retrieves the objects near the player.

        Args:
            radius (int): Search radius

        Returns:
            dict: Dictionary with the nearby objects
        """
        return self.player.get_nearby_items(self.map_manager, radius)
    
    def get_nearby_npcs(self, radius=1):
        """
        Retrieves the NPCs near the player.

        Args:
            radius (int): Search radius

        Returns:
            dict: Dictionary with the nearby NPCs
        """
        map = self.map_manager.get_map(self.player.current_map)
        if not map:
            return {}
        
        return map.get_nearby_npcs(self.player.x, self.player.y, radius)
    
    def run_item_interaction(self):
        """
        Performs the interaction with the selected object.

        Returns:
            str: Result of the interaction
        """
        if self.selected_item:
            result = self.selected_item.interact(self.player)
            self.selected_item = None
            return result
        return None
    
    def run_npc_interaction(self):
        """
        Performs the interaction with the selected NPC by showing a dialogue.

        Returns:
            dict: Dialogue data or None
        """
        if not self.selected_npc:
            return None
        
        # Get the dialogue data
        dialogue = self.selected_npc.get_conversation("start")
        
        # Save the current NPC for future reference
        current_npc = self.selected_npc
        self.selected_npc = None
        
        return {
            "npc": current_npc,
            "dialogue": dialogue
        }
    
    def proceed_dialogue(self, npc, dialogue_state):
        """
        Continues an existing dialogue with an NPC.

        Args:
            npc: The NPC to talk to
            dialogue_state: The dialogue state to move to

        Returns:
            dict: New dialogue data or None
        """
        if not dialogue_state:
            return None
        
        # Get the data of the new dialogue state
        dialogue = npc.get_conversation(dialogue_state)
        
        # If there is an effect, apply it
        if dialogue and "effect" in dialogue:
            effect = dialogue["effect"]
            
            # Handle simple effects
            if effect == "rest":
                # Use heal instead of setting hp directly
                heal_quantity = self.player.hp_max - self.player.hp
                if heal_quantity > 0:
                    self.player.heal(heal_quantity, None)  # We pass None as the game, since we have no access to the game object here
                return {"npc": npc, "dialogue": dialogue, "message": "You rested and recovered all your hit points."}
            # Handle item trade effects
            elif isinstance(effect, dict) and effect["type"] == "trade":
                # Simplified implementation
                object_name = effect["item"]
                cost = effect["cost"]
                
                if self.player.gold >= cost:
                    self.player.gold -= cost
                    # The item should be added to the inventory here
                    return {"npc": npc, "dialogue": dialogue, "message": f"You bought {object_name} for {cost} gold coins."}
                else:
                    return {"npc": npc, "dialogue": dialogue, "message": "You do not have enough gold for this!"}
        
        return {"npc": npc, "dialogue": dialogue}
    
    def change_map(self, map_name):
        """
        Changes the current map.

        Args:
            map_name (str): Name of the new map

        Returns:
            bool: True if the change happened, False otherwise
        """
        return self.map_manager.change_player_map(self.player, map_name)

    def transfer_items_from_state(self, map_name, state, game=None):
        """Transfers objects and NPCs from the state to the corresponding map"""
        map = self.map_manager.maps.get(map_name)
        if not map:
            return False

        # Place the interactive objects on the map precisely
        pos_items = {
            "counter": (5, 5),
            "fireplace": (15, 3),
            "hidden_chest": (8, 10),
            "cellar_door": (22, 9),
            "secret_lever": (20, 5),
            "floor_trap": (10, 15),
            "magic_altar": (18, 15)
        }
        
        for key, item in state.interactive_objects.items():
            if key in pos_items:
                x, y = pos_items[key]
                map.add_item(item, x, y)
            else:
                # Alternative placement for objects with no fixed position
                alternative_positions = [(7, 12), (14, 7), (16, 10), (4, 8), (19, 7)]

                for x, y in alternative_positions:
                    # Check whether the position is valid and free
                    if map.is_valid_position(x, y) and (x, y) not in map.items and (x, y) not in map.npc:
                        map.add_item(item, x, y)
                        break
        
        # Place NPCs at precise positions
        pos_npc = {
            "Durnan": (6, 6),
            "Elminster": (9, 9),
            "Mirt": (7, 7)  # Changed from (12, 12) to (7, 7) to make it more visible
        }
        
        # Alternative positions in case the main ones are occupied
        pos_npc_alternative = {
            "Durnan": [(5, 5), (6, 5), (5, 6)],
            "Elminster": [(8, 8), (9, 8), (8, 9)],
            "Mirt": [(7, 8), (8, 7), (6, 7)]
        }
        
        for name, npc in state.present_npcs.items():
            # First try the default position
            if name in pos_npc:
                x, y = pos_npc[name]
                if map.is_valid_position(x, y) and (x, y) not in map.items and (x, y) not in map.npc:
                    map.add_npc(npc, x, y)
                    if game:
                        game.io.show_message(f"Placed {name} at ({x}, {y})")  # Debug log
                    continue

            # If it fails, try the alternative positions
            if name in pos_npc_alternative:
                positioned = False
                for x, y in pos_npc_alternative[name]:
                    if map.is_valid_position(x, y) and (x, y) not in map.items and (x, y) not in map.npc:
                        map.add_npc(npc, x, y)
                        if game:
                            game.io.show_message(f"Placed {name} at alternative position ({x}, {y})")  # Debug log
                        positioned = True
                        break
                
                if positioned:
                    continue
                
            # If it still fails, look for a random position (last resort)
            positioned = False
            attempts = 0
            
            while not positioned and attempts < 20:
                x = random.randint(1, map.width - 2)
                y = random.randint(1, map.height - 2)
                
                # Check whether the position is valid and free
                if map.is_valid_position(x, y) and (x, y) not in map.items and (x, y) not in map.npc:
                    map.add_npc(npc, x, y)
                    if game:
                        game.io.show_message(f"Placed {name} at random position ({x}, {y})")  # Debug log
                    positioned = True

                attempts += 1

            if not positioned and game:
                game.io.show_message(f"ERROR: Could not place {name}")  # Debug log
            
        return True
