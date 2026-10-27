from world.map import Map
import random
from items.interactive_object import InteractiveObject, Door, Chest, Lever, Trap
from items.keys import find_matching_key
from entities.player import Player
from entities.npc import NPC
from entities.enemy import Enemy
from world.map import MapComponent, MapLoader
from pathlib import Path
from util.data_manager import get_data_manager
import json
import os
import logging
from util.config import get_save_path, create_backup, SAVE_FORMAT_VERSION


def _same_object_name(first, second):
    """Compares display names tolerantly ("Cellar Door" vs "cellar_door")."""

    def normalize(value):
        return str(value).replace("_", " ").replace("-", " ").strip().casefold()

    return normalize(first) == normalize(second)


def _is_locked_door(door):
    """True for a keyed door that has not been opened yet."""
    return (
        isinstance(door, Door)
        and bool(getattr(door, "requires_key", False))
        and getattr(door, "state", "closed") not in {"open", "unlocked"}
    )


def _door_label(door):
    """Human-readable door name for messages ("cellar_door" -> "Cellar door")."""
    label = str(getattr(door, "name", "door")).replace("_", " ").strip()
    if not label:
        return "Door"
    return label[:1].upper() + label[1:]


class MapManager:
    def __init__(self):
        """Initializes the map manager"""
        self.maps = {}  # Map name -> Map object
        self.current_map = None
        self.data_manager = get_data_manager()
        self.map_loader = MapLoader(Path("data/maps"))
        self.initialize_maps()

    def initialize_maps(self):
        """Creates and configures all the game maps exclusively from JSON"""
        # Load the maps from JSON files
        maps_json = self.load_maps_from_json()

        if not maps_json:
            logging.error("No JSON maps found. The game cannot continue without maps.")
            raise ValueError("No JSON maps found in data/maps. Check that the map JSON files exist.")

        # Use the maps loaded from JSON
        for name, map in maps_json.items():
            self.maps[name] = map
            # Load the interactive objects and NPCs for this map
            self.load_interactive_objects_from_json(map, name)
            self.load_npcs_from_json(map, name)

        logging.info(f"Loaded {len(maps_json)} maps from JSON files")

        # Set the "tavern" map as the default current map
        if "tavern" in self.maps:
            self.set_current_map("tavern")
        elif self.maps:
            # Otherwise, use the first available map
            first_name = next(iter(self.maps.keys()))
            self.set_current_map(first_name)
            logging.info(f"Tavern map not found, set map {first_name} as default")
        else:
            logging.error("No maps loaded")
        
    def load_maps_from_json(self):
        """
        Loads the maps from the JSON files in the data/maps directory.

        Returns:
            dict: Dictionary of loaded maps (name -> Map object) or {} if it fails
        """
        maps = {}

        try:
            # Get the list of all .json files in the maps directory
            file_maps = self.map_loader.list_available_maps()

            if not file_maps:
                logging.error("No map file found in data/maps")
                return {}

            # Load each map
            for file_name in file_maps:
                try:
                    map = self.map_loader.load_map(file_name)
                    # Check that the map is valid
                    if self._valid_verify_map(map):
                        maps[map.name] = map
                        logging.info(f"Map loaded: {map.name}")
                    else:
                        logging.error(f"Map {file_name} is invalid, skipped")
                except Exception as e:
                    logging.error(f"Error loading map {file_name}: {e}")
                    import traceback
                    logging.error(traceback.format_exc())

            return maps
        except Exception as e:
            logging.error(f"General error while loading maps: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return {}
    
    def _valid_verify_map(self, map):
        """
        Checks that a map is valid and complete.

        Args:
            map: The Map object to check

        Returns:
            bool: True if the map is valid, False otherwise
        """
        # Check that the map has a name
        if not map.name:
            logging.error("Map without a name")
            return False

        # Check that the grid is present and has the correct dimensions
        if not map.grid:
            logging.error(f"Map {map.name} has no grid")
            return False

        # Check that the grid dimensions match the declared ones
        if len(map.grid) != map.height:
            logging.error(f"Map {map.name}: declared height {map.height} but grid has {len(map.grid)} rows")
            return False

        for row in map.grid:
            if len(row) != map.width:
                logging.error(f"Map {map.name}: declared width {map.width} but row has {len(row)} columns")
                return False

        # Check that the starting position is set and valid
        x, y = map.player_start_position
        if x == 0 and y == 0:
            logging.error(f"Map {map.name}: player starting position is not set")
            return False

        if x < 0 or x >= map.width or y < 0 or y >= map.height:
            logging.error(f"Map {map.name}: player starting position ({x}, {y}) is outside the map bounds")
            return False

        # If the starting position is inside a wall, it is an error
        if map.grid[y][x] != 0:  # Assuming 0 is the empty space
            logging.error(f"Map {map.name}: player starting position ({x}, {y}) is inside a wall")
            return False

        # All checks passed
        return True
    
    def refresh_static_map_data(self):
        """Reconciles persisted maps with the current map JSON files.

        A save or cached session can outlive a fix to map data. Layout, exits
        and the start position are static, so refresh them from JSON while
        leaving NPCs, objects and the player's state untouched.
        """
        try:
            current_maps = self.load_maps_from_json()
        except Exception as e:
            logging.error(f"Error refreshing map data: {e}")
            return False

        if not current_maps:
            return False

        for name, current in current_maps.items():
            existing = self.maps.get(name)
            if existing is None:
                self.maps[name] = current
                self.load_interactive_objects_from_json(current, name)
                self.load_npcs_from_json(current, name)
                logging.info(f"Added new map {name} from JSON")
                continue
            if (
                existing.grid != current.grid
                or existing.doors != current.doors
                or existing.player_start_position != current.player_start_position
            ):
                logging.info(f"Refreshed static map data for {name}")
            existing.grid = current.grid
            existing.width = current.width
            existing.height = current.height
            existing.doors = current.doors
            existing.player_start_position = current.player_start_position
            # Place objects added by newer content (for example the Vault Door
            # and strongbox) without touching existing ones or resurrecting NPCs.
            self.load_interactive_objects_from_json(existing, name)

        return True

    def save_maps_to_json(self):
        """
        Saves all the current maps to JSON files.

        Returns:
            bool: True if the save succeeded for all the maps
        """
        success = True

        for name, map in self.maps.items():
            try:
                # Save the map in JSON format
                if not self.map_loader.save_map(map):
                    success = False
                    logging.error(f"Error saving map {name}")
            except Exception as e:
                success = False
                logging.error(f"Error while saving map {name}: {e}")
                
        return success

    def load_npcs_from_json(self, map, map_name):
        """
        Loads the NPCs for a map from the JSON configurations.

        Args:
            map (Map): Map object in which to place the NPCs
            map_name (str): Name of the map
        """
        try:
            # File name: map_npcs.json
            # Structure: {"tavern": [{"name": "Durnan", "position": [5, 5]}, ...], ...}
            npc_config = self.data_manager.load_data("npc", "map_npcs.json").get(map_name, [])

            if not npc_config:
                logging.info(f"No NPC configuration found for map {map_name}")
                return

            # For each NPC configuration
            for config in npc_config:
                npc_name = config.get("name")
                position = config.get("position")
                
                if not npc_name or not position or len(position) != 2:
                    logging.warning(f"Invalid NPC configuration: {config}")
                    continue

                # Create the NPC
                npc = NPC(npc_name)
                npc.group = config.get("group")

                # Place the NPC on the map
                x, y = position
                # Check that x and y are valid and within the map bounds
                if 0 <= x < map.width and 0 <= y < map.height:
                    # Check that the position is not already occupied
                    if (x, y) in map.items or (x, y) in map.npc:
                        logging.warning(f"Position ({x}, {y}) already occupied, cannot place NPC {npc_name}")
                        continue
                        
                    # Check that the position is not a wall
                    if map.grid[y][x] != 0:  # Assuming 0 is the empty space
                        logging.warning(f"Position ({x}, {y}) is a wall, cannot place NPC {npc_name}")
                        continue

                    map.add_npc(npc, x, y)
                    logging.info(f"NPC {npc_name} placed at ({x}, {y}) on map {map_name}")
                else:
                    logging.warning(f"Invalid position for NPC {npc_name}: ({x}, {y})")
        except Exception as e:
            logging.error(f"Error while loading NPCs for map {map_name}: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    def load_interactive_objects_from_json(self, map, map_name):
        """
        Loads the interactive objects for a map from the JSON configurations.

        Args:
            map (Map): Map object in which to place the objects
            map_name (str): Name of the map
        """
        try:
            # Get the object configuration for this map
            items_config = self.data_manager.get_map_objects(map_name)

            # If there are no configurations, warn but it is not a critical error
            if not items_config:
                logging.warning(f"No object configuration found for map {map_name}")
                return

            # For each object configuration
            for config in items_config:
                object_name = config.get("name")
                position = config.get("position")
                
                if not object_name or not position or len(position) != 2:
                    logging.warning(f"Invalid object configuration: {config}")
                    continue

                # Load the interactive object from the JSON
                item = InteractiveObject.load_from_json(object_name)
                
                if item:
                    # Place the object on the map
                    x, y = position
                    # Check that x and y are valid and within the map bounds
                    if 0 <= x < map.width and 0 <= y < map.height:
                        # Check that the position is not already occupied
                        if (x, y) in map.items or (x, y) in map.npc:
                            logging.warning(f"Position ({x}, {y}) already occupied, cannot place object {object_name}")
                            continue
                            
                        # Check that the position is not a wall
                        if map.grid[y][x] != 0:  # Assuming 0 is the empty space
                            logging.warning(f"Position ({x}, {y}) is a wall, cannot place object {object_name}")
                            continue

                        map.add_item(item, x, y)
                        logging.info(f"Object {object_name} placed at ({x}, {y}) on map {map_name}")
                    else:
                        logging.warning(f"Invalid position for object {object_name}: ({x}, {y})")
                else:
                    logging.warning(f"Object {object_name} not found in the JSON data")
        except Exception as e:
            logging.error(f"Error while loading objects for map {map_name}: {e}")
            import traceback
            logging.error(traceback.format_exc())
        
    def get_map(self, name):
        """Returns a map by name"""
        return self.maps.get(name)

    def remove_npc(self, map_name, npc):
        """Removes an NPC from a map, matching by identity or name."""
        map_obj = self.maps.get(map_name)
        if map_obj is None or npc is None:
            return None

        for position, candidate in list(map_obj.npc.items()):
            if candidate is npc:
                del map_obj.npc[position]
                return position

        name = getattr(npc, "name", None)
        if name:
            for position, candidate in list(map_obj.npc.items()):
                if _same_object_name(getattr(candidate, "name", ""), name):
                    del map_obj.npc[position]
                    return position

        return None

    def prune_defeated_npcs(self):
        """Removes NPCs at 0 HP left on maps by older sessions."""
        removed = []
        for map_name, map_obj in self.maps.items():
            for position, npc in list(map_obj.npc.items()):
                hp = getattr(npc, "hp", 1)
                if isinstance(hp, (int, float)) and hp <= 0:
                    del map_obj.npc[position]
                    removed.append((map_name, getattr(npc, "name", "?"), position))

        if removed:
            logging.info("Removed %d defeated NPC(s) from persisted maps", len(removed))
        return removed

    def set_current_map(self, name):
        """Sets the current map for easy reference"""
        if name in self.maps:
            self.current_map = self.maps[name]
            return True
        return False
        
    def transfer_items_from_state(self, map_name, state):
        """Transfers objects and NPCs from the state to the corresponding map"""
        map = self.maps.get(map_name)
        if not map:
            return False

        # Get the interactive object positions from the JSON configuration
        items_config = self.data_manager.get_map_objects(map_name)
        pos_items = {}
        
        if items_config:
            for config in items_config:
                object_name = config.get("name")
                position = config.get("position")
                if object_name and position and len(position) == 2:
                    pos_items[object_name] = tuple(position)
        
        # Place the interactive objects on the map using the positions from JSON
        for key, item in state.interactive_objects.items():
            if key in pos_items:
                x, y = pos_items[key]
                if 0 <= x < map.width and 0 <= y < map.height:
                    existing = map.items.get((x, y))
                    if existing is not None:
                        if _same_object_name(
                            getattr(existing, "name", ""), getattr(item, "name", "")
                        ):
                            # Already placed from map_objects.json; keep that
                            # instance and point the state at it so menu actions
                            # and map movement share one door/chest.
                            if isinstance(
                                getattr(state, "interactive_objects", None), dict
                            ):
                                state.interactive_objects[key] = existing
                            continue
                        logging.warning(f"Position ({x}, {y}) already occupied, cannot place object {key}")
                    elif (x, y) in map.npc:
                        logging.warning(f"Position ({x}, {y}) already occupied, cannot place object {key}")
                    else:
                        map.add_item(item, x, y)
                else:
                    logging.warning(f"Invalid position for object {key}: ({x}, {y})")
            else:
                logging.debug(f"No position defined for object {key}, object not placed")

        # Load NPC positions from JSON
        npc_config = self.data_manager.load_data("npc", "map_npcs.json").get(map_name, [])
        pos_npc = {}
        
        if npc_config:
            for config in npc_config:
                npc_name = config.get("name")
                position = config.get("position")
                if npc_name and position and len(position) == 2:
                    pos_npc[npc_name] = tuple(position)
        
        # Place the NPCs on the map using the positions from JSON
        for name, npc in state.present_npcs.items():
            if name in pos_npc:
                x, y = pos_npc[name]
                if 0 <= x < map.width and 0 <= y < map.height:
                    existing = map.npc.get((x, y))
                    if existing is not None:
                        if _same_object_name(
                            getattr(existing, "name", ""), getattr(npc, "name", "")
                        ):
                            # Already placed from map_npcs.json; keep that instance.
                            continue
                        logging.warning(f"Position ({x}, {y}) already occupied, cannot place NPC {name}")
                    elif (x, y) in map.items:
                        logging.warning(f"Position ({x}, {y}) already occupied, cannot place NPC {name}")
                    else:
                        map.add_npc(npc, x, y)
                else:
                    logging.warning(f"Invalid position for NPC {name}: ({x}, {y})")
            else:
                logging.warning(f"No position defined for NPC {name}, NPC not placed")
            
        return True

    def move_player(self, player, dx, dy):
        """
        Handles the player's movement on the map.

        Args:
            player (Player): The player to move
            dx, dy (int): Movement delta

        Returns:
            dict: Movement result with keys 'success', 'message', 'change_map'
        """
        # Check that we are on a valid map
        if not player.current_map or player.current_map not in self.maps:
            return {"success": False, "message": "Invalid map", "change_map": False}
            
        map = self.maps[player.current_map]
        
        # Calculate the new position
        new_x = player.x + dx
        new_y = player.y + dy
        
        # Check that the new position is valid
        if not (0 <= new_x < map.width and 0 <= new_y < map.height):
            return {"success": False, "message": "Position outside the map bounds", "change_map": False}

        # A door may be the only opening in a wall, so doors are checked first.
        door_dest = map.doors.get((new_x, new_y))
        door_object = map.items.get((new_x, new_y))

        # A keyed door blocks the transition until it is opened with its key,
        # Knock, or a lever.
        if door_dest is not None and _is_locked_door(door_object):
            return {
                "success": False,
                "message": f"The {_door_label(door_object)} is locked.",
                "change_map": False,
            }

        # Check whether there is a wall (unless this cell is a door)
        if door_dest is None and map.grid[new_y][new_x] != 0:
            return {"success": False, "message": "There is a wall in that direction", "change_map": False}

        # Check whether there is a blocking object
        if (new_x, new_y) in map.items:
            item = map.items[(new_x, new_y)]
            # Check whether the object is blocking
            if hasattr(item, 'blocking') and item.blocking:
                return {"success": False, "message": f"There is a blocking {item.name}", "change_map": False}

        # Check whether there is an NPC (they are always blocking)
        if (new_x, new_y) in map.npc:
            npc = map.npc[(new_x, new_y)]
            return {"success": False, "message": f"{npc.name} blocks your way", "change_map": False}

        # Update the player's position
        previous = (player.x, player.y)
        player.x = new_x
        player.y = new_y

        # If there is a door, change map
        if door_dest:
            map_dest, x_dest, y_dest = door_dest
            # Change map
            result = self.change_player_map(player, map_dest, x_dest, y_dest)
            if result["success"]:
                from core.achievements import record_event

                record_event(player, "movement")
                return {"success": True, "message": f"You entered {map_dest}", "change_map": True}
            else:
                # Keep the player next to the door rather than stranded on it.
                player.x, player.y = previous
                return {"success": False, "message": result["message"], "change_map": False}

        from core.achievements import record_event

        record_event(player, "movement")
        return {"success": True, "message": "You moved", "change_map": False}

    @staticmethod
    def _is_free_cell(map, x, y):
        """True when a cell is walkable and not occupied by an object or NPC."""
        return (
            0 <= x < map.width
            and 0 <= y < map.height
            and map.grid[y][x] == 0
            and (x, y) not in map.items
            and (x, y) not in map.npc
        )

    def _nearest_free_position(self, map, x, y):
        """Finds the free cell closest to (x, y), preferring cells that are not doors."""
        candidates = []
        fallback_candidates = []
        for candidate_y in range(map.height):
            for candidate_x in range(map.width):
                if not self._is_free_cell(map, candidate_x, candidate_y):
                    continue
                entry = (
                    abs(candidate_x - x) + abs(candidate_y - y),
                    candidate_y,
                    candidate_x,
                )
                fallback_candidates.append(entry)
                if (candidate_x, candidate_y) not in map.doors:
                    candidates.append(entry)

        pool = candidates or fallback_candidates
        if not pool:
            return None
        _, free_y, free_x = min(pool)
        return free_x, free_y

    def routes_to(self, map_name):
        """Returns (source map, cell, door object or None) for every route."""
        routes = []
        for source_name, source_map in self.maps.items():
            for (x, y), destination in source_map.doors.items():
                if destination[0] != map_name:
                    continue
                routes.append(
                    (source_name, (x, y), source_map.items.get((x, y)))
                )
        return routes

    def _routes_from(self, map_name):
        """Returns (destination, cell, door object or None) in a stable order."""
        source_map = self.maps.get(map_name)
        if source_map is None:
            return []
        routes = []
        for cell, destination in sorted(source_map.doors.items()):
            routes.append(
                (destination[0], cell, source_map.items.get(cell))
            )
        return routes

    def prepare_map_entry(self, player, map_name):
        """Decides whether the player may enter a map.

        Travel is checked as reachability from the player's current map: open
        routes are always passable, a locked route is passable only when the
        player carries a matching key. This prevents an open door in a distant
        room from unlocking a map from anywhere. Returns ``(allowed, message)``.
        When travel succeeds through a locked route, that door is opened.
        """
        if map_name not in self.maps:
            return False, f"Map {map_name} does not exist."

        current = getattr(player, "current_map", None)
        if current == map_name:
            return True, None

        if not current or current not in self.maps:
            return self._prepare_entry_without_origin(player, map_name)

        from collections import deque

        predecessors = {}
        visited = {current}
        queue = deque([current])
        final_route = None

        while queue and final_route is None:
            node = queue.popleft()
            for destination, cell, door in self._routes_from(node):
                if destination not in self.maps or destination in visited:
                    continue

                key = None
                if _is_locked_door(door):
                    key = find_matching_key(player, getattr(door, "name", ""))
                    if key is None:
                        continue

                predecessors[destination] = (node, cell, door, key)
                if destination == map_name:
                    final_route = predecessors[destination]
                    break

                visited.add(destination)
                queue.append(destination)

        if final_route is None:
            blocked = []
            for node in visited:
                source_map = self.maps.get(node)
                if source_map is None:
                    continue
                for cell, destination in sorted(source_map.doors.items()):
                    if destination[0] != map_name:
                        continue
                    door = source_map.items.get(cell)
                    if not _is_locked_door(door):
                        continue
                    if find_matching_key(player, getattr(door, "name", "")) is None:
                        blocked.append(door)
            if blocked:
                door = min(
                    blocked,
                    key=lambda item: str(getattr(item, "name", "")).casefold(),
                )
                return False, (
                    f"The way to {map_name.capitalize()} is locked "
                    f"({_door_label(door)})."
                )
            return False, f"The way to {map_name.capitalize()} is locked."

        _, _, door, key = final_route
        if _is_locked_door(door) and key is not None:
            door.state = "open"
            return True, f"You unlock the {_door_label(door)} with {key.name}."
        return True, None

    def _prepare_entry_without_origin(self, player, map_name):
        """Fallback for callers without a current map (tests, setup code)."""
        routes = self.routes_to(map_name)
        if not routes:
            return True, None
        if any(not _is_locked_door(door) for _, _, door in routes):
            return True, None
        for _, _, door in routes:
            key = find_matching_key(player, getattr(door, "name", ""))
            if key is not None:
                door.state = "open"
                return True, (
                    f"You unlock the {_door_label(door)} with {key.name}."
                )
        return False, (
            f"The way to {map_name.capitalize()} is locked "
            f"({_door_label(routes[0][2])})."
        )

    def change_player_map(self, player, map_name, x=None, y=None):
        """
        Changes the player's current map.

        Args:
            player (Player): The player to move
            map_name (str): Name of the new map
            x, y (int, optional): Position at which to place the player in the new map

        Returns:
            dict: Result of the operation with keys 'success' and 'message'
        """
        # Check that the map exists
        if map_name not in self.maps:
            return {"success": False, "message": f"Map {map_name} does not exist"}

        # Direct travel (map selection, "go to <map>") must obey the same
        # locks as walking through a door.
        if getattr(player, "current_map", None) != map_name:
            allowed, message = self.prepare_map_entry(player, map_name)
            if not allowed:
                return {"success": False, "message": message}
            if message:
                game = getattr(player, "game", None)
                if game is not None and getattr(game, "io", None):
                    game.io.show_message(message)

        # Get the new map
        new_map = self.maps[map_name]

        # If x and y are not specified, use the map's starting position
        if x is None or y is None:
            x, y = new_map.player_start_position

        # Old saves and persisted sessions can name an arrival cell that is now a
        # wall or is occupied (for example the market's door object). Move the
        # player to the nearest free cell instead of failing the transition and
        # leaving them stuck on the exit.
        if not self._is_free_cell(new_map, x, y):
            requested = (x, y)
            fallback = self._nearest_free_position(new_map, x, y)
            if fallback is None:
                return {"success": False, "message": f"No free position is available in map {map_name}"}
            x, y = fallback
            logging.warning(
                "Arrival cell %s in map %s is unavailable; using (%s, %s) instead",
                requested,
                map_name,
                x,
                y,
            )

        # Update the map and the player's position
        player.current_map = map_name
        player.x = x
        player.y = y

        # Set the new map as the current map
        self.set_current_map(map_name)

        from core.achievements import record_event

        record_event(player, "area_visited", map=map_name)

        return {"success": True, "message": f"You entered {map_name}"}
    
    def get_position_info(self, x, y, map=None):
        """
        Gets information about what is at a specific position.

        Args:
            x, y (int): Coordinates to check
            map (Map, optional): Map in which to search. If None, uses the current map.

        Returns:
            dict: Position information with keys 'type', 'item' and 'message'
        """
        # If no map is specified, use the current map
        map = map or self.current_map
        if not map:
            return {"type": "error", "item": None, "message": "No active map"}

        # Check that the position is valid
        if not (0 <= x < map.width and 0 <= y < map.height):
            return {"type": "out_of_map", "item": None, "message": "Position outside the map bounds"}

        # Check whether there is a wall
        if map.grid[y][x] != 0:  # Assuming 0 is the empty space
            return {"type": "wall", "item": None, "message": "There is a wall here"}

        # Check whether there is an object
        if (x, y) in map.items:
            item = map.items[(x, y)]
            return {"type": "item", "item": item, "message": f"{item.name} is here"}

        # Check whether there is an NPC
        if (x, y) in map.npc:
            npc = map.npc[(x, y)]
            return {"type": "npc", "item": npc, "message": f"{npc.name} is here"}

        # Check whether there is a door
        if (x, y) in map.doors:
            door_dest = map.doors[(x, y)]
            map_dest = door_dest[0]
            return {"type": "door", "item": door_dest, "message": f"There is a door to {map_dest} here"}

        # If there is nothing
        return {"type": "empty", "item": None, "message": "There is nothing here"}
    
    def to_dict(self):
        """
        Converts the map manager into a dictionary for serialization.

        Returns:
            dict: Dictionary representation of the map manager
        """
        # List of the serialized maps
        maps_dict = {}
        for name, map in self.maps.items():
            maps_dict[name] = map.to_dict()
            
        return {
            "maps": maps_dict,
            "current_map": self.current_map.name if self.current_map else None,
            "version": SAVE_FORMAT_VERSION
        }
        
    def from_dict(self, data):
        """
        Loads the map manager state from a dictionary.

        Args:
            data (dict): Dictionary containing the map manager state

        Returns:
            bool: True if the load succeeded, False otherwise
        """
        try:
            from world.map import Map

            # Load the maps from the dictionary
            maps_data = data.get("maps", {})
            self.maps = {}
            
            for map_name, map_dict in maps_data.items():
                self.maps[map_name] = Map.from_dict(map_dict)
                
                # Load the interactive objects for this map
                self.load_interactive_objects_from_json(self.maps[map_name], map_name)

            # Set the current map
            current_map_name = data.get("current_map")
            if current_map_name and current_map_name in self.maps:
                self.current_map = self.maps[current_map_name]
            elif self.maps:
                # If there is no current map, set the first available one
                self.current_map = next(iter(self.maps.values()))

            # Apply fixes to map layout/exits made since this save was written.
            self.refresh_static_map_data()
            self.prune_defeated_npcs()

            return True
        except Exception as e:
            print(f"Error while loading maps: {e}")
            return False
    
    def save(self, file_path="maps_save.json"):
        """
        Saves the complete state of all the maps and their interactive objects.

        Args:
            file_path (str): Path of the file in which to save the data

        Returns:
            bool: True if the save succeeded, False otherwise
        """
        logger = logging.getLogger("game_rpg")

        try:
            # Create the save dictionary
            save_data = self.to_dict()

            # Determine the save path
            save_path = get_save_path(file_path)

            # Create a backup if the file already exists
            if os.path.exists(save_path):
                backup_success = create_backup(save_path)
                if backup_success:
                    logger.info(f"Backup created for {save_path}")
                else:
                    logger.warning(f"Could not create backup for {save_path}")

            # Make sure the directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Save the file
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
            
            # Also save the interactive objects
            saved_items = self.save_modified_interactive_objects()

            logger.info(f"Maps saved successfully to {save_path}")
            return True
        except Exception as e:
            import traceback
            logging.getLogger("game_rpg").error(f"Error while saving maps: {e}")
            logging.getLogger("game_rpg").error(traceback.format_exc())
            return False
            
    def save_modified_interactive_objects(self):
        """
        Saves the modified interactive objects to the JSON system.

        Returns:
            bool: True if the save succeeded, False otherwise
        """
        logger = logging.getLogger("game_rpg")

        try:
            # Get all interactive objects from all the maps
            items_by_map = {}
            interactive_objects = []
            
            for map_name, map in self.maps.items():
                items_by_map[map_name] = []
                
                for pos, item in map.items.items():
                    # Add the object to the general list for saving
                    interactive_objects.append(item)

                    # Add the position to the list for this map
                    items_by_map[map_name].append({
                        "name": item.name,
                        "position": list(pos)  # Convert the tuple into a list for JSON serialization
                    })

            # Save the object positions for each map
            for map_name, items in items_by_map.items():
                self.data_manager.save_map_objects(map_name, items)
                logger.info(f"Saved positions of {len(items)} objects for map {map_name}")

            # Save the interactive objects themselves
            saved_items = 0
            items_with_errors = 0
            
            for item in interactive_objects:
                try:
                    item.save_to_json()
                    saved_items += 1
                except Exception as e:
                    logger.error(f"Error saving object {item.name}: {e}")
                    items_with_errors += 1
            
            if items_with_errors > 0:
                logger.warning(f"Saved {saved_items} objects with {items_with_errors} errors")
            else:
                logger.info(f"Successfully saved {saved_items} interactive objects")
                
            return items_with_errors == 0
        except Exception as e:
            import traceback
            logging.getLogger("game_rpg").error(f"Error while saving interactive objects: {e}")
            logging.getLogger("game_rpg").error(traceback.format_exc())
            return False

    def load(self, file_path="maps_save.json"):
        """
        Loads the complete state of all the maps and their interactive objects.

        Args:
            file_path (str): Path of the file from which to load the data

        Returns:
            bool: True if the load succeeded, False otherwise
        """
        logger = logging.getLogger("game_rpg")

        try:
            # Determine the load path
            save_path = get_save_path(file_path)

            # Check that the file exists
            if not os.path.exists(save_path):
                logger.error(f"Save file not found: {save_path}")
                return False

            # Load the file
            with open(save_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)

            # Check the version
            saved_version = saved_data.get("version", "1.0")
            if saved_version != SAVE_FORMAT_VERSION:
                logger.warning(f"Save version ({saved_version}) differs from the current one ({SAVE_FORMAT_VERSION})")

            # Load the maps from the dictionary
            maps_data = saved_data.get("maps", {})
            self.maps = {}
            
            for map_name, map_dict in maps_data.items():
                try:
                    # We use the existing from_dict method in the Map class
                    self.maps[map_name] = Map.from_dict(map_dict)

                    # Load the interactive objects for this map
                    self.load_interactive_objects_from_json(self.maps[map_name], map_name)
                except Exception as e:
                    logger.error(f"Error loading map {map_name}: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Set the current map
            current_map_name = saved_data.get("current_map")
            if current_map_name and current_map_name in self.maps:
                self.current_map = self.maps[current_map_name]
                logger.info(f"Current map set to: {current_map_name}")
            elif self.maps:
                # If there is no current map, set the first available one
                self.current_map = next(iter(self.maps.values()))
                logger.warning(f"Current map not specified, set to: {self.current_map.name}")
            else:
                logger.error("No maps loaded")
                return False

            # Apply fixes to map layout/exits made since this save was written.
            self.refresh_static_map_data()
            self.prune_defeated_npcs()

            logger.info(f"Maps loaded successfully from {save_path}")
            return True
        except Exception as e:
            import traceback
            logging.getLogger("game_rpg").error(f"Error while loading maps: {e}")
            logging.getLogger("game_rpg").error(traceback.format_exc())
            return False
