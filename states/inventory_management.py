from states.base_state import BaseState
from util.helpers import press_enter

class InventoryManagementState(BaseState):
    def __init__(self, previous_state=None):
        self.previous_state = previous_state
        self.phase = "main_menu"  # Initial phase
        self.last_input = None
        self.equippable = []  # Cache for equippable items
        self.options_removal = []  # Cache for removal options
    
    def run(self, game):
        # Handle an empty inventory
        if self.phase == "main_menu" and not game.player.inventory:
            game.io.show_message("\n--- INVENTORY MANAGEMENT ---")
            game.io.show_message("Your inventory is empty.")
            press_enter(game, "Press ENTER to go back...")
            if game.current_state():
                game.pop_state()
            return
            
        # Process the phases in sequence
        if self.phase == "main_menu":
            self._main_show_menu(game)
        elif self.phase == "process_main_menu":
            self._main_process_menu(game)
        elif self.phase == "use_item":
            self._show_use_item(game)
        elif self.phase == "process_use_item":
            self._process_use_item(game)
        elif self.phase == "equip_item":
            self._show_equip_item(game)
        elif self.phase == "process_equip_item":
            self._process_equip_item(game)
        elif self.phase == "remove_equipment":
            self._show_remove_equipment(game)
        elif self.phase == "process_remove_equipment":
            self._process_remove_equipment(game)
        elif self.phase == "examine_item":
            self._show_examine_item(game)
        elif self.phase == "process_examine_item":
            self._process_examine_item(game)
        elif self.phase == "wait_for_confirmation":
            self._wait_confirm(game)
    
    def _main_show_menu(self, game):
        game.io.show_message("\n--- INVENTORY MANAGEMENT ---")
        
        # Show the items in the inventory
        game.io.show_message(f"\nGold: {game.player.gold}")
        game.io.show_message("\nItems:")
        for i, item in enumerate(game.player.inventory, 1):
            if isinstance(item, str):
                game.io.show_message(f"{i}. {item}")
            else:
                game.io.show_message(f"{i}. {item.name} - {item.type} - {item.description}")
        
        if game.player.weapon:
            if isinstance(game.player.weapon, str):
                game.io.show_message(f"\nEquipped weapon: {game.player.weapon}")
            else:
                game.io.show_message(f"\nEquipped weapon: {game.player.weapon.name}")
                
        if game.player.armor:
            if isinstance(game.player.armor, str):
                game.io.show_message(f"\nEquipped armor: {game.player.armor}")
            else:
                game.io.show_message(f"\nEquipped armor: {game.player.armor.name}")
        
        game.io.show_message("\nWhat do you want to do?")
        game.io.show_message("1. Use an item")
        game.io.show_message("2. Equip an item")
        game.io.show_message("3. Remove equipment")
        game.io.show_message("4. Examine an item")
        game.io.show_message("5. Go back")
        
        self.last_input = game.io.request_input("Choice: ")
        self.phase = "process_main_menu"
    
    def _main_process_menu(self, game):
        selection = self.last_input
        
        if selection == "1":
            self.phase = "use_item"
        elif selection == "2":
            self.phase = "equip_item"
        elif selection == "3":
            self.phase = "remove_equipment"
        elif selection == "4":
            self.phase = "examine_item"
        elif selection == "5":
            if game.current_state():
                game.pop_state()
        else:
            game.io.show_message("Invalid choice.")
            self.phase = "main_menu"  # Return to the main menu
    
    def _show_use_item(self, game):
        game.io.show_message("\nWhich item do you want to use?")
        for i, item in enumerate(game.player.inventory, 1):
            if isinstance(item, str):
                game.io.show_message(f"{i}. {item}")
            else:
                game.io.show_message(f"{i}. {item.name}")
        game.io.show_message(f"{len(game.player.inventory) + 1}. Cancel")
        
        self.last_input = game.io.request_input("\nChoose: ")
        self.phase = "process_use_item"
    
    def _process_use_item(self, game):
        try:
            selection = int(self.last_input)
            if 1 <= selection <= len(game.player.inventory):
                item = game.player.inventory[selection - 1]
                if isinstance(item, str):
                    game.io.show_message(f"You cannot use {item} directly.")
                else:
                    item.use(game.player, game)
                    game.io.show_message(f"You used: {item.name}")
            elif selection == len(game.player.inventory) + 1:
                self.phase = "main_menu"
                return
            else:
                game.io.show_message("Invalid choice.")
        except ValueError:
            game.io.show_message("You must enter a number.")
        
        self.phase = "wait_for_confirmation"
    
    def _show_equip_item(self, game):
        self.equippable = [item for item in game.player.inventory 
                             if not isinstance(item, str) and hasattr(item, 'type') and item.type in ["weapon", "armor", "accessory"]]
        
        if not self.equippable:
            game.io.show_message("You have no equippable items.")
            self.phase = "wait_for_confirmation"
            return
        
        game.io.show_message("\nWhich item do you want to equip?")
        for i, item in enumerate(self.equippable, 1):
            game.io.show_message(f"{i}. {item.name} ({item.type})")
        game.io.show_message(f"{len(self.equippable) + 1}. Cancel")
        
        self.last_input = game.io.request_input("\nChoose: ")
        self.phase = "process_equip_item"
    
    def _process_equip_item(self, game):
        try:
            selection = int(self.last_input)
            if 1 <= selection <= len(self.equippable):
                item = self.equippable[selection - 1]
                item.equip(game.player)
                game.io.show_message(f"You equipped: {item.name}")
            elif selection == len(self.equippable) + 1:
                self.phase = "main_menu"
                return
            else:
                game.io.show_message("Invalid choice.")
        except ValueError:
            game.io.show_message("You must enter a number.")
        
        self.phase = "wait_for_confirmation"
    
    def _show_remove_equipment(self, game):
        game.io.show_message("\nWhat do you want to remove?")
        self.options_removal = []
        
        if game.player.weapon and not isinstance(game.player.weapon, str):
            self.options_removal.append(("weapon", game.player.weapon))
        if game.player.armor and not isinstance(game.player.armor, str):
            self.options_removal.append(("armor", game.player.armor))
        for i, acc in enumerate(game.player.accessories):
            if not isinstance(acc, str):
                self.options_removal.append((f"accessory {i+1}", acc))
        
        if not self.options_removal:
            game.io.show_message("You have no equipment to remove.")
            self.phase = "wait_for_confirmation"
            return
        
        for i, (type, item) in enumerate(self.options_removal, 1):
            game.io.show_message(f"{i}. {type.capitalize()}: {item.name}")
        game.io.show_message(f"{len(self.options_removal) + 1}. Cancel")
        
        self.last_input = game.io.request_input("\nChoose: ")
        self.phase = "process_remove_equipment"
    
    def _process_remove_equipment(self, game):
        try:
            selection = int(self.last_input)
            if 1 <= selection <= len(self.options_removal):
                type, item = self.options_removal[selection - 1]
                item.remove(game.player)
                game.io.show_message(f"You removed: {item.name}")
            elif selection == len(self.options_removal) + 1:
                self.phase = "main_menu"
                return
            else:
                game.io.show_message("Invalid choice.")
        except ValueError:
            game.io.show_message("You must enter a number.")
        
        self.phase = "wait_for_confirmation"
    
    def _show_examine_item(self, game):
        game.io.show_message("\nWhich item do you want to examine?")
        for i, item in enumerate(game.player.inventory, 1):
            if isinstance(item, str):
                game.io.show_message(f"{i}. {item}")
            else:
                game.io.show_message(f"{i}. {item.name}")
        game.io.show_message(f"{len(game.player.inventory) + 1}. Cancel")
        
        self.last_input = game.io.request_input("\nChoose: ")
        self.phase = "process_examine_item"
    
    def _process_examine_item(self, game):
        try:
            selection = int(self.last_input)
            if 1 <= selection <= len(game.player.inventory):
                item = game.player.inventory[selection - 1]
                if isinstance(item, str):
                    game.io.show_message(f"\nName: {item}")
                    game.io.show_message("Type: Generic")
                    game.io.show_message("Description: Not available")
                    game.io.show_message("Value: Unknown")
                else:
                    game.io.show_message(f"\nName: {item.name}")
                    game.io.show_message(f"Type: {item.type}")
                    game.io.show_message(f"Description: {item.description}")
                    game.io.show_message(f"Value: {item.value} gold")
                    
                    if hasattr(item, 'effect') and item.effect:
                        game.io.show_message("Effects:")
                        for stat, value in item.effect.items():
                            game.io.show_message(f"  - {stat}: {value}")
            elif selection == len(game.player.inventory) + 1:
                self.phase = "main_menu"
                return
            else:
                game.io.show_message("Invalid choice.")
        except ValueError:
            game.io.show_message("You must enter a number.")
        
        self.phase = "wait_for_confirmation"
    
    def _wait_confirm(self, game):
        press_enter(game, "Press ENTER to continue...")
        self.phase = "main_menu"

    def to_dict(self):
        """
        Convert the state into a dictionary for serialization.
        
        Returns:
            dict: Dictionary representation of the state
        """
        # Get the base dictionary
        data = super().to_dict()
        
        # Add specific attributes
        data.update({
            "phase": self.phase,
            "last_input": self.last_input
        })
        
        # If previous_state is a state object with to_dict(), we serialize it
        if self.previous_state and hasattr(self.previous_state, 'to_dict'):
            data["previous_state"] = self.previous_state.to_dict()
        elif self.previous_state and hasattr(self.previous_state, '__class__'):
            # Otherwise we save only the type
            data["previous_state_type"] = self.previous_state.__class__.__name__
            
        return data

    @classmethod
    def from_dict(cls, data):
        """
        Create an instance of InventoryManagementState from a dictionary.
        
        Args:
            data (dict): Dictionary with the state data
            
        Returns:
            InventoryManagementState: New instance of the state
        """
        state = cls()
        
        # Restore attributes
        state.phase = data.get("phase", "main_menu")
        state.last_input = data.get("last_input")
        
        # Note: previous_state will be handled by the caller
        # because it might require references to the entire state stack
        
        return state

# The old methods are no longer needed because we now have separate versions for each phase
# def _use_item(self, game): ...
# def _equip_item(self, game): ...
# def _remove_equipment(self, game): ...
# def _examine_item(self, game): ...
