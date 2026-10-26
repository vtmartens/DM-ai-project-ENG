from entities.player import Player
from states.combat import CombatState
from states.menu import MenuState
from core.game import Game
from states.tavern import TavernState
from states.map_selection_state import MapSelectionState
from util.helpers import press_enter
from items.item import Item
from entities.entity import Entity
from world.map import Map
from world.map_manager import MapManager
from core.io_interface import TerminalIO
from ai.io import attach_game, create_game_io
import json
import os


def get_available_classes():
    """Gets the list of available classes from the JSON file"""
    file_path = os.path.join("data", "classes", "classes.json")
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            classes = json.load(file)
            return list(classes.keys())
    except (FileNotFoundError, json.JSONDecodeError):
        # On error, return the default classes
        return ["fighter", "wizard", "rogue"]


def request_class(io_handler):
    """Asks the user to choose a class from those available"""
    available_classes = get_available_classes()
    
    io_handler.show_message("Available classes:")
    for i, char_class in enumerate(available_classes, 1):
        io_handler.show_message(f"{i}. {char_class}")
        
    while True:
        selection = io_handler.request_input("Choose a class (number or name): ")
        
        # If the user entered a number
        if selection.isdigit():
            index = int(selection) - 1
            if 0 <= index < len(available_classes):
                return available_classes[index]
        # If the user entered the class name
        elif selection.lower() in [c.lower() for c in available_classes]:
            for c in available_classes:
                if c.lower() == selection.lower():
                    return c
                    
        io_handler.show_message("Invalid choice. Try again.")


def main():
    # Create an I/O object that will be used throughout the application.
    # create_game_io only wraps it when AI narration is enabled and configured.
    io_handler = create_game_io(TerminalIO())

    # Create a temporary game object for the initial messages
    game_temp = Game(None, None, io_handler, temporary=True)
    attach_game(io_handler, game_temp)
    
    game_temp.io.show_message("Welcome, adventurer!")
    
    # Show the initial menu
    game_temp.io.show_message("1. New Game")
    game_temp.io.show_message("2. Load Game")
    selection = game_temp.io.request_input("> ")

    if selection == "2":
        # Create a temporary game just for loading, passing the io_handler
        game_temp = Game(None, None, io_handler, temporary=True)
        attach_game(io_handler, game_temp)

        if game_temp.load():
            # If loading succeeded, create the real game with the initial state
            game = Game(game_temp.player, None, io_handler)
            attach_game(io_handler, game)
            # Set the current map
            game.map_manager.set_current_map(game.player.current_map)
            # Load the map selection state
            game.push_state(MapSelectionState(game))
            
            # Set the game context on the player
            if hasattr(game.player, 'set_game_context'):
                game.player.set_game_context(game)
        else:
            # If loading fails, create a new game
            game_temp.io.show_message("Creating a new game...")
            name = game_temp.io.request_input("What is your name? ")
            char_class = request_class(game_temp.io)
            player = Player(name, char_class)
            # Create the game with the player
            game = Game(player, None, io_handler)
            attach_game(io_handler, game)
            # Load the map selection state
            game.push_state(MapSelectionState(game))
            
            # Set the game context on the player
            if hasattr(game.player, 'set_game_context'):
                game.player.set_game_context(game)
    else:
        # Request initial input
        name = game_temp.io.request_input("What is your name? ")
        char_class = request_class(game_temp.io)
        player = Player(name, char_class)
        
        # Create the game with the player
        game = Game(player, None, io_handler)
        attach_game(io_handler, game)

        # Welcome message
        game.io.show_message(f"Welcome {player.name} the {player.char_class}! Your adventure is about to begin.")
        game.io.show_message("Choose where you want to go to begin your adventure...")
        press_enter(game)

        # Load the map selection state
        game.push_state(MapSelectionState(game))

        # Set the game context on the player
        if hasattr(game.player, 'set_game_context'):
            game.player.set_game_context(game)
    
    game.run()
    
    # End of the game
    game.io.show_message("\n=== End of the show! ===")
    press_enter(game)

if __name__ == "__main__":
    main()
