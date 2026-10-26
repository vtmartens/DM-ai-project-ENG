from items.interactive_object import InteractiveObject 
from entities.npc import NPC     
from entities.entity import Entity   
from entities.player import Player
from entities.enemy import Enemy
import json
import logging
from pathlib import Path

class Map:
    def __init__(self, name, width, height, type="indoor"):
        """
        Initializes a game map.

        Args:
            name (str): Name of the map (e.g. "tavern", "market")
            width (int): Width of the map in cells
            height (int): Height of the map in cells
            type (str): Type of map ("indoor", "outdoor", "dungeon", etc.)
        """
        self.name = name
        self.width = width
        self.height = height
        self.type = type
        
        # Matrix representing the map (0=empty, 1=wall, etc.)
        self.grid = [[0 for _ in range(width)] for _ in range(height)]

        # Dictionaries for tracking the objects on the map
        self.items = {}  # key: (x, y), value: object
        self.npc = {}      # key: (x, y), value: npc
        self.doors = {}    # key: (x, y), value: (destination_map, x_dest, y_dest)

        # Player's starting position on this map
        self.player_start_position = (0, 0)
        
    def add_item(self, item, x, y):
        """Adds an object to the map at a specific position"""
        self.items[(x, y)] = item
        item.position = (x, y, self.name)  # Update the object's position

    def add_npc(self, npc, x, y):
        """Adds an NPC to the map at a specific position"""
        self.npc[(x, y)] = npc
        npc.set_position(x, y)  # Uses the existing method in NPC

    def add_door(self, door, x, y, map_dest, x_dest, y_dest):
        """Links a door to another map and position"""
        self.items[(x, y)] = door
        door.position = (x, y, self.name)
        self.doors[(x, y)] = (map_dest, x_dest, y_dest)
        
    def set_wall(self, x, y):
        """Marks a cell as a wall"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = 1
            
    def set_initial_position(self, x, y):
        """Sets the player's starting position on this map"""
        self.player_start_position = (x, y)
        
    def get_item_at(self, x, y):
        """Returns the object at the specified position or None"""
        return self.items.get((x, y))
        
    def get_npc_at(self, x, y):
        """Returns the NPC at the specified position or None"""
        return self.npc.get((x, y))
    
    def get_door_at(self, x, y):
        """Returns the door's destination at the specified position or None"""
        return self.doors.get((x, y))
        
    def is_valid_position(self, x, y):
        """Checks whether the position is valid and walkable"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x] == 0  # 0 = empty cell
        return False
    
    @staticmethod
    def display_token(obj):
        """Returns a single-character map token for an object or NPC.

        Legacy data contains multi-character tokens such as "or" and "and",
        which shifted every cell after them. Fall back to the first alphanumeric
        character of the name so a row always has one character per cell.
        """
        token = getattr(obj, "token", "")
        if isinstance(token, str):
            token = token.strip()
            if len(token) == 1:
                return token

        name = getattr(obj, "name", "") or "?"
        for char in str(name):
            if char.isalnum():
                return char.upper()
        return "?"

    def token_legend(self):
        """Returns token -> name(s)/type(s) for everything placed on the map."""
        legend = {}

        def add(obj, kind):
            token = self.display_token(obj)
            entry = legend.setdefault(
                token, {"token": token, "names": set(), "types": set()}
            )
            entry["names"].add(str(getattr(obj, "name", str(obj))).replace("_", " "))
            entry["types"].add(getattr(obj, "type", None) or kind)

        for obj in self.items.values():
            add(obj, "object")
        for npc in self.npc.values():
            add(npc, "npc")

        return [
            {
                "token": entry["token"],
                "names": sorted(entry["names"]),
                "types": sorted(t for t in entry["types"] if t),
            }
            for entry in sorted(legend.values(), key=lambda item: item["token"])
        ]

    def generate_ascii_representation(self, pos_player=None):
        """
        Generates an ASCII representation of the map

        Args:
            player_pos: Tuple (x, y) of the player's position

        Returns:
            str: ASCII representation of the map
        """
        map_ascii = []
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                if pos_player and pos_player == (x, y):
                    row += "P"  # Player, we always use P for visual consistency
                elif (x, y) in self.npc:
                    row += self.display_token(self.npc[(x, y)])
                elif (x, y) in self.items:
                    row += self.display_token(self.items[(x, y)])
                elif self.grid[y][x] == 1:
                    row += "#"  # Wall
                else:
                    row += "."  # Empty space
            map_ascii.append(row)
        
        return "\n".join(map_ascii)
    
    def get_nearby_items(self, x, y, radius=1):
        """
        Returns the objects within a certain radius of the position

        Args:
            x, y: Center coordinates
            radius: Maximum distance in cells

        Returns:
            dict: Dictionary of positions and objects
        """
        nearby_items = {}
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                pos = (x + dx, y + dy)
                if pos in self.items:
                    nearby_items[pos] = self.items[pos]
        return nearby_items
    
    def get_nearby_npcs(self, x, y, radius=1):
        """
        Returns the NPCs within a certain radius of the position

        Args:
            x, y: Center coordinates
            radius: Maximum distance in cells

        Returns:
            dict: Dictionary of positions and NPCs
        """
        nearby_npcs = {}
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                pos = (x + dx, y + dy)
                if pos in self.npc:
                    nearby_npcs[pos] = self.npc[pos]
        return nearby_npcs
    
    def load_layout_from_string(self, layout_str):
        """
        Loads the map layout from a string of characters
        # = wall, . = floor, P = player start position

        Args:
            layout_str: Multi-line string representing the map
        """
        rows = layout_str.strip().split('\n')
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                if cell == '#':
                    self.set_wall(x, y)
                elif cell == 'P':
                    self.set_initial_position(x, y)
    
    def to_dict(self):
        """
        Converts the map into a dictionary for serialization.

        Returns:
            dict: Dictionary representation of the map
        """
        # Convert the grid into a list for serialization
        serialized_grid = [row.copy() for row in self.grid]

        # Serialize objects and NPCs using to_dict if available
        items_dict = {}
        for pos, obj in self.items.items():
            if hasattr(obj, 'to_dict'):
                items_dict[str(pos)] = obj.to_dict()
            else:
                items_dict[str(pos)] = {"name": obj.name, "token": obj.token}
        
        npc_dict = {}
        for pos, npc in self.npc.items():
            if hasattr(npc, 'to_dict'):
                npc_dict[str(pos)] = npc.to_dict()
            else:
                npc_dict[str(pos)] = {"name": npc.name, "token": npc.token}
        
        # Serialize the doors
        doors_dict = {str(pos): list(dest) for pos, dest in self.doors.items()}
        
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "type": self.type,
            "grid": serialized_grid,
            "items": items_dict,
            "npc": npc_dict,
            "doors": doors_dict,
            "player_start_position": self.player_start_position
        }
        
    @classmethod
    def from_dict(cls, data):
        """
        Creates a new Map instance from a dictionary.

        Args:
            data (dict): Dictionary with the map data

        Returns:
            Map: New Map instance
        """
        # Create a new map with the base parameters
        map = cls(
            name=data.get("name", "unknown_map"),
            width=data.get("width", 10),
            height=data.get("height", 10),
            type=data.get("type", "indoor")
        )
        
        # Load the grid
        if "grid" in data:
            map.grid = [row.copy() for row in data["grid"]]
        
        # Load the objects
        from items.interactive_object import InteractiveObject
        for pos_str, obj_data in data.get("items", {}).items():
            try:
                # Convert the position string into a tuple
                pos = eval(pos_str)  # Safe because the position is a simple tuple (x, y)

                # Create the object using from_dict if available
                if isinstance(obj_data, dict):
                    obj = InteractiveObject.from_dict(obj_data)
                    map.items[pos] = obj
                    # Update the object's position
                    obj.position = (pos[0], pos[1], map.name)
            except Exception as e:
                print(f"Error while loading the object at {pos_str}: {e}")

        # Load the NPCs
        from entities.npc import NPC
        for pos_str, npc_data in data.get("npc", {}).items():
            try:
                # Convert the position string into a tuple
                pos = eval(pos_str)

                # Create the NPC using from_dict if available
                if isinstance(npc_data, dict):
                    if hasattr(NPC, 'from_dict'):
                        npc = NPC.from_dict(npc_data)
                    else:
                        npc = NPC(npc_data.get("name", "NPC"), token=npc_data.get("token", "N"))
                    
                    map.npc[pos] = npc
                    npc.set_position(pos[0], pos[1])
            except Exception as e:
                print(f"Error while loading the NPC at {pos_str}: {e}")

        # Load the doors
        for pos_str, dest_data in data.get("doors", {}).items():
            try:
                pos = eval(pos_str)
                # Convert the destination list into a tuple
                if isinstance(dest_data, list) and len(dest_data) == 3:
                    map.doors[pos] = (dest_data[0], dest_data[1], dest_data[2])
            except Exception as e:
                print(f"Error while loading the door at {pos_str}: {e}")

        # Load the player's starting position
        if "player_start_position" in data:
            map.player_start_position = tuple(data["player_start_position"])
        
        return map

class MapComponent:
    """
    Base class for map components that can be serialized and deserialized.
    Used to extend the map's functionality with modular components.
    """
    def __init__(self, name, description=""):
        self.name = name
        self.description = description
        
    def to_dict(self):
        """Converts the component into a dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.__class__.__name__
        }
    
    @classmethod
    def from_dict(cls, data):
        """Creates a component instance from a dictionary"""
        return cls(
            name=data.get("name", "unknown_component"),
            description=data.get("description", "")
        )
        
class MapLoader:
    """
    Class responsible for loading and saving maps to and from files.
    """
    def __init__(self, base_path=None):
        """
        Initializes the map loader.

        Args:
            base_path: Base path where the map files are looked up
        """
        self.base_path = base_path or Path("data/maps")
        
    def load_map(self, file_name):
        """
        Loads a map from a JSON file.

        Args:
            file_name: Name of the JSON file (without path)

        Returns:
            Map: The loaded map object
        """
        complete_path = self.base_path / file_name
        
        if not complete_path.exists():
            raise FileNotFoundError(f"Map file not found: {complete_path}")
            
        try:
            with open(complete_path, 'r', encoding='utf-8') as f:
                map_data = json.load(f)
                
            return Map.from_dict(map_data)
        except Exception as e:
            logging.error(f"Error loading map {file_name}: {e}")
            raise
            
    def save_map(self, map, file_name=None):
        """
        Saves a map to a JSON file.

        Args:
            map: Map object to save
            file_name: Name of the file (if None, uses the map's name)

        Returns:
            bool: True if the save succeeded
        """
        file_name = file_name or f"{map.name}.json"
        complete_path = self.base_path / file_name
        
        # Make sure the directory exists
        complete_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(complete_path, 'w', encoding='utf-8') as f:
                json.dump(map.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Error saving map {file_name}: {e}")
            return False
            
    def list_available_maps(self):
        """
        Lists all maps available in the directory.

        Returns:
            list: List of file names of the available maps
        """
        if not self.base_path.exists():
            return []
            
        return [f.name for f in self.base_path.glob("*.json")]
