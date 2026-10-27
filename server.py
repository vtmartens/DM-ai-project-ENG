from flask import Flask, jsonify, redirect, request, send_file, send_from_directory
from uuid import uuid4
import os
import pickle
import json
import time
import datetime
import logging
from flask_cors import CORS

from core.game_state import GameState
from entities.player import Player
from states.tavern import TavernState
from util.data_manager import get_data_manager
from util.config import (
    BACKUPS_DIR,
    BASE_DIR,
    SAVE_DIR,
    SESSIONS_DIR,
    delete_save_file,
    get_save_path,
    get_session_path,
    list_save_files,
)

# Configure the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("game_rpg")

app = Flask(__name__)
CORS(app)  # Enable CORS to allow requests from the frontend

# Make sure the directories exist
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# Directories for the graphic assets and the optional web client
ASSETS_DIR = BASE_DIR / "assets"
FRONTEND_DIR = BASE_DIR / "frontend"
os.makedirs(ASSETS_DIR, exist_ok=True)

# Dictionary to store the active sessions in memory
active_sessions = {}  # {uuid: GameState}

# Dictionary to store the system notifications
system_notifications = {}  # {uuid: [list of notifications]}

def save_session(session_id, session):
    """Save a session to disk"""
    path = get_session_path(session_id)
    with open(path, 'wb') as f:
        pickle.dump(session, f)

def load_session(session_id):
    """Load a session from disk"""
    path = get_session_path(session_id)
    if os.path.exists(path):
        with open(path, 'rb') as f:
            session = pickle.load(f)
        # Cached sessions can predate fixes to static map layout or exits.
        map_manager = getattr(getattr(session, "game", None), "map_manager", None)
        if map_manager is not None and hasattr(map_manager, "refresh_static_map_data"):
            map_manager.refresh_static_map_data()
        if map_manager is not None and hasattr(map_manager, "prune_defeated_npcs"):
            map_manager.prune_defeated_npcs()
        game = getattr(session, "game", None)
        if game is not None and hasattr(game, "_restore_quest_items"):
            game._restore_quest_items()
        return session
    return None

def get_session_or_error(session_id):
    """Returns (session, error_response) and caches disk-loaded sessions."""
    if not session_id:
        return None, (jsonify({"error": "Session ID not provided"}), 400)

    session = active_sessions.get(session_id)
    if session is None:
        session = load_session(session_id)
        if session is not None:
            active_sessions[session_id] = session

    if session is None:
        return None, (jsonify({"error": "Session not found"}), 404)
    return session, None


def add_notification(session_id, type, message, data=None):
    """Add a notification to the system"""
    if session_id not in system_notifications:
        system_notifications[session_id] = []
    
    notification = {
        "id": str(uuid4()),
        "type": type,  # "info", "warning", "achievement", "quest", "combat", etc.
        "message": message,
        "data": data or {},
        "timestamp": time.time(),
        "read": False
    }
    
    system_notifications[session_id].append(notification)
    return notification

@app.route("/")
def home():
    """Main page"""
    return jsonify({
        "message": "RPG server active",
        "endpoints": {
            "POST /start": "Create a new game",
            "POST /command": "Send a command to the game",
            "GET /state": "Get the current game state",
            "POST /save": "Save the current game",
            "POST /load": "Load an existing game",
            "GET /map": "Get information about the map",
            "POST /move": "Move the player in a direction",
            "GET /inventory": "Get the player's inventory",
            "GET /stats": "Get the player's stats",
            "GET /position": "Get the player's position",
            "GET /map_view": "Get the current map as an ASCII grid",
            "GET /missions": "Get active/completed quests",
            "GET /classes": "Get information about the available classes",
            "GET /saves": "Get the list of available saves (legacy shape)",
            "GET /list_saves": "Get the list of available saves",
            "GET /combat": "Get the current combat state",
            "POST /combat_action": "Perform a combat action",
            "GET /npcs": "Get information about the NPCs in the current location",
            "GET /log": "Get the log of recent events",
            "POST /equipment": "Manage the player's equipment",
            "GET /available_actions": "Get the actions available in the current context",
            "GET /shop": "Get the market stock and sellable inventory",
            "POST /shop/buy": "Buy a market item",
            "POST /shop/sell": "Sell an inventory item",
            "GET /forge": "Get the Sanctum Forge recipes",
            "POST /forge/craft": "Craft a Rune Shard recipe",
            "GET /bounties": "Get the tavern bounty board",
            "POST /bounties/accept": "Accept a bounty contract",
            "POST /bounties/claim": "Claim a ready bounty contract",
            "POST /dialogue": "Manage dialogue with an NPC",
            "POST /explore": "Explore the surrounding environment",
            "POST /preferences": "Save the user's preferences",
            "POST /delete_save": "Delete a save",
            "GET /notifications": "Get unread notifications",
            "POST /read_notification": "Mark a notification as read",
            "GET /asset/<path:file_name>": "Get a graphic asset",
            "GET /assets_info": "Get information about the available assets",
            "GET /tutorial": "Get information about the tutorials",
            "GET /achievements": "Get the player's achievements",
            "GET /reputation": "Get faction standing and shop discounts",
            "GET /campaign": "Get main-story and endgame progress",
            "POST /hint": "Ask the Dungeon Master for a hint",
            "POST /recap": "Get a recap of the story so far",
            "GET /item_details": "Get details about a specific item",
            "GET /abilities": "Get the player's abilities",
            "POST /use_ability": "Use a player ability",
            "POST /export_save": "Export a save as a file",
            "POST /import_save": "Import a save from a file",
            "GET /app": "Serve the optional web client"
        }
    })

@app.route("/start", methods=["POST"])
def start_game():
    """Start a new game session"""
    # Extract the data from the request
    data = request.json or {}
    name = data.get("name", "Adventurer")
    char_class = data.get("char_class", "fighter").lower()
    
    # Create a new session ID
    session_id = str(uuid4())
    
    # Create a new player
    player = Player(name, char_class)
    
    # Create a new game session
    session = GameState(player, TavernState())
    active_sessions[session_id] = session
    
    # Render the opening menu without consuming a command
    session.process_command("", provide_input=False)
    structured_output = session.io_buffer.get_structured_output()
    session.io_buffer.clear()

    # Save the session to disk
    save_session(session_id, session)

    # Get the initial state
    state = session.get_current_state()

    return jsonify({
        "session_id": session_id,
        "message": "Game started",
        "player": session.get_player_summary(),
        "state": state,
        "output": structured_output,
    })

@app.route("/command", methods=["POST"])
def run_command():
    """Process a command sent by the client"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    command = data.get("command", "")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Process the command
    session.process_command(command)
    
    # Save the updated session
    save_session(session_id, session)
    
    # Get the current state
    current_state = session.get_current_state()
    
    # Get the name of the current state
    state_name = "NoneState"
    if session.game.current_state():
        state_name = type(session.game.current_state()).__name__
    
    # Get the structured output
    structured_output = session.io_buffer.get_structured_output()
    
    # Clear the message buffer
    session.io_buffer.clear()
    
    # Check whether the game has ended
    game_finished = not session.game.active
    
    # Return the updated state
    return jsonify({
        "output": structured_output,
        "state": current_state,
        "state_name": state_name,
        "end": game_finished
    })

@app.route("/state", methods=["GET"])
def get_state():
    """Get the current state of the session"""
    # Extract the session ID from the query string
    session_id = request.args.get("session_id")
    
    # Check that the session ID was provided
    
    # Look for the session in memory or on disk
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Return the current state
    return jsonify(session.get_current_state())

@app.route("/save", methods=["POST"])
def save_game():
    """Save the game to a file"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    file_name = data.get("file_name", "save.json")
    
    # Check that the session ID was provided
    
    # Look for the session
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Save the game
    try:
        # Get the full path through the config module
        path = get_save_path(file_name)
        saved = session.save(path)
        if not saved:
            return jsonify(
                {"error": "The game cannot be saved in the current state"}
            ), 409
        logger.info(f"Game saved to {path}")
        return jsonify({"message": f"Game saved to {file_name}"})
    except Exception as e:
        logger.error(f"Error while saving: {str(e)}")
        return jsonify({"error": f"Error while saving: {str(e)}"}), 500

@app.route("/load", methods=["POST"])
def load_game():
    """Load a game from a file"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    file_name = data.get("file_name", "save.json")

    # A save can be loaded without an existing session (e.g. from the start
    # screen): create a fresh session for it. A provided-but-unknown session
    # ID is still a 404 so clients notice stale IDs.
    if session_id:
        session, error = get_session_or_error(session_id)
        if error:
            return error
    else:
        session_id = str(uuid4())
        session = GameState(Player("Adventurer", "fighter"), None)

    # Load the game
    try:
        # Get the full path through the config module
        path = get_save_path(file_name)

        if not os.path.exists(path):
            return jsonify({"error": f"Save file not found: {file_name}"}), 404

        result = session.load(path)

        if result:
            structured_output = session.io_buffer.get_structured_output()
            session.io_buffer.clear()

            # Save the updated session
            active_sessions[session_id] = session
            save_session(session_id, session)

            # Get information about the player
            state = session.get_current_state()

            return jsonify({
                "session_id": session_id,
                "message": f"Game loaded from {file_name}",
                "player": session.get_player_summary(),
                "state": state,
                "output": structured_output,
            })
        else:
            return jsonify({"error": "Error while loading"}), 500
    except Exception as e:
        logger.error(f"Error while loading the game: {str(e)}")
        return jsonify({"error": f"Error while loading: {str(e)}"}), 500

def _json_safe_position(info):
    """Convert Game.get_player_position() into something jsonify can serialize.

    That method returns nearby_items / nearby_npcs as {(x, y): object}, and a tuple key
    makes jsonify raise "keys must be str, int, float, bool or None, not tuple"; the
    objects are not serializable either. Neither /map nor /position worked because of
    this. The engine's own return value is left untouched.
    """
    if not isinstance(info, dict):
        return info
    out = dict(info)
    for key in ("nearby_items", "nearby_npcs"):
        value = out.get(key)
        if isinstance(value, dict):
            out[key] = [
                {
                    "position": list(pos) if isinstance(pos, tuple) else pos,
                    "name": getattr(obj, "name", str(obj)),
                    "type": getattr(obj, "type", None),
                }
                for pos, obj in value.items()
            ]
    return out

@app.route("/map", methods=["GET"])
def get_map():
    """Get information about the current map"""
    # Extract the session ID from the query string
    session_id = request.args.get("session_id")
    
    # Check that the session ID was provided
    
    # Look for the session
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Get information about the map
    position_info = session.get_player_position()
    
    if not position_info:
        return jsonify({"error": "Player position not available"}), 404
    
    return jsonify(_json_safe_position(position_info))

@app.route("/move", methods=["POST"])
def move_player():
    """Move the player in the specified direction"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    direction = data.get("direction")
    
    # Check that both the session ID and the direction were provided
    if not direction:
        return jsonify({"error": "Direction not provided"}), 400
    
    # Look for the session
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Move the player
    movement = session.move_player(direction)
    
    # Save the updated session
    save_session(session_id, session)
    
    # Return the updated state
    return jsonify({
        "movement": movement,
        "state": session.get_current_state()
    })

@app.route("/inventory", methods=["GET"])
def get_inventory():
    """Get the player's inventory"""
    session_id = request.args.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Get the full state and extract only the inventory information
    state = session.get_current_state()
    
    return jsonify({
        "inventory": state.get("inventory", []),
        "equipment": state.get("equipment", {})
    })

@app.route("/stats", methods=["GET"])
def get_stats():
    """Get the player's stats"""
    session_id = request.args.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Get the full state and extract only the stats
    state = session.get_current_state()
    
    return jsonify({
        "name": state.get("name", ""),
        "char_class": state.get("char_class", ""),
        "hp": state.get("hp", 0),
        "max_hp": state.get("max_hp", 0),
        "stats": state.get("stats", {})
    })

@app.route("/map_view", methods=["GET"])
def get_map_view():
    """Get the current map as an ASCII grid with the player marked."""
    session_id = request.args.get("session_id")


    session, error = get_session_or_error(session_id)
    if error:
        return error

    view = session.get_map_view()
    if not view:
        return jsonify({"error": "Map not available"}), 404

    return jsonify(view)


@app.route("/position", methods=["GET"])
def get_position():
    """Get the player's current position"""
    session_id = request.args.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Use the existing method to get the position
    position_info = session.get_player_position()
    
    if not position_info:
        return jsonify({"error": "Player position not available"}), 404
    
    return jsonify(_json_safe_position(position_info))

@app.route("/classes", methods=["GET"])
def get_classes():
    """Get information about the available character classes"""
    # Use the data manager to load the classes from the external file
    return jsonify(get_data_manager().get_classes())

@app.route("/missions", methods=["GET"])
def get_quests():
    """Get the list of the player's active and completed quests"""
    session_id = request.args.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # The player keeps a quest log; the state view exposes it directly.
    state = session.get_current_state()
    quests = {
        "active": state.get("active_quests", []),
        "completed": state.get("completed_quests", []),
        "in_progress": dict(session.game.player.progress_quests),
    }

    return jsonify(quests)

@app.route("/combat", methods=["GET"])
def get_combat_state():
    """Get the current combat state"""
    session_id = request.args.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    return jsonify(session.get_combat_state())

@app.route("/combat_action", methods=["POST"])
def run_combat_action():
    """Perform a combat action"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    action = data.get("action", "")
    target = data.get("target", "")
    parameters = data.get("parameters", {})
    
    
    if not action:
        return jsonify({"error": "Action not specified"}), 400
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Build a formatted command for the combat action
    command = f"{action}"
    if target:
        command += f" {target}"
    
    # Process the command like a normal game command
    session.process_command(command)
    
    # Save the updated session
    save_session(session_id, session)
    
    # Get the structured output
    structured_output = session.io_buffer.get_structured_output()
    
    # Clear the message buffer
    session.io_buffer.clear()
    
    # Get the updated combat state
    state = session.get_current_state()

    return jsonify({
        "output": structured_output,
        "state": state,
        "combat": session.get_combat_state()
    })

@app.route("/npcs", methods=["GET"])
def get_npc():
    """Get information about the NPCs in the current location"""
    session_id = request.args.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    return jsonify(session.get_npcs_in_location())

@app.route("/item", methods=["POST"])
def interact_with_item():
    """Interact with an item in the inventory or the environment"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    item = data.get("item", "")
    action = data.get("action", "use")
    
    
    if not item:
        return jsonify({"error": "Item not specified"}), 400
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Build the command for interacting with the item
    command = f"{action} {item}"
    
    # Process the command
    session.process_command(command)
    
    # Save the updated session
    save_session(session_id, session)
    
    # Get the structured output
    structured_output = session.io_buffer.get_structured_output()
    
    # Clear the message buffer
    session.io_buffer.clear()
    
    # Get the updated state
    state = session.get_current_state()
    
    return jsonify({
        "output": structured_output,
        "state": state
    })

@app.route("/saves", methods=["GET"])
def list_saves_legacy():
    """Get the list of available saves"""
    try:
        # Get all the save files
        saves = []
        for file in os.listdir(SAVE_DIR):
            if file.endswith(".json"):
                path = get_save_path(file)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        # Extract the relevant information from the save
                        save_info = {
                            "file_name": file,
                            "character_name": data.get("player", {}).get("name", "Unknown"),
                            "char_class": data.get("player", {}).get("char_class", "Unknown"),
                            "level": data.get("player", {}).get("level", 1),
                            "save_date": data.get("metadata", {}).get("save_date", "Unknown")
                        }
                        saves.append(save_info)
                except Exception as e:
                    # If a file is corrupted, we skip it
                    continue
        
        return jsonify(saves)
    except Exception as e:
        return jsonify({"error": f"Error while listing the saves: {str(e)}"}), 500

@app.route("/log", methods=["GET"])
def get_log():
    """Get the log of recent events"""
    session_id = request.args.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # The session keeps a rolling log of the events the engine emitted.
    max_events = int(request.args.get("max", 50))
    log = session.get_log(max_events)

    return jsonify({
        "events": log
    })

@app.route("/hint", methods=["POST"])
def dungeon_master_hint():
    """Return a hint, optionally rephrased by the configured AI narrator."""
    data = request.json or {}
    session_id = data.get("session_id")

    session, error = get_session_or_error(session_id)
    if error:
        return error

    from ai.hints import generate_hint

    narrator = getattr(getattr(session, "io_buffer", None), "narrator", None)
    memory = getattr(getattr(session, "io_buffer", None), "memory", None)
    result = generate_hint(session.game, narrator=narrator, memory=memory)

    # Keep the hint in the session log so a reload shows it too.
    if isinstance(getattr(session, "event_log", None), list):
        session.event_log.append(
            {"type": "hint", "text": result["hint"], "time": time.time()}
        )
        if len(session.event_log) > 500:
            del session.event_log[:-500]

    return jsonify({"session_id": session_id, **result})


@app.route("/recap", methods=["POST"])
def session_recap():
    """Return a recap, optionally rephrased by the configured AI narrator."""
    data = request.json or {}
    session_id = data.get("session_id")

    session, error = get_session_or_error(session_id)
    if error:
        return error

    from ai.recap import generate_recap

    narrator = getattr(getattr(session, "io_buffer", None), "narrator", None)
    memory = getattr(getattr(session, "io_buffer", None), "memory", None)
    result = generate_recap(
        session.game,
        narrator=narrator,
        memory=memory,
        events=session.event_log,
    )

    # Keep the recap in the session log so a reload shows it too. Recaps are
    # excluded from the recent-event input on the next request.
    if isinstance(getattr(session, "event_log", None), list):
        session.event_log.append(
            {"type": "recap", "text": result["recap"], "time": time.time()}
        )
        if len(session.event_log) > 500:
            del session.event_log[:-500]

    return jsonify({"session_id": session_id, **result})


@app.route("/equipment", methods=["POST"])
def manage_equipment():
    """Manage the player's equipment"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    action = data.get("action", "")  # "equip", "unequip", "examine"
    item = data.get("item", "")
    slot = data.get("slot", "")  # e.g. "weapon", "armor", "ring", etc.
    
    
    if not item:
        return jsonify({"error": "Item not specified"}), 400
    
    if not action:
        return jsonify({"error": "Action not specified"}), 400
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Build the appropriate command based on the requested action
    if action == "equip":
        command = f"equip {item}"
        if slot:
            command += f" {slot}"
    elif action == "unequip":
        command = f"remove {item}"
    elif action == "examine":
        command = f"examine {item}"
    else:
        return jsonify({"error": "Invalid action"}), 400
    
    # Process the command
    session.process_command(command)
    
    # Save the updated session
    save_session(session_id, session)
    
    # Get the structured output
    structured_output = session.io_buffer.get_structured_output()
    
    # Clear the message buffer
    session.io_buffer.clear()
    
    # Get the updated state
    state = session.get_current_state()
    
    return jsonify({
        "output": structured_output,
        "state": state,
        "equipment": state.get("equipment", {})
    })

@app.route("/available_actions", methods=["GET"])
def get_available_actions():
    """Get the actions available in the current context"""
    session_id = request.args.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    state = session.get_current_state()
    state_name = state.get("state", "NoneState")

    # Define different actions depending on the context
    actions_context = {
        "base": ["examine", "pick_up", "talk", "use", "look"],
        "map": [
            "search",
            "sneak",
            "move north",
            "move south",
            "move east",
            "move west",
        ],
        "combat": [
            "attack",
            "defend",
            "aim",
            "take cover",
            "run",
            "use item",
            "use ability",
            "change equipment",
        ],
        "dialogue": ["talk", "ask", "offer", "goodbye"],
        "market": ["shop", "buy", "sell", "examine", "exit"],
        "inventory": ["use", "equip", "drop", "examine"],
        "tavern": [
            "rest",
            "bounties",
            "talk",
            "fight",
            "travel",
            "inventory",
            "map",
            "save",
        ],
        "waystation": [
            "confront",
            "strongbox",
            "rest",
            "underroad",
            "leave",
        ],
        "underroad": ["confront", "cache", "sanctum", "leave"],
        "sanctum": ["amulet", "force", "confront", "vault", "trials", "forge", "leave"],
        "rune_trials": ["begin", "leave"],
        "forge": ["rune_draught", "rune_forged_blade", "rune_ward_plate", "leave"],
        "bounty_board": ["accept", "claim", "leave"],
        "rune_pillar": ["study", "leave"],
        "road_event": ["leave"],
    }

    combat_state = session.get_combat_state()
    if combat_state.get("in_combat"):
        actions = (
            combat_state.get("available_actions")
            or actions_context["combat"]
        )
    elif state_name == "MapState":
        actions = actions_context["map"]
    elif state_name == "DialogueState":
        actions = actions_context["dialogue"]
    elif state_name == "MarketState":
        actions = actions_context["market"]
    elif state_name == "InventoryManagementState":
        actions = actions_context["inventory"]
    elif state_name == "TavernState":
        actions = actions_context["tavern"]
    elif state_name == "WaystationState":
        actions = actions_context["waystation"]
    elif state_name == "UnderroadState":
        underroad = session.game.current_state()
        chooser = getattr(underroad, "available_actions", None)
        actions = (
            chooser()
            if callable(chooser)
            else actions_context["underroad"]
        )
    elif state_name == "SanctumState":
        sanctum = session.game.current_state()
        chooser = getattr(sanctum, "available_actions", None)
        actions = chooser() if callable(chooser) else actions_context["sanctum"]
    elif state_name == "RuneTrialsState":
        trials = session.game.current_state()
        chooser = getattr(trials, "available_actions", None)
        actions = (
            chooser()
            if callable(chooser)
            else actions_context["rune_trials"]
        )
    elif state_name == "ForgeState":
        forge = session.game.current_state()
        chooser = getattr(forge, "available_actions", None)
        actions = (
            chooser()
            if callable(chooser)
            else actions_context["forge"]
        )
    elif state_name == "BountyBoardState":
        actions = actions_context["bounty_board"]
    elif state_name == "RunePillarState":
        actions = actions_context["rune_pillar"]
    elif state_name == "RoadEventState":
        road_event = session.game.current_state()
        chooser = getattr(road_event, "available_actions", None)
        actions = chooser() if callable(chooser) else actions_context["road_event"]
    else:
        actions = actions_context["base"]

    return jsonify({
        "actions": actions,
        "targets": session.get_nearby_targets(),
        "context": state_name
    })

@app.route("/shop", methods=["GET"])
def get_shop():
    """Get the market's purchasable stock and the player's sellable items."""
    session_id = request.args.get("session_id")

    session, error = get_session_or_error(session_id)
    if error:
        return error

    current = session.game.current_state()
    if type(current).__name__ != "MarketState":
        return jsonify({"error": "Shopping is only available in the market."}), 409

    return jsonify(session.get_shop_state())

@app.route("/shop/buy", methods=["POST"])
def shop_buy():
    """Buy one item from the market stock."""
    data = request.json or {}
    session_id = data.get("session_id")
    item_name = data.get("item")
    if not item_name:
        return jsonify({"error": "Item name not provided"}), 400

    session, error = get_session_or_error(session_id)
    if error:
        return error

    current = session.game.current_state()
    if type(current).__name__ != "MarketState":
        return jsonify({"error": "Shopping is only available in the market."}), 409

    result = session.shop_buy(str(item_name))
    save_session(session_id, session)
    structured_output = session.io_buffer.get_structured_output()
    session.io_buffer.clear()

    return jsonify({
        "output": structured_output,
        "state": session.get_current_state(),
        "bought": bool(result.get("success")),
        "message": result.get("message", ""),
        "shop": session.get_shop_state(),
    })

@app.route("/shop/sell", methods=["POST"])
def shop_sell():
    """Sell one non-equipped inventory item."""
    data = request.json or {}
    session_id = data.get("session_id")
    item_name = data.get("item")
    if not item_name:
        return jsonify({"error": "Item name not provided"}), 400

    session, error = get_session_or_error(session_id)
    if error:
        return error

    current = session.game.current_state()
    if type(current).__name__ != "MarketState":
        return jsonify({"error": "Shopping is only available in the market."}), 409

    result = session.shop_sell(str(item_name))
    save_session(session_id, session)
    structured_output = session.io_buffer.get_structured_output()
    session.io_buffer.clear()

    return jsonify({
        "output": structured_output,
        "state": session.get_current_state(),
        "sold": bool(result.get("success")),
        "message": result.get("message", ""),
        "shop": session.get_shop_state(),
    })

@app.route("/forge", methods=["GET"])
def get_forge():
    """Get the Sanctum Forge recipes and resources."""
    session_id = request.args.get("session_id")
    session, error = get_session_or_error(session_id)
    if error:
        return error

    forge = session.get_forge_state()
    if forge is None:
        return jsonify(
            {"error": "The Rune Forge is only available in the Sanctum."}
        ), 409
    return jsonify(forge)


@app.route("/forge/craft", methods=["POST"])
def craft_at_forge():
    """Craft one recipe at the Sanctum Forge."""
    data = request.json or {}
    session_id = data.get("session_id")
    recipe_id = data.get("recipe_id")
    if not recipe_id:
        return jsonify({"error": "Recipe ID not provided"}), 400

    session, error = get_session_or_error(session_id)
    if error:
        return error

    result = session.forge_craft(str(recipe_id))
    save_session(session_id, session)
    structured_output = session.io_buffer.get_structured_output()
    session.io_buffer.clear()

    return jsonify({
        "output": structured_output,
        "state": session.get_current_state(),
        "crafted": bool(result.get("success")),
        "message": result.get("message", ""),
        "forge": session.get_forge_state(),
    })


@app.route("/bounties", methods=["GET"])
def get_bounties():
    """Get the tavern bounty board."""
    session_id = request.args.get("session_id")
    session, error = get_session_or_error(session_id)
    if error:
        return error

    current = session.game.current_state()
    if type(current).__name__ not in {"TavernState", "BountyBoardState"}:
        return jsonify(
            {"error": "The bounty board is only available in the tavern."}
        ), 409

    return jsonify(session.get_bounty_state())

@app.route("/bounties/accept", methods=["POST"])
def accept_bounty_contract():
    """Accept one bounty contract."""
    data = request.json or {}
    session_id = data.get("session_id")
    bounty_id = data.get("bounty_id")
    if not bounty_id:
        return jsonify({"error": "Bounty ID not provided"}), 400

    session, error = get_session_or_error(session_id)
    if error:
        return error

    current = session.game.current_state()
    if type(current).__name__ not in {"TavernState", "BountyBoardState"}:
        return jsonify(
            {"error": "The bounty board is only available in the tavern."}
        ), 409

    accepted = session.bounty_accept(str(bounty_id))
    save_session(session_id, session)
    structured_output = session.io_buffer.get_structured_output()
    session.io_buffer.clear()

    return jsonify({
        "output": structured_output,
        "state": session.get_current_state(),
        "accepted": bool(accepted),
        "bounties": session.get_bounty_state(),
    })

@app.route("/bounties/claim", methods=["POST"])
def claim_bounty_contract():
    """Claim one ready bounty contract."""
    data = request.json or {}
    session_id = data.get("session_id")
    bounty_id = data.get("bounty_id")
    if not bounty_id:
        return jsonify({"error": "Bounty ID not provided"}), 400

    session, error = get_session_or_error(session_id)
    if error:
        return error

    current = session.game.current_state()
    if type(current).__name__ not in {"TavernState", "BountyBoardState"}:
        return jsonify(
            {"error": "The bounty board is only available in the tavern."}
        ), 409

    claimed = session.bounty_claim(str(bounty_id))
    save_session(session_id, session)
    structured_output = session.io_buffer.get_structured_output()
    session.io_buffer.clear()

    return jsonify({
        "output": structured_output,
        "state": session.get_current_state(),
        "claimed": bool(claimed),
        "bounties": session.get_bounty_state(),
    })

@app.route("/dialogue", methods=["POST"])
def manage_dialogue():
    """Manage dialogue with an NPC"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    npc = data.get("npc", "")
    option = data.get("option", "")
    
    
    if not npc:
        return jsonify({"error": "NPC not specified"}), 400
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Build the dialogue command
    if option:
        command = f"talk {npc} {option}"
    else:
        command = f"talk {npc}"
    
    # Process the command
    session.process_command(command)
    
    # Save the updated session
    save_session(session_id, session)
    
    # Get the structured output
    structured_output = session.io_buffer.get_structured_output()
    
    # Clear the message buffer
    session.io_buffer.clear()
    
    # Get the updated state
    state = session.get_current_state()
    
    dialogue = session.get_dialogue_state()

    return jsonify({
        "output": structured_output,
        "state": state,
        "dialogue": dialogue,
        "options_dialogue": dialogue.get("options", []),
    })

@app.route("/explore", methods=["POST"])
def explore_environment():
    """Explore the surrounding environment"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Run a "look" or "explore" command
    session.process_command("look")
    
    # Save the updated session
    save_session(session_id, session)
    
    # Get the structured output
    structured_output = session.io_buffer.get_structured_output()
    
    # Clear the message buffer
    session.io_buffer.clear()
    
    # Get the updated state and the real nearby targets
    state = session.get_current_state()
    targets = session.get_nearby_targets()

    return jsonify({
        "output": structured_output,
        "state": state,
        "items": targets["items"],
        "exits": targets["directions"],
        "npc": targets["npc"],
    })

@app.route("/preferences", methods=["POST"])
def save_preferences():
    """Save the user's preferences"""
    # Extract the data from the request
    data = request.json or {}
    session_id = data.get("session_id")
    preferences = data.get("preferences", {})
    
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Save the preferences in the session context
    # This operation assumes GameState has a way to manage preferences
    try:
        session.save_preferences(preferences)
        save_session(session_id, session)
        return jsonify({"message": "Preferences saved successfully"})
    except TypeError as e:
        return jsonify({"error": f"Invalid preferences: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Error while saving the preferences: {str(e)}"}), 500

@app.route("/delete_save", methods=["POST"])
def delete_save():
    """Delete a save"""
    # Extract the data from the request
    data = request.json or {}
    file_name = data.get("file_name")
    
    if not file_name:
        return jsonify({"error": "File name not provided"}), 400
    
    # Use the function from the config module
    try:
        if delete_save_file(file_name):
            return jsonify({"message": f"Save {file_name} deleted successfully"})
        else:
            return jsonify({"error": "Save file not found"}), 404
    except Exception as e:
        logger.error(f"Error while deleting the save: {str(e)}")
        return jsonify({"error": f"Error while deleting the save: {str(e)}"}), 500

@app.route("/notifications", methods=["GET"])
def get_notifications():
    """Get the notifications for the current session"""
    session_id = request.args.get("session_id")
    
    
    # Initialize the notifications array if it does not exist
    if session_id not in system_notifications:
        system_notifications[session_id] = []
    
    # Filter the notifications based on the parameters
    only_unread = request.args.get("only_unread", "true").lower() == "true"
    type = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    
    notifications = system_notifications[session_id]
    
    # Apply the filters
    if only_unread:
        notifications = [n for n in notifications if not n.get("read", False)]
    
    if type:
        notifications = [n for n in notifications if n.get("type") == type]
    
    # Limit the number of notifications
    notifications = notifications[-limit:] if len(notifications) > limit else notifications
    
    return jsonify({
        "notifications": notifications,
        "total_read_not": len([n for n in system_notifications[session_id] if not n.get("read", False)])
    })

@app.route("/read_notification", methods=["POST"])
def read_notification():
    """Mark a notification as read"""
    data = request.json or {}
    session_id = data.get("session_id")
    notification_id = data.get("notification_id")
    all = data.get("all", False)
    
    
    if session_id not in system_notifications:
        return jsonify({"error": "No notifications found for this session"}), 404
    
    if all:
        # Mark all the notifications as read
        for notification in system_notifications[session_id]:
            notification["read"] = True
        return jsonify({"message": "All notifications marked as read"})
    
    if not notification_id:
        return jsonify({"error": "Notification ID not provided"}), 400
    
    # Look for the specific notification
    for notification in system_notifications[session_id]:
        if notification["id"] == notification_id:
            notification["read"] = True
            return jsonify({"message": "Notification marked as read"})
    
    return jsonify({"error": "Notification not found"}), 404

@app.route("/asset/<path:file_name>", methods=["GET"])
def get_asset(file_name):
    """Get a graphic asset"""
    return send_from_directory(str(ASSETS_DIR), file_name)

@app.route("/assets_info", methods=["GET"])
def get_assets_info():
    """Get information about the available assets"""
    asset_type = request.args.get("type")  # characters, environments, items, enemies

    # Use the data manager to load the asset information
    assets = get_data_manager().get_asset_info(asset_type)

    return jsonify({
        "assets": assets
    })


@app.route("/app")
def web_client():
    """Redirect to the trailing-slash form so relative asset URLs resolve."""
    if not (FRONTEND_DIR / "index.html").exists():
        return jsonify({"error": "Web client not installed"}), 404
    return redirect("/app/")


@app.route("/app/")
def web_client_index():
    """Serve the optional dependency-free web client."""
    if not (FRONTEND_DIR / "index.html").exists():
        return jsonify({"error": "Web client not installed"}), 404
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/app/<path:file_name>")
def web_client_file(file_name):
    """Serve the web client's static files."""
    return send_from_directory(str(FRONTEND_DIR), file_name)

@app.route("/tutorial", methods=["GET"])
def get_tutorial():
    """Get information about the available tutorials"""
    session_id = request.args.get("session_id")
    type = request.args.get("type")  # e.g. "combat", "inventory", "dialogue"
    
    
    # Check that the session exists
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Load the tutorials from the external file using the data manager
    tutorial = get_data_manager().get_tutorials()
    
    # If a type is specified, return only that tutorial
    if type and type in tutorial:
        return jsonify(tutorial[type])
    
    # Otherwise, return all the tutorials
    return jsonify(tutorial)

@app.route("/achievements", methods=["GET"])
def get_achievements():
    """Get the player's achievements"""
    session_id = request.args.get("session_id")
    
    
    # Check that the session exists
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # In a real implementation, these data would be extracted from the game state
    state = session.get_current_state()
    
    # Copy before annotating: DataManager caches this list, and mutating the
    # cache would leak one session's unlock state into every other session.
    all_achievements = [dict(achievement) for achievement in get_data_manager().get_achievements()]
    
    # Get the achievements unlocked by the player
    unlocked_achievements = state.get("achievements", [])
    
    # Update the unlock status for each achievement
    for achievement in all_achievements:
        achievement["unlocked"] = achievement["id"] in unlocked_achievements
        
        # If it is unlocked, add the unlock date
        if achievement["unlocked"] and "timestamp_achievements" in state:
            timestamp = state["timestamp_achievements"].get(achievement["id"])
            if timestamp:
                achievement["unlock_date"] = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify({
        "achievements": all_achievements,
        "total": len(all_achievements),
        "unlocked": len(unlocked_achievements)
    })


@app.route("/reputation", methods=["GET"])
def get_reputation():
    """Get faction standing and the current merchant discount."""
    session_id = request.args.get("session_id")

    session, error = get_session_or_error(session_id)
    if error:
        return error

    return jsonify(session.get_reputation_state())


@app.route("/campaign", methods=["GET"])
def get_campaign():
    """Get main-story chapters and endgame progression."""
    session_id = request.args.get("session_id")

    session, error = get_session_or_error(session_id)
    if error:
        return error

    return jsonify(session.get_campaign_state())

@app.route("/item_details", methods=["GET"])
def get_item_details():
    """Get details about a specific item"""
    session_id = request.args.get("session_id")
    item_id = request.args.get("item_id")
    object_name = request.args.get("object_name")
    
    
    if not item_id and not object_name:
        return jsonify({"error": "Item ID or item name not provided"}), 400
    
    # Check that the session exists
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    # Get the player's inventory
    state = session.get_current_state()
    inventory = state.get("inventory", [])
    
    # The state view returns the inventory as plain name strings, so those entries carry no
    # "type" or "description" to report. Prefer the player's real item objects (they do),
    # fall back to the name list, then normalise to a dict -- the rest of this handler
    # expects one (item.copy(), item.get(...)).
    player = getattr(session.game, "player", None)
    objects = list(getattr(player, "inventory", None) or [])
    matched = None
    if objects:
        for obj in objects:
            obj_name = obj if isinstance(obj, str) else getattr(obj, "name", None)
            if item_id and getattr(obj, "id", None) == item_id:
                matched = obj
                break
            if object_name and obj_name == object_name:
                matched = obj
                break
    elif object_name and object_name in inventory:
        matched = object_name

    if matched is None:
        return jsonify({"error": "Item not found in the inventory"}), 404

    if isinstance(matched, str):
        item = {"name": matched}
    elif hasattr(matched, "to_dict"):
        item = matched.to_dict()
    else:
        item = {"name": str(matched)}
    
    if not item:
        return jsonify({"error": "Item not found in the inventory"}), 404
    
    # If the item was found, enrich the details
    detailed_item = item.copy()
    
    # Add information about how to get the item's asset
    detailed_item["asset_url"] = f"/asset/items/{item.get('asset', 'item_default.png')}"
    
    # Add the possible uses of the item
    detailed_item["uses"] = []
    
    if item.get("type") == "weapon":
        detailed_item["uses"].append({"action": "equip", "description": "Equip this weapon"})
        detailed_item["uses"].append({"action": "examine", "description": "Examine the weapon in detail"})
    elif item.get("type") in (
        "heal",
        "light_heal",
        "grave_heal",
        "buff",
        "poison",
        "bomb",
        "key",
    ):
        detailed_item["uses"].append({"action": "use", "description": "Use this item"})
        detailed_item["uses"].append({"action": "examine", "description": "Examine the item in detail"})
    elif item.get("type") in ("armor", "accessory"):
        detailed_item["uses"].append({"action": "equip", "description": "Equip this item"})
        detailed_item["uses"].append({"action": "examine", "description": "Examine the item in detail"})
    
    # Always add the option to discard
    detailed_item["uses"].append({"action": "drop", "description": "Drop the item"})
    
    return jsonify(detailed_item)

@app.route("/abilities", methods=["GET"])
def get_ability():
    """Get the player's abilities"""
    session_id = request.args.get("session_id")
    
    
    # Check that the session exists
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    return jsonify(session.get_abilities())

@app.route("/use_ability", methods=["POST"])
def use_ability():
    """Use a player ability"""
    data = request.json or {}
    session_id = data.get("session_id")
    ability_id = data.get("ability_id")
    ability_name = data.get("ability_name")
    target = data.get("target", "")
    
    
    if not ability_id and not ability_name:
        return jsonify({"error": "Ability ID or ability name not provided"}), 400
    
    # Check that the session exists
    session, error = get_session_or_error(session_id)
    if error:
        return error
    
    from core.abilities import resolve_ability

    name, definition = resolve_ability(
        session.game.player, ability_name or ability_id
    )
    if not name:
        return jsonify({"error": "Ability not found"}), 404

    used = session.use_ability(name)
    save_session(session_id, session)

    current_state = session.get_current_state()
    state_name = "NoneState"
    if session.game.current_state():
        state_name = type(session.game.current_state()).__name__

    structured_output = session.io_buffer.get_structured_output()
    session.io_buffer.clear()

    return jsonify({
        "output": structured_output,
        "state": current_state,
        "state_name": state_name,
        "end": not session.game.active,
        "used": used,
        "combat": session.get_combat_state(),
        "ability": {
            "name": name,
            "mana_cost": definition.get("mana_cost", 0),
        },
    })

@app.route("/export_save", methods=["POST"])
def export_save():
    """Export a save as a downloadable file"""
    data = request.json or {}
    session_id = data.get("session_id")
    file_name = data.get("file_name")
    
    
    # Never let a request escape the saves directory
    file_name = os.path.basename(file_name)
    if not file_name:
        # Generate a file name based on the date and time
        file_name = f"save_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Make sure the file name has the .json extension
    if not file_name.endswith(".json"):
        file_name += ".json"

    # Check that the session exists
    session, error = get_session_or_error(session_id)
    if error:
        return error

    # Save the file temporarily
    temp_path = get_save_path(file_name)
    try:
        if not session.save(str(temp_path)):
            return jsonify({"error": "The game cannot be saved in the current state"}), 409

        # Send the file to the client
        return send_file(
            str(temp_path),
            as_attachment=True,
            download_name=file_name,
            mimetype="application/json"
        )
    except Exception as e:
        return jsonify({"error": f"Error while exporting: {str(e)}"}), 500

@app.route("/import_save", methods=["POST"])
def import_save():
    """Import a save from a file"""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.endswith(".json"):
        return jsonify({"error": "The file must be in JSON format"}), 400
    
    # Save the uploaded file under a unique, sanitized name
    original_name = os.path.basename(file.filename)
    file_name = f"import_{uuid4().hex[:8]}_{original_name}"
    path = get_save_path(file_name)

    try:
        file.save(str(path))

        # Load the save to verify that it is valid
        with open(path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        # Create a new session ID
        session_id = str(uuid4())
        
        # Create a player from the save
        from entities.player import Player
        player = Player.from_dict(saved_data["player"])
        
        # Create a temporary session with a null state
        session = GameState(player, None)
        
        # Load the full game (including the state stack)
        if session.game.load(str(path)):
            # Store the session
            active_sessions[session_id] = session
            save_session(session_id, session)

            # Get the initial state
            state = session.get_current_state()

            return jsonify({
                "session_id": session_id,
                "message": f"Save imported from {original_name}",
                "player": session.get_player_summary(),
                "state": state,
            })
        else:
            # If loading fails, delete the file
            os.remove(path)
            return jsonify({"error": "The save file is not valid"}), 400
        
    except Exception as e:
        # If there is an error, delete the file if it exists
        if os.path.exists(path):
            os.remove(path)
        return jsonify({"error": f"Error while importing: {str(e)}"}), 500

@app.route("/list_saves", methods=["GET"])
def list_saves():
    """Return the list of available saves"""
    try:
        # Get all the save files
        saves = []
        for file in list_save_files():
            path = get_save_path(file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Extract the relevant information
                timestamp = data.get("timestamp", 0)
                version = data.get("game_version", "unknown")
                player_name = data.get("player", {}).get("name", "Unknown")
                level = data.get("player", {}).get("level", 1)
                char_class = data.get("player", {}).get("char_class", "unknown")
                map = data.get("current_map", "unknown")
                
                # Convert the timestamp into a readable date
                datetime_now = datetime.datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M:%S")
                
                saves.append({
                    "file": file,
                    "player": player_name,
                    "level": level,
                    "char_class": char_class,
                    "map": map,
                    "data": datetime_now,
                    "version": version
                })
            except Exception as e:
                # Corrupted or invalid save
                saves.append({
                    "file": file,
                    "player": "Corrupted save",
                    "error": str(e)
                })
                
        return jsonify({"saves": saves})
    except Exception as e:
        logger.error(f"Error while reading the saves: {str(e)}")
        return jsonify({"error": f"Error while reading the saves: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0") 