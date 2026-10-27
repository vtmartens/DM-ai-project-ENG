import os
import json
import logging
from pathlib import Path

# Configure the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base path for the data
DATA_DIR = Path(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))

class DataManager:
    """
    Manager for the game's static data.
    Loads the data from the JSON files in the 'data' directory.
    """
    
    _instance = None
    _data_cache = {}
    
    def __new__(cls):
        """Singleton implementation to have only one instance of the data manager."""
        if cls._instance is None:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initializes the directories for the data."""
        self._data_paths = {
            "classes": DATA_DIR / "classes",
            "tutorials": DATA_DIR / "tutorials",
            "achievements": DATA_DIR / "achievements",
            "items": DATA_DIR / "items",
            "npc": DATA_DIR / "npc",
            "quests": DATA_DIR / "quests",
            "monsters": DATA_DIR / "monsters",
            "conditions": DATA_DIR / "conditions",
            "combat": DATA_DIR / "combat",
            "factions": DATA_DIR / "factions",
            "trials": DATA_DIR / "trials",
            "crafting": DATA_DIR / "crafting",
            "road": DATA_DIR / "road",
            "assets_info": DATA_DIR / "assets_info"
        }
        
        # Make sure all the directories exist
        for path in self._data_paths.values():
            if not path.exists():
                logger.warning(f"Data directory not found: {path}")
    
    def load_data(self, data_type, file_name=None, reload=False):
        """
        Loads the data from a JSON file.

        Args:
            data_type (str): Type of data to load (classes, tutorials, etc.)
            file_name (str, optional): Name of the specific file. If None, uses the default value.
            reload (bool, optional): If True, reloads the data even if already cached.

        Returns:
            dict/list: The data loaded from the JSON file.
        """
        if data_type not in self._data_paths:
            logger.error(f"Invalid data type: {data_type}")
            return {}

        # Determine the default file name if not specified
        if file_name is None:
            file_name = f"{data_type}.json"
        
        # Cache key
        cache_key = f"{data_type}/{file_name}"

        # If the data is already cached and a reload is not requested, return it
        if not reload and cache_key in self._data_cache:
            return self._data_cache[cache_key]

        # Full path of the file
        file_path = self._data_paths[data_type] / file_name
        
        try:
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return {}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._data_cache[cache_key] = data
                return data
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            return {}
    
    def get_all_data_files(self, data_type):
        """
        Returns all the data files of a certain type.

        Args:
            data_type (str): Type of data to look for.

        Returns:
            list: List of the available file names.
        """
        if data_type not in self._data_paths:
            logger.error(f"Invalid data type: {data_type}")
            return []
        
        path = self._data_paths[data_type]
        if not path.exists():
            return []
        
        return [f.name for f in path.glob("*.json")]
    
    def get_classes(self):
        """Get information about the character classes."""
        return self.load_data("classes")
    
    def get_tutorials(self):
        """Get the game tutorials."""
        return self.load_data("tutorials")
    
    def get_achievements(self):
        """Get the game achievements."""
        return self.load_data("achievements")

    def get_quests(self):
        """Get the quest definitions."""
        return self.load_data("quests", "quests.json")
    
    def get_items(self, category=None):
        """
        Get the game items, optionally filtered by category.

        Args:
            category (str, optional): Item category (weapons, armor, etc.)

        Returns:
            list: List of items.
        """
        if category:
            file_name = f"{category}.json"
            return self.load_data("items", file_name)
        else:
            # Load all the items from all the files
            items = []
            for file_name in self.get_all_data_files("items"):
                items_data = self.load_data("items", file_name)
                if isinstance(items_data, list):
                    items.extend(items_data)
                elif isinstance(items_data, dict):
                    # If it is a dictionary, add the items with the category
                    category = file_name.replace(".json", "")
                    for item_id, item in items_data.items():
                        item_copy = item.copy()
                        item_copy["id"] = item_id
                        item_copy["category"] = category
                        items.append(item_copy)
            return items
    
    def get_asset_info(self, asset_type=None):
        """
        Get information about the graphic assets.

        The backend ships no graphic assets. The catalogue file exists so the
        API shape is stable; clients should treat empty lists as "use
        placeholders".

        Args:
            asset_type (str, optional): Type of asset (characters, items, etc.)

        Returns:
            dict or list: The whole catalogue, or one category of it.
        """
        catalogue = self.load_data("assets_info", "assets.json")
        if not isinstance(catalogue, dict):
            return [] if asset_type else {}
        if asset_type:
            return catalogue.get(asset_type, [])
        return catalogue
    
    def get_npc_data(self, npc_name=None):
        """
        Get the data of one or all the NPCs.

        Args:
            npc_name (str, optional): Name of the specific NPC requested.

        Returns:
            dict: Data of the NPC or of all the NPCs.
        """
        npcs = self.load_data("npc", "npcs.json")
        if npc_name:
            return npcs.get(npc_name, {})
        return npcs
    
    def get_npc_conversation(self, npc_name, state="start"):
        """
        Get an NPC's conversation for the specified state.

        Args:
            npc_name (str): Name of the NPC.
            state (str, optional): Conversation state.

        Returns:
            dict: Conversation data for the specified state.
        """
        conversations = self.load_data("npc", "conversations.json")
        npc_conversations = conversations.get(npc_name)
        
        # If there are no specific conversations for this NPC, use the default ones
        if not npc_conversations:
            npc_conversations = conversations.get("default", {})
            
        # Return the conversation for the specified state or the initial one
        return npc_conversations.get(state, npc_conversations.get("start", {}))
    
    def get_all_npc_conversations(self, npc_name):
        """
        Get all the conversations of an NPC.

        Args:
            npc_name (str): Name of the NPC.

        Returns:
            dict: All the conversations of the NPC.
        """
        conversations = self.load_data("npc", "conversations.json")
        return conversations.get(npc_name, conversations.get("default", {}))
    
    def get_interactive_objects(self, object_name=None):
        """
        Get the data of the interactive objects.

        Args:
            object_name (str, optional): Name of the specific object requested.

        Returns:
            dict or list: Data of the specific object or list of all the interactive objects.
        """
        items = self.load_data("items", "interactive_objects.json")
        if object_name:
            for item in items:
                if item.get("name") == object_name:
                    return item
            return {}
        return items
    
    def save_interactive_objects(self, items):
        """
        Saves the interactive object data.

        Args:
            items (list): List of interactive objects to save.

        Returns:
            bool: True if the save succeeded, False otherwise.
        """
        return self.save_data("items", items, "interactive_objects.json")
    
    def get_map_objects(self, map_name):
        """
        Get the interactive objects associated with a specific map.

        Args:
            map_name (str): Name of the map.

        Returns:
            list: List of interactive objects present in the map.
        """
        map_objects = self.load_data("items", "map_objects.json")
        return map_objects.get(map_name, [])
    
    def save_map_objects(self, map_name, item_positions):
        """
        Saves the interactive objects associated with a map.

        Args:
            map_name (str): Name of the map.
            item_positions (list): List of interactive objects with their positions.

        Returns:
            bool: True if the save succeeded, False otherwise.
        """
        map_objects = self.load_data("items", "map_objects.json")
        map_objects[map_name] = item_positions
        return self.save_data("items", map_objects, "map_objects.json")
    
    def save_data(self, data_type, data, file_name=None):
        """
        Saves the data to a JSON file.

        Args:
            data_type (str): Type of data to save.
            data (dict/list): Data to save.
            file_name (str, optional): Name of the file. If None, uses the default value.

        Returns:
            bool: True if the save succeeded, False otherwise.
        """
        if data_type not in self._data_paths:
            logger.error(f"Invalid data type: {data_type}")
            return False

        # Determine the default file name if not specified
        if file_name is None:
            file_name = f"{data_type}.json"

        # Full path of the file
        file_path = self._data_paths[data_type] / file_name

        try:
            # Make sure the directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Update the cache
            cache_key = f"{data_type}/{file_name}"
            self._data_cache[cache_key] = data
            
            return True
        except Exception as e:
            logger.error(f"Error saving file {file_path}: {str(e)}")
            return False

# Global instance for easy access
data_manager = DataManager()

def get_data_manager():
    """
    Get the data manager instance.

    Returns:
        DataManager: The singleton instance of the data manager.
    """
    return data_manager 