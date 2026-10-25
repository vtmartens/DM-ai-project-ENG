import os
import pathlib
import logging
from pathlib import Path

# Configure the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Definition of the main folders
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = BASE_DIR / "data"
SAVE_DIR = BASE_DIR / "saves"
SESSIONS_DIR = BASE_DIR / "sessions"
BACKUPS_DIR = BASE_DIR / "backup"

# Make sure all the directories exist
for directory in [DATA_DIR, SAVE_DIR, SESSIONS_DIR, BACKUPS_DIR]:
    directory.mkdir(exist_ok=True, parents=True)

# Constants for the save paths
DEFAULT_SAVE_PATH = SAVE_DIR / "save.json"
DEFAULT_MAP_SAVE_PATH = SAVE_DIR / "maps_save.json"
DEFAULT_SESSION_PREFIX = "session_"
DEFAULT_BACKUP_PREFIX = "backup_"

# Current save format version
SAVE_FORMAT_VERSION = "1.0.0"

def get_save_path(filename=None):
    """
    Gets the full path for a save file.
    
    Args:
        filename (str, optional): Name of the save file
        
    Returns:
        Path: Full path of the save file
    """
    if not filename:
        return DEFAULT_SAVE_PATH
    
    # If the file name has no .json extension, add it
    # Accept a Path as well as a str: Game.save() resolves the path and passes the
    # Path on, and Path has no .lower().
    filename = str(filename)
    if not filename.lower().endswith('.json'):
        filename += '.json'
    
    return SAVE_DIR / filename

def get_standardized_paths(filename=None):
    """
    Gets all the standardized paths for a file.
    
    Args:
        filename (str, optional): Name of the file
        
    Returns:
        dict: Dictionary with all the standardized paths
    """
    # Normalize the file name
    filename = str(filename) if filename else filename
    if filename and not filename.lower().endswith('.json'):
        filename += '.json'
    
    base_filename = filename or "save.json"
    map_filename = "maps_" + base_filename if filename else "maps_save.json"
    
    return {
        "save": SAVE_DIR / base_filename,
        "maps": SAVE_DIR / map_filename,
        "backup_dir": BACKUPS_DIR,
        "data_dir": DATA_DIR,
        "sessions_dir": SESSIONS_DIR
    }

def get_backup_path(original_filename):
    """
    Generates a path for the backup of a file.
    
    Args:
        original_filename (str): Name of the original file
        
    Returns:
        Path: Full path of the backup file
    """
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.basename(original_filename)
    
    # Remove the extension
    name, ext = os.path.splitext(filename)
    backup_name = f"{DEFAULT_BACKUP_PREFIX}{name}_{timestamp}{ext}"
    
    return BACKUPS_DIR / backup_name

def create_backup(filepath):
    """
    Creates a backup of the specified file.
    
    Args:
        filepath (str or Path): Path of the file to copy
        
    Returns:
        Path: Path of the backup file, None if an error occurred
    """
    import shutil
    
    source_path = Path(filepath)
    if not source_path.exists():
        logger.error(f"Cannot create backup: file {filepath} does not exist")
        return None
    
    backup_path = get_backup_path(source_path)
    
    try:
        # Make sure the backup directory exists
        backup_path.parent.mkdir(exist_ok=True, parents=True)
        
        # Copy the file
        shutil.copy2(source_path, backup_path)
        logger.info(f"Backup creato: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Error while creating the backup: {e}")
        return None

def get_session_path(session_id):
    """
    Gets the full path for a session file.
    
    Args:
        session_id (str): Session ID
        
    Returns:
        Path: Full path of the session file
    """
    return SESSIONS_DIR / f"{DEFAULT_SESSION_PREFIX}{session_id}.pickle"

def list_save_files():
    """
    Lists all the available save files.
    
    Returns:
        list: List of save file names
    """
    return [f.name for f in SAVE_DIR.glob("*.json")]

def list_backup_files():
    """
    Lists all the available backup files.
    
    Returns:
        list: List of backup file names
    """
    return [f.name for f in BACKUPS_DIR.glob("*.json")]

def validate_save_data(data):
    """
    Validates the contents of a save file.
    
    Args:
        data (dict): Save data to validate
        
    Returns:
        tuple: (validity, error message)
    """
    if not data:
        return False, "Empty or invalid save file"
    
    # Check the main fields
    required_fields = ["player", "game_version"]
    for field in required_fields:
        if field not in data:
            return False, f"Missing field '{field}' in the save file"
    
    # Check the player data
    player = data.get("player", {})
    if not isinstance(player, dict):
        return False, "The player data is not valid"
        
    player_fields = ["name", "char_class", "hp", "hp_max"]
    for field in player_fields:
        if field not in player:
            return False, f"Missing field '{field}' in the player data"
    
    # Check the version
    version = data.get("game_version", "unknown")
    if version != SAVE_FORMAT_VERSION:
        logger.warning(f"Save version ({version}) differs from the current one ({SAVE_FORMAT_VERSION})")
        # Does not block loading, just a warning
    
    return True, ""

def migrate_save_data(data):
    """
    Migrates the data to the current version if necessary.
    
    Args:
        data (dict): Save data
        
    Returns:
        dict: Data migrated to the current version
    """
    origin_version = data.get("game_version", "0.0.0")
    
    # If already at the current version, do nothing
    if origin_version == SAVE_FORMAT_VERSION:
        return data
        
    logger.info(f"Migrating data from version {origin_version} to {SAVE_FORMAT_VERSION}")

    # Migration from 0.9.0 to 1.0.0
    if origin_version == "0.9.0" and SAVE_FORMAT_VERSION == "1.0.0":
        # Update the format
        data["game_version"] = "1.0.0"
        
        # Add any missing fields
        if "player" in data and isinstance(data["player"], dict):
            player = data["player"]
            if "accessories" not in player:
                player["accessories"] = []
                
    # Other migrations to be added in the future
    
    return data

def delete_save_file(filename):
    """
    Deletes a save file.
    
    Args:
        filename (str): Name of the file to delete
        
    Returns:
        bool: True if the deletion succeeded, False otherwise
    """
    file_path = get_save_path(filename)
    try:
        if file_path.exists():
            # First create a backup
            create_backup(file_path)
            # Then delete
            file_path.unlink()
            logger.info(f"Save file deleted: {file_path}")
            return True
        else:
            logger.warning(f"Save file not found: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error while deleting file {file_path}: {e}")
        return False

def clean_old_backups(max_backups=20):
    """
    Removes the oldest backups if there are too many.
    
    Args:
        max_backups (int): Maximum number of backups to keep
    """
    backup_files = list(BACKUPS_DIR.glob("*.json"))
    
    # Sort by modification date (oldest first)
    backup_files.sort(key=lambda f: f.stat().st_mtime)
    
    # Remove the oldest backups if necessary
    if len(backup_files) > max_backups:
        files_to_remove = backup_files[:(len(backup_files) - max_backups)]
        for file in files_to_remove:
            try:
                file.unlink()
                logger.info(f"Removed old backup: {file.name}")
            except Exception as e:
                logger.error(f"Error while removing backup {file.name}: {e}") 