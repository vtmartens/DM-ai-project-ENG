from states.base_state import BaseGameState
from util.helpers import press_enter
from entities.npc import NPC
from states.dialogue import DialogueState
from entities.player import Player
from states.inventory_management import InventoryManagementState
from items.interactive_object import Chest, Lever, Door, InteractiveObject, Trap, BreakableObject
from items.item import Item  # Make sure this import is correct
from states.ability_check import AbilityCheckState
from world.map import Map
from world.map_manager import MapManager
from core.io_interface import GameIO  # Correct import for the IO interface
from util.data_manager import get_data_manager
import logging


class MarketState(BaseGameState):
    """Class representing the market state"""

    def __init__(self, game):
        super().__init__(game)
        self.state_name = "market"
        # Load the NPCs specific to the market
        self.present_npcs = {
            "Herald": NPC("Herald"),
            "Violet": NPC("Violet"),
            "Gundren": NPC("Gundren")
        }
        self.active_npc_name = None
        self.conversation_state = "start"
        self.previous_state = None

        # Initialize menu and commands
        self._init_commands()

        # Attributes for asynchronous handling
        self.phase = "main_menu"
        self.last_input = None
        self.contextual_data = {}  # To store data between multiple phases

        # Add the market's interactive objects
        self.interactive_objects = {
            "stall": InteractiveObject("Stall", "A stall of used goods.", "open", position="market"),
            "chest_merchant": Chest("Merchant's Chest", "An iron chest with a sturdy lock.",
                                   content=[Item("Amulet", "accessory", {"luck": 1}, 10)],
                                   requires_key=True, position="market"),
            "door_magazzino": Door("Warehouse Door", "A door that leads to the market's warehouse.",
                                    state="closed", requires_key=True, position="market",
                                    destination_position="warehouse"),
            "secret_lever": Lever("Hidden Lever", "A lever hidden under the counter.", position="market")
        }

        # Link the lever to the warehouse door
        self.interactive_objects["secret_lever"].link_item("door", self.interactive_objects["door_magazzino"])

        # NEW OBJECT 1: Ancient Statue with several required abilities
        ancient_statue = InteractiveObject("Ancient Statue", "A stone statue depicting a merchant. It looks very old.", state="normal", position="market")

        # Configure descriptions for various states
        ancient_statue.set_state_description("normal", "A stone statue depicting a merchant. It looks very old.")
        ancient_statue.set_state_description("examined", "Looking carefully, you notice strange symbols carved into the base of the statue.")
        ancient_statue.set_state_description("deciphered", "The symbols on the statue seem to indicate the location of a hidden treasure.")
        ancient_statue.set_state_description("rotated", "The statue has been rotated. You hear a click coming from the floor.")

        # Define the possible transitions
        ancient_statue.add_transition("normal", "examined")
        ancient_statue.add_transition("examined", "deciphered")
        ancient_statue.add_transition("deciphered", "rotated")
        ancient_statue.add_transition("rotated", "normal")

        # Link abilities to the transitions
        ancient_statue.request_ability("perception", "examined", 12,
                                      "You study the statue carefully and notice small symbols carved into the base.")
        ancient_statue.request_ability("history", "deciphered", 15,
                                      "Thanks to your knowledge of history, you understand that the symbols tell of a hidden treasure.")
        ancient_statue.request_ability("strength", "rotated", 14,
                                      "With a great effort, you manage to rotate the heavy statue, revealing a small crack in the floor.")

        # Link a game event to the "ruotata" state
        ancient_statue.link_event("rotated", lambda game: game.unlock_area("merchant_crypt"))

        # Add the statue to the market
        self.interactive_objects["ancient_statue"] = ancient_statue

        # NEW OBJECT 2: Shelf with special goods
        shelf_goods = InteractiveObject("Goods Shelf", "A shelf full of exotic goods.", state="untouched", position="market")

        # Configure descriptions for various states
        shelf_goods.set_state_description("untouched", "A shelf full of exotic goods from various lands.")
        shelf_goods.set_state_description("inspected", "Among the various goods, you notice a small box hidden behind some fabrics.")
        shelf_goods.set_state_description("moved", "You moved some items aside, revealing a decorated box.")
        shelf_goods.set_state_description("open", "The box is open, revealing a map of an unknown place.")

        # Define the possible transitions
        shelf_goods.add_transition("untouched", "inspected")
        shelf_goods.add_transition("inspected", "moved")
        shelf_goods.add_transition("moved", "open")

        # Link abilities to the transitions
        shelf_goods.request_ability("perception", "inspected", 10,
                                        "Looking among the displayed goods, you notice something unusual...")
        shelf_goods.request_ability("investigation", "moved", 12,
                                        "You carefully move some items aside, revealing a small decorated box.")
        shelf_goods.request_ability("dexterity", "open", 13,
                                        "With your nimble fingers you manage to open the box's locking mechanism.")

        # Define an event for when the box is opened
        def map_reward(game):
            map = Item("Treasure Map", "map", {}, 50, "A map showing the location of a hidden treasure.")
            game.player.add_item(map)
            game.io.show_message("You obtained a Treasure Map!")

        shelf_goods.link_event("open", map_reward)

        # Add the shelf to the market
        self.interactive_objects["shelf_goods"] = shelf_goods

        # NEW OBJECT 3: Magic Fountain
        fountain = InteractiveObject("Magic Fountain", "A small decorative fountain in the center of the market.", state="inactive", position="market")

        # Configure descriptions for various states
        fountain.set_state_description("inactive", "A small decorative fountain that seems to have not worked for a long time.")
        fountain.set_state_description("examined", "You notice arcane symbols carved on the rim of the fountain.")
        fountain.set_state_description("activated", "The fountain lights up and water begins to flow, giving off a pale blue glow.")
        fountain.set_state_description("purified", "The fountain's water gives off a golden glow and seems to have healing properties.")

        # Define the possible transitions
        fountain.add_transition("inactive", "examined")
        fountain.add_transition("examined", "activated")
        fountain.add_transition("activated", "purified")
        fountain.add_transition("purified", "inactive")

        # Link abilities to the transitions
        fountain.request_ability("arcana", "examined", 13,
                                "Studying the fountain, you recognize ancient arcane symbols of water and energy.")
        fountain.request_ability("intelligence", "activated", 14,
                                "Recalling an ancient spell, you speak the words that activate the fountain.")
        fountain.request_ability("religion", "purified", 15,
                                "With a prayer of purification, the fountain's water changes color, turning golden.")

        # Define events for the various states
        def drink_healer_water(game):
            game.io.show_message("You drink the water from the fountain and feel revitalized!")
            game.player.heal(10)

        fountain.link_event("purified", drink_healer_water)

        # Add the fountain to the market
        self.interactive_objects["magic_fountain"] = fountain

        # Attribute to track map display
        self.show_map = False

        # Movement directions
        self.directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0)
        }

    def run(self, game):
        # If this is the first visit to the market, initialize the position and populate the map
        if not hasattr(self, 'first_visit_completed'):
            map = game.map_manager.get_map("market")
            if map:
                game.map_manager.set_current_map("market")
                x, y = map.player_start_position
                game.player.set_position("market", x, y)
                # Populate the map with interactive objects and NPCs
                game.map_manager.transfer_items_from_state("market", self)
            self.first_visit_completed = True

        # Asynchronous handling based on the current phase
        if self.phase == "main_menu":
            self._main_show_menu(game)
        elif self.phase == "buy_potion":
            self._buy_potion(game)
        elif self.phase == "item_sale_list":
            self._sell_item_list(game)
        elif self.phase == "confirm_item_sale":
            self._sell_item_confirm(game)
        elif self.phase == "npc_talk_list":
            self._talk_npc_list(game)
        elif self.phase == "npc_fight_list":
            self._fight_npc_list(game)
        elif self.phase == "confirm_npc_fight":
            self._fight_npc_confirm(game)
        elif self.phase == "explore_items_list":
            self._explore_items_list(game)
        elif self.phase == "interact_with_item":
            self._interact_item(game)
        elif self.phase.startswith("ability_check"):
            # Handling delegated to AbilityCheckState
            game.push_state(AbilityCheckState())
            self.phase = "main_menu"  # Return to the menu afterwards
        elif self.phase == "display_map":
            self._display_map(game)
        elif self.phase == "move_map":
            self._move_on_map(game)
        elif self.phase == "interact_with_environment":
            self._interact_environment(game)
        else:
            # Unrecognized phase, return to the main menu
            self.phase = "main_menu"
            self.run(game)

    def _main_show_menu(self, game):
        game.io.show_message("\n=== MARKET ===")
        game.io.show_message("1. Buy potion (5 gold)")
        game.io.show_message("2. Sell item")
        game.io.show_message("3. Talk to a merchant")
        game.io.show_message("4. Challenge a merchant")
        game.io.show_message("5. Manage inventory")
        game.io.show_message("6. Explore objects in the market")
        game.io.show_message("7. Ability check")
        game.io.show_message("8. Display map")
        game.io.show_message("9. Move on the map")
        game.io.show_message("10. Interact with the environment")
        game.io.show_message("11. Travel to another area")

        selection_input = game.io.request_input("\nWhat do you want to do? ")
        self.last_input = selection_input

        # Process the command
        if not selection_input.isdigit():
            selection = self._process_command_market(selection_input)
        else:
            selection = selection_input

        # Set the next phase based on the choice
        if selection == "1":
            self.phase = "buy_potion"
        elif selection == "2":
            self.phase = "item_sale_list"
        elif selection == "3":
            self.phase = "npc_talk_list"
        elif selection == "4":
            self.phase = "npc_fight_list"
        elif selection == "5":
            game.push_state(InventoryManagementState())
            # We stay in the main menu upon return
        elif selection == "6":
            self.phase = "explore_items_list"
        elif selection == "7":
            self.phase = "ability_check"
        elif selection == "8":
            self.phase = "display_map"
        elif selection == "9":
            self.phase = "move_map"
        elif selection == "10":
            self.phase = "interact_with_environment"
        elif selection == "11":
            from states.map_selection_state import MapSelectionState
            game.push_state(MapSelectionState(game))
        else:
            game.io.show_message(f"I don't understand what you want to do with '{selection_input}'.")
            press_enter(game)
            return

        # If we have not changed state, run the next phase immediately
        if self.phase != "main_menu" and game.current_state() == self:
            self.run(game)

    def _process_command_market(self, cmd):
        cmd = cmd.lower().strip()

        # Mapping of text commands to actions
        if any(x in cmd for x in ["buy", "potion", "purchase"]):
            return "1"
        elif any(x in cmd for x in ["sell", "sells", "sell"]):
            return "2"
        elif any(x in cmd for x in ["talk", "merchant", "converse"]):
            return "3"
        elif any(x in cmd for x in ["challenge", "fight", "duel"]):
            return "4"
        elif any(x in cmd for x in ["inventory", "backpack", "manage"]):
            return "5"
        elif any(x in cmd for x in ["explore", "search", "items"]):
            return "6"
        elif any(x in cmd for x in ["check", "ability", "skill"]):
            return "7"
        elif any(x in cmd for x in ["map", "display"]):
            return "8"
        elif any(x in cmd for x in ["move", "movement", "go"]):
            return "9"
        elif any(x in cmd for x in ["interact", "environment", "interaction"]):
            return "10"
        elif any(x in cmd for x in ["travel", "area", "change", "map"]):
            return "11"
        else:
            return cmd  # return the original command if it matches no action

    def _buy_potion(self, game):
        if game.player.gold >= 5:
            game.player.gold -= 5
            game.player.add_item("Healing Potion")
            game.io.show_message("You bought a healing potion!")
        else:
            game.io.show_message("You don't have enough gold!")

        self.phase = "main_menu"
        press_enter(game)

    def _sell_item_list(self, game):
        if len(game.player.inventory) == 0:
            game.io.show_message("You have no items to sell!")
            self.phase = "main_menu"
            press_enter(game)
            return

        # Show the list of items
        game.io.show_message("\nYour items:")
        for i, item in enumerate(game.player.inventory, 1):
            if isinstance(item, str):
                game.io.show_message(f"{i}. {item}")
            else:
                # Also show the item type and value if available
                type_str = f" - {item.type}" if hasattr(item, 'type') else ""
                value_str = f" (Value: {item.value} gold)" if hasattr(item, 'value') else ""
                game.io.show_message(f"{i}. {item.name}{type_str}{value_str}")
        game.io.show_message(f"0. Go back")

        idx_input = game.io.request_input("\nWhich item do you want to sell? ")
        self.last_input = idx_input

        # Return to the menu if requested
        if idx_input == "0":
            self.phase = "main_menu"
            self.run(game)
            return

        # Find the item by name or index
        idx = -1
        if idx_input.isdigit():
            idx = int(idx_input) - 1
        else:
            # Try to find the item by name
            object_name = idx_input.lower().strip()
            for i, itm in enumerate(game.player.inventory):
                itm_name = itm.name.lower() if hasattr(itm, 'name') else str(itm).lower()
                if object_name in itm_name:
                    idx = i
                    break

        # Check whether the item was found
        if 0 <= idx < len(game.player.inventory):
            # Store the item index in the contextual data
            self.contextual_data["idx_item_from_sell"] = idx
            self.phase = "confirm_item_sale"
            self.run(game)  # Run the confirmation phase immediately
        else:
            game.io.show_message("Item not found in the inventory.")
            self.phase = "main_menu"
            press_enter(game)

    def _sell_item_confirm(self, game):
        idx = self.contextual_data.get("idx_item_from_sell", -1)
        if idx < 0 or idx >= len(game.player.inventory):
            game.io.show_message("Error: the selected item is no longer available.")
            self.phase = "main_menu"
            press_enter(game)
            return

        item = game.player.inventory[idx]

        # Calculate the sale price
        sale_price = 3  # Base price
        if hasattr(item, 'value'):
            sale_price = max(1, item.value // 2)  # Half the original value

        game.io.show_message(f"You are about to sell {item} for {sale_price} gold coins.")
        confirm = game.io.request_input("Do you confirm the sale? (y/n): ")
        self.last_input = confirm

        if confirm.lower() == "y":
            item = game.player.inventory.pop(idx)
            game.player.gold += sale_price
            game.io.show_message(f"You sold {item} for {sale_price} gold coins!")
        else:
            game.io.show_message("Sale cancelled.")

        self.phase = "main_menu"
        press_enter(game)

    def _talk_npc_list(self, game):
        # First check whether there are NPCs on the map
        nearby_npcs = {}
        if game.player.current_map:
            nearby_npcs = game.player.get_nearby_npcs(game.map_manager)

        # If there are no NPCs on the map, use the ones defined in the state
        if not nearby_npcs:
            npc_list = list(self.present_npcs.values())
        else:
            npc_list = list(nearby_npcs.values())

        game.io.show_message("\nWho do you want to talk to?")
        for i, npc in enumerate(npc_list, 1):
            game.io.show_message(f"{i}. {npc.name}")
        game.io.show_message(f"0. Go back")

        selection = game.io.request_input("\nChoose: ")
        self.last_input = selection

        if selection == "0":
            self.phase = "main_menu"
            self.run(game)
            return

        try:
            idx = int(selection) - 1
            if 0 <= idx < len(npc_list):
                npc = npc_list[idx]
                # Start the dialogue with the chosen NPC
                game.push_state(DialogueState(npc))
                # After the dialogue, return to the main menu
                self.phase = "main_menu"
            else:
                game.io.show_message("Invalid choice.")
                self.phase = "main_menu"
                press_enter(game)
        except ValueError:
            game.io.show_message("You must enter a number.")
            self.phase = "main_menu"
            press_enter(game)

    def _fight_npc_list(self, game):
        # First check whether there are NPCs on the map
        nearby_npcs = {}
        if game.player.current_map:
            nearby_npcs = game.player.get_nearby_npcs(game.map_manager)

        # If there are no NPCs on the map, use the ones defined in the state
        if not nearby_npcs:
            npc_list = list(self.present_npcs.values())
        else:
            npc_list = list(nearby_npcs.values())

        game.io.show_message("\nWho do you want to fight?")
        for i, npc in enumerate(npc_list, 1):
            game.io.show_message(f"{i}. {npc.name}")
        game.io.show_message(f"0. Go back")

        selection = game.io.request_input("\nChoose: ")
        self.last_input = selection

        if selection == "0":
            self.phase = "main_menu"
            self.run(game)
            return

        try:
            idx = int(selection) - 1
            if 0 <= idx < len(npc_list):
                # Store the chosen NPC in the contextual data
                self.contextual_data["npc_combat"] = npc_list[idx]
                self.phase = "confirm_npc_fight"
                self.run(game)  # Run the confirmation phase immediately
            else:
                game.io.show_message("Invalid choice.")
                self.phase = "main_menu"
                press_enter(game)
        except ValueError:
            game.io.show_message("You must enter a number.")
            self.phase = "main_menu"
            press_enter(game)

    def _fight_npc_confirm(self, game):
        npc = self.contextual_data.get("npc_combat")
        if not npc:
            game.io.show_message("Error: the selected NPC is no longer available.")
            self.phase = "main_menu"
            press_enter(game)
            return

        game.io.show_message(f"Are you sure you want to attack {npc.name}?")
        confirm = game.io.request_input("Confirm (y/n): ")
        self.last_input = confirm

        if confirm.lower() == "y":
            from states.combat import CombatState
            game.push_state(CombatState(hostile_npc=npc))
            # After the combat, return to the main menu
            self.phase = "main_menu"
        else:
            game.io.show_message("You have decided not to fight.")
            self.phase = "main_menu"
            press_enter(game)

    def _explore_items_list(self, game):
        # First check whether there are objects on the map
        nearby_items = {}
        if game.player.current_map:
            nearby_items = game.player.get_nearby_items(game.map_manager)

        # Prepare the list of objects to show
        if not nearby_items:
            # Use the objects defined in the state
            game.io.show_message("\nObjects in the market:")
            items_list = []
            for name, obj in self.interactive_objects.items():
                items_list.append(obj)
                game.io.show_message(f"{len(items_list)}. {obj.name} [{obj.state}]")
        else:
            # Use the objects on the map
            game.io.show_message("\nNearby objects:")
            items_list = []
            for pos, obj in nearby_items.items():
                items_list.append(obj)
                x, y = pos
                game.io.show_message(f"{len(items_list)}. {obj.name} [{obj.state}] at ({x}, {y})")

        game.io.show_message(f"0. Go back")

        selection = game.io.request_input("\nWhich object do you want to interact with? ")
        self.last_input = selection

        if selection == "0":
            self.phase = "main_menu"
            self.run(game)
            return

        try:
            idx = int(selection) - 1
            if 0 <= idx < len(items_list):
                item = items_list[idx]
                self.contextual_data["item_interaction"] = item
                self.phase = "interact_with_item"
                self.run(game)
            else:
                game.io.show_message("Invalid choice.")
                self.phase = "main_menu"
                press_enter(game)
        except ValueError:
            game.io.show_message("You must enter a number.")
            self.phase = "main_menu"
            press_enter(game)

    def _interact_item(self, game):
        item = self.contextual_data.get("item_interaction")
        if not item:
            game.io.show_message("Error: the selected item is no longer available.")
            self.phase = "main_menu"
            press_enter(game)
            return

        item.describe()
        item.interact(game.player)

        self.phase = "main_menu"
        press_enter(game)

    def _display_map(self, game):
        """Display the market map"""
        from states.map_state import MapState

        game.push_state(MapState(origin_state=self))
        self.phase = "main_menu"

    def _move_on_map(self, game):
        """Open the map directly in movement mode"""
        from states.map_state import MapState

        if not game.player.current_map:
            game.io.show_message("Movement system is not available!")
            self.phase = "main_menu"
            press_enter(game)
            return

        map_state = MapState(origin_state=self)
        map_state.phase = "move"
        game.push_state(map_state)
        self.phase = "main_menu"

    def _interact_environment(self, game):
        """Open the map directly in interaction mode"""
        from states.map_state import MapState

        if not game.player.current_map:
            game.io.show_message("Interaction system is not available!")
            self.phase = "main_menu"
            press_enter(game)
            return

        map_state = MapState(origin_state=self)
        map_state.phase = "interact"
        game.push_state(map_state)
        self.phase = "main_menu"

    def _init_commands(self):
        """Initialize the commands and their mappings for this state"""
        # This is a temporary method that may be fully implemented in the future
        # For now it is empty to allow the game to run
        pass

    def to_dict(self):
        """
        Convert the market state into a dictionary for serialization.

        Returns:
            dict: Dictionary representation of the state
        """
        # Get the base dictionary
        data = super().to_dict()

        # Add specific attributes
        data.update({
            "phase": self.phase,
            "last_input": self.last_input,
            # Do not serialize merchants, stock, interactive_objects since they are generated dynamically
        })

        return data

    @classmethod
    def from_dict(cls, data, game=None):
        """
        Create an instance of MarketState from a dictionary.

        Args:
            data (dict): Dictionary with the state data
            game: Game instance (optional)

        Returns:
            MarketState: New instance of MarketState
        """
        # First we get a base state through the parent class
        state = super().from_dict(data, game)

        # Manually initialize the market-specific attributes
        state.state_name = "market"
        state.game = game
        state.phase = data.get("phase", "main_menu")
        state.last_input = data.get("last_input")
        state.contextual_data = {}
        state.first_visit_completed = False

        # Initialize the market NPCs
        state.present_npcs = {
            "Herald": NPC("Herald"),
            "Violet": NPC("Violet"),
            "Gundren": NPC("Gundren")
        }
        state.active_npc_name = None
        state.conversation_state = "start"
        state.previous_state = None

        # Initialize empty interactive objects (they will be loaded by the JSON system)
        state.interactive_objects = {}
        state.show_map = False

        # Movement directions
        state.directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0)
        }

        return state

    def __getstate__(self):
        """
        Special method for pickling serialization.

        Returns:
            dict: Serializable state of the object
        """
        state = self.__dict__.copy()

        # Remove any circular or non-serializable references
        if 'contextual_data' in state:
            # Filter only the serializable data
            contextual_data_safe = {}
            for k, v in state['contextual_data'].items():
                if isinstance(v, (str, int, float, bool, list, dict, tuple)):
                    contextual_data_safe[k] = v
            state['contextual_data'] = contextual_data_safe

        return state

    def __setstate__(self, state):
        """
        Special method for unpickling deserialization.

        Args:
            state (dict): Object state to restore
        """
        self.__dict__.update(state)