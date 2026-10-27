from states.base_state import BaseGameState
from util.helpers import press_enter, show_inventory, show_stats
from states.market import MarketState
from states.dialogue import DialogueState
from entities.npc import NPC
from states.inventory_management import InventoryManagementState
from items.interactive_object import InteractiveObject, Chest, Door, Lever, Trap
from items.item import Item
from states.ability_check import AbilityCheckState
from states.commands import handle_targeted_command, parse_targeted_command
from world.map import Map
from world.map_manager import MapManager
from util.data_manager import get_data_manager
from core.conditions import condition_catalogue
import logging


class TavernState(BaseGameState):
    """Class representing the tavern state"""

    REST_COST = 10

    def __init__(self, game=None):
        super().__init__(game)
        self.state_name = "tavern"
        self.last_selection = None  # To remember the last choice made
        self.first_visit = True  # Flag for the first visit
        self.phase = "main_menu"  # Current phase for asynchronous operations
        self.last_input = None  # Stores the user's last input
        self.contextual_data = {}  # To store data between multiple phases

        # Load the NPCs specific to the tavern
        self.present_npcs = {
            "Durnan": NPC("Durnan"),
            "Elminster": NPC("Elminster"),
            "Mirt": NPC("Mirt")
        }
        self.active_npc_name = None
        self.conversation_state = "start"
        self.previous_state = None

        # Interactive objects in the tavern
        self.interactive_objects = {
            "counter": InteractiveObject("counter", "A long, polished wooden counter where drinks are served.", "clean", position="tavern"),
            "fireplace": InteractiveObject("fireplace", "A large stone fireplace with a crackling fire.", "on", position="tavern"),
            "hidden_chest": Chest("Hidden Chest", "A small chest hidden under a floorboard.",
                                     content=[Item("Rusty Key", "key", {"opens": ["Treasure Chest"]}, 2, "An old rusty key.")],
                                     position="tavern"),
            "cellar_door": Door("Cellar Door", "A sturdy door that leads to the cellar.",
                                  state="closed", requires_key=True, position="tavern",
                                  destination_position="cellar"),
            "floor_trap": Trap("Floor Trap", "Part of the floor seems unstable.",
                                         damage=5, position="tavern", saving_throw_difficulty=10)
        }

        # Link some objects together to create interactions
        secret_lever = Lever("Secret Lever", "A lever hidden behind a painting.", position="tavern")
        self.interactive_objects["secret_lever"] = secret_lever
        secret_lever.link_item("trap", self.interactive_objects["floor_trap"])

        # Example of a magic altar
        altar = InteractiveObject("Magic Altar", "An ancient altar with mysterious symbols.", state="inactive")
        altar.set_state_description("inactive", "An ancient altar with mysterious symbols that seem dormant.")
        altar.set_state_description("active", "The altar emits an intense blue light and the symbols glow.")
        altar.set_state_description("examined", "You notice that the altar bears runes forming an ancient spell.")

        # Add possible transitions
        altar.add_transition("inactive", "examined")
        altar.add_transition("inactive", "active")
        altar.add_transition("examined", "active")
        altar.add_transition("active", "inactive")

        # Link abilities
        altar.request_ability("perception", "examined", 12,
                            "Studying the altar carefully, you notice hidden carvings.")
        altar.request_ability("arcana", "active", 15,
                            "Using your arcane knowledge, you activate the ancient power of the altar.")

        # Link events to the world
        altar.link_event("active", lambda game: game.unlock_area("magic_crypt"))

        # Add the object to the tavern
        self.interactive_objects["magic_altar"] = altar

        # Attribute to track map display
        self.show_map = False

        # Movement directions
        self.directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0)
        }

        # Initialize menu and commands
        self._init_commands()

    def _init_commands(self):
        """Initialize the commands and their mappings for this state"""
        # This is a temporary method that may be fully implemented in the future
        # For now it is empty to allow the game to run
        pass

    def run(self, game):
        if self.first_visit:
            game.io.show_message(f"Welcome {game.player.name}, you have just arrived at The Wide-Open Portal Tavern in Waterdeep. You are returning from a long journey that brought you many treasures but also many scars. You walk in briskly and head toward your next adventure")
            self.first_visit = False

            # Set the player's starting position on the tavern map, unless a
            # map exit already placed them on a valid arrival tile.
            map = game.map_manager.get_map("tavern")
            if map:
                game.map_manager.set_current_map("tavern")
                if (
                    game.player.current_map != "tavern"
                    or not map.is_valid_position(game.player.x, game.player.y)
                ):
                    x, y = map.player_start_position
                    game.player.set_position("tavern", x, y)
                # Populate the map with interactive objects and NPCs
                game.map_manager.transfer_items_from_state("tavern", self)

        # Asynchronous handling based on the current phase
        if self.phase == "main_menu":
            self._main_show_menu(game)
        elif self.phase == "process_selection":
            self._process_selection(game)
        elif self.phase == "talk_npc":
            self._talk_with_npc(game)
        elif self.phase == "fight_npc":
            self._fight_with_npc(game)
        elif self.phase == "explore_items":
            self._explore_items(game)
        elif self.phase == "display_map":
            self._display_map(game)
        elif self.phase == "move_map":
            self._move_on_map(game)
        elif self.phase == "interact_with_environment":
            self._interact_environment(game)
        elif self.phase == "save_game":
            self._save_game(game)
        elif self.phase == "choose_enemy":
            self._choose_enemy(game)
        elif self.phase == "confirm_new_cycle":
            self._confirm_new_cycle(game)
        else:
            # Unrecognized phase, return to the main menu
            self.phase = "main_menu"
            self.run(game)

    def _main_show_menu(self, game):
        # The web session opens by rendering this menu with no command pending.
        # On the next run the same menu would otherwise be printed again; keep
        # the flag until a command is consumed.
        if not self.contextual_data.get("main_menu_rendered"):
            game.io.show_message("\nYou are in the tavern. What do you want to do?")
            game.io.show_message("1. Talk to someone")
            game.io.show_message("2. Travel to another area")
            game.io.show_message("3. Show stats")
            game.io.show_message("4. Fight an enemy")
            game.io.show_message("5. Challenge an NPC")
            game.io.show_message("6. Explore objects in the tavern")
            game.io.show_message("7. Show inventory")
            game.io.show_message("8. Ability check")
            game.io.show_message("9. Display map")
            game.io.show_message("10. Move on the map")
            game.io.show_message("11. Interact with the environment")
            game.io.show_message("12. Save game")
            game.io.show_message("13. Exit the game")
            game.io.show_message(f"14. Rest at the inn ({self.REST_COST} gold)")
            game.io.show_message("15. Bounty board")
            if self._campaign_complete(game.player):
                game.io.show_message(
                    "16. Begin a new cycle (New Game+)"
                )
            self.contextual_data["main_menu_rendered"] = True

        # Gets the command from input and stores it
        self.last_input = game.io.request_input("Choice: ")
        self.contextual_data["main_menu_rendered"] = False
        self.phase = "process_selection"

    def _process_selection(self, game):
        # Save the choice
        selection = str(self.last_input or "")
        self.last_selection = selection

        # Supports numeric, targeted natural-language, and simple text commands
        original_selection = selection
        if not selection.isdigit():
            targeted = parse_targeted_command(selection)
            if targeted is not None:
                action, target = targeted
                if handle_targeted_command(
                    game, action, target, extra_npcs=list(self.present_npcs.values())
                ):
                    self.phase = "main_menu"
                    return
                fallbacks = {
                    "talk": "1",
                    "attack": "5",
                    "use": "7",
                    "equip": "7",
                    "go": "2",
                    "examine": "6",
                    "interact": "6",
                }
                selection = fallbacks.get(action, selection)
            else:
                selection = self._process_command(selection)

        if selection == "1":
            self.phase = "talk_npc"
            self.contextual_data.clear()
        elif selection == "2":
            from states.map_selection_state import MapSelectionState
            game.push_state(MapSelectionState(game))
            self.phase = "main_menu"
        elif selection == "3":
            show_stats(game.player, game)
            press_enter(game)
            self.phase = "main_menu"
        elif selection == "4":
            # Modified to allow enemy selection
            self.phase = "choose_enemy"
            self.contextual_data.clear()
        elif selection == "5":
            self.phase = "fight_npc"
            self.contextual_data.clear()
        elif selection == "6":
            self.phase = "explore_items"
            self.contextual_data.clear()
        elif selection == "7":
            game.push_state(InventoryManagementState())
            self.phase = "main_menu"
        elif selection == "8":
            game.push_state(AbilityCheckState())
            self.phase = "main_menu"
        elif selection == "9":
            self.phase = "display_map"
        elif selection == "10":
            self.phase = "move_map"
        elif selection == "11":
            self.phase = "interact_with_environment"
        elif selection == "12":
            self.phase = "save_game"
        elif selection == "13":
            game.active = False
        elif selection == "14":
            self._rest(game)
        elif selection == "15":
            from states.bounty_board import BountyBoardState

            game.push_state(BountyBoardState(game))
            self.phase = "main_menu"
        elif selection == "16":
            if not self._campaign_complete(game.player):
                game.io.show_message(
                    "Finish the Sealed Sanctum before beginning a new cycle."
                )
                self.phase = "main_menu"
                return
            self.phase = "confirm_new_cycle"
            self.contextual_data.clear()
        else:
            game.io.show_message(f"I don't understand what you want to do with '{original_selection}'.")
            self.phase = "main_menu"

    def _process_command(self, cmd):
        cmd = cmd.lower().strip()
        words = {word.strip(".,!?;:") for word in cmd.split()}

        # Mapping of text commands to numbers
        if any(word in cmd for word in ["talk", "converse", "converse"]):
            return "1"
        elif any(word in cmd for word in ["travel", "go", "area", "change", "map"]):
            return "2"
        elif any(word in cmd for word in ["stats", "stat", "status"]):
            return "3"
        elif any(word in cmd for word in ["fight", "attack", "fight"]):
            return "4"
        elif any(word in cmd for word in ["challenge", "duel"]):
            return "5"
        elif any(word in cmd for word in ["explore", "search", "items"]):
            return "6"
        elif any(word in cmd for word in ["inventory", "backpack", "items"]):
            return "7"
        elif any(word in cmd for word in ["check", "ability", "skill"]):
            return "8"
        elif any(word in cmd for word in ["map", "display map", "display"]):
            return "9"
        elif any(word in cmd for word in ["move", "go", "move"]):
            return "10"
        elif any(word in cmd for word in ["interact", "use", "environment"]):
            return "11"
        elif any(word in cmd for word in ["save", "save"]):
            return "12"
        elif any(word in cmd for word in ["exit", "quit", "exit"]):
            return "13"
        elif words & {"rest", "sleep", "recover", "nap"}:
            return "14"
        elif words & {"bounty", "bounties", "contract", "contracts"}:
            return "15"
        elif "new" in words and "cycle" in words:
            return "16"
        elif words & {"newgameplus", "ng+"}:
            return "16"
        else:
            return cmd  # return the original command if it matches no action

    @staticmethod
    def _campaign_complete(player):
        return any(
            isinstance(quest, dict)
            and quest.get("id") == "sanctum_chapter"
            for quest in (getattr(player, "completed_quests", []) or [])
        )

    def _confirm_new_cycle(self, game):
        player = game.player
        next_cycle = max(1, int(getattr(player, "cycle", 1) or 1)) + 1
        game.io.show_message(
            f"\nBegin a new cycle? Cycle {next_cycle} restarts the story "
            "and world state, but keeps your level, equipment, achievements, "
            "faction standing, Rune Trials progress, Rune Shards and forged gear."
        )
        choice = str(
            game.io.request_input("Begin the new cycle? (y/n): ") or ""
        )
        if choice.strip().casefold() in {"y", "yes", "begin"}:
            game.start_new_cycle()
            return
        game.io.show_message("You remain in the current cycle.")
        self.phase = "main_menu"

    def _rest(self, game):
        """Restore the party at the inn for gold and clear temporary effects."""
        player = game.player
        mana = int(getattr(player, "mana", 0) or 0)
        mana_max = int(getattr(player, "mana_max", 0) or 0)
        conditions = getattr(player, "conditions", None)
        if not isinstance(conditions, dict):
            conditions = {}
        stealthed = bool(getattr(player, "stealthed", False))
        disguised = bool(getattr(player, "disguised", False))

        if (
            player.hp >= player.hp_max
            and mana >= mana_max
            and not conditions
            and not stealthed
            and not disguised
        ):
            game.io.show_message("\nYou are already rested.")
            press_enter(game)
            self.phase = "main_menu"
            return

        if player.gold < self.REST_COST:
            game.io.show_message(
                f"\nThe innkeeper shakes her head. A long rest costs "
                f"{self.REST_COST} gold, and you only have {player.gold}."
            )
            press_enter(game)
            self.phase = "main_menu"
            return

        player.gold -= self.REST_COST
        player.hp = player.hp_max
        player.mana = mana_max
        player.stealthed = False
        player.disguised = False
        cleared = sorted(conditions)
        conditions.clear()

        game.io.show_message(
            f"\nYou pay {self.REST_COST} gold for a room and take a long rest. "
            "Your wounds close and your strength returns."
        )
        if cleared:
            game.io.show_message(
                "The rest clears: " + self._condition_labels(cleared) + "."
            )
        press_enter(game)
        self.phase = "main_menu"

    @staticmethod
    def _condition_labels(condition_ids):
        """Return player-facing names for cleared condition ids."""
        catalogue = condition_catalogue()
        fallback = {
            "poison": "Poisoned",
            "guidance": "Guidance",
            "advantage": "Advantage",
            "disadvantage": "Disadvantage",
        }
        labels = []
        for condition_id in condition_ids:
            definition = catalogue.get(condition_id)
            if isinstance(definition, dict):
                labels.append(definition.get("name", condition_id))
            else:
                labels.append(
                    fallback.get(
                        condition_id, condition_id.replace("_", " ").title()
                    )
                )
        return ", ".join(labels)

    def _talk_with_npc(self, game):
        # Check whether we have already shown the NPC list
        if "npc_list_mostrata" not in self.contextual_data:
            # Try to use the NPCs on the map
            if game.player.current_map:
                nearby_npcs = game.player.get_nearby_npcs(game.map_manager)
                if nearby_npcs:
                    game.io.show_message("\nWho do you want to talk to?")
                    npc_list = list(nearby_npcs.values())
                    for i, npc in enumerate(npc_list, 1):
                        game.io.show_message(f"{i}. {npc.name}")
                    game.io.show_message(f"{len(npc_list) + 1}. Go back")

                    self.contextual_data["npc_list_mostrata"] = True
                    self.contextual_data["type_list"] = "map"
                    self.contextual_data["npc_list"] = npc_list
                    self.last_input = game.io.request_input("\nChoose: ")
                    return

            # Fall back to the original method if there are no nearby NPCs or we are not using the map manager
            game.io.show_message("\nWho do you want to talk to?")
            for i, name in enumerate(self.present_npcs.keys(), 1):
                game.io.show_message(f"{i}. {name}")
            game.io.show_message(f"{len(self.present_npcs) + 1}. Go back")

            self.contextual_data["npc_list_mostrata"] = True
            self.contextual_data["type_list"] = "local"
            self.last_input = game.io.request_input("\nChoose: ")
            return

        # Process the NPC selection
        try:
            selection = int(self.last_input)

            if self.contextual_data["type_list"] == "map":
                npc_list = self.contextual_data["npc_list"]
                if 1 <= selection <= len(npc_list):
                    npc = npc_list[selection - 1]
                    game.push_state(DialogueState(npc))
                elif selection == len(npc_list) + 1:
                    # Return to the main menu
                    pass
                else:
                    game.io.show_message("Invalid choice.")
            else:  # type_list == "locale"
                if 1 <= selection <= len(self.present_npcs):
                    npc_name = list(self.present_npcs.keys())[selection - 1]
                    npc = self.present_npcs[npc_name]
                    game.push_state(DialogueState(npc))
                elif selection == len(self.present_npcs) + 1:
                    # Return to the main menu
                    pass
                else:
                    game.io.show_message("Invalid choice.")

        except ValueError:
            game.io.show_message("You must enter a number.")

        # Finally, restore the state
        self.phase = "main_menu"
        self.contextual_data.clear()

    def _fight_with_npc(self, game):
        # Check whether we have already shown the NPC list
        if "npc_list_mostrata" not in self.contextual_data:
            # Try to use the NPCs on the map
            if game.player.current_map:
                nearby_npcs = game.player.get_nearby_npcs(game.map_manager)
                if nearby_npcs:
                    game.io.show_message("\nWho do you want to fight?")
                    npc_list = list(nearby_npcs.values())
                    for i, npc in enumerate(npc_list, 1):
                        game.io.show_message(f"{i}. {npc.name}")
                    game.io.show_message(f"{len(npc_list) + 1}. Go back")

                    self.contextual_data["npc_list_mostrata"] = True
                    self.contextual_data["type_list"] = "map"
                    self.contextual_data["npc_list"] = npc_list
                    self.last_input = game.io.request_input("\nChoose: ")
                    return

            # Fall back to the original method
            game.io.show_message("\nWho do you want to fight?")
            for i, name in enumerate(self.present_npcs.keys(), 1):
                game.io.show_message(f"{i}. {name}")
            game.io.show_message(f"{len(self.present_npcs) + 1}. Go back")

            self.contextual_data["npc_list_mostrata"] = True
            self.contextual_data["type_list"] = "local"
            self.last_input = game.io.request_input("\nChoose: ")
            return

        # If we have shown the list but have not yet asked for confirmation
        if "npc_scelto" not in self.contextual_data:
            try:
                selection = int(self.last_input)

                if self.contextual_data["type_list"] == "map":
                    npc_list = self.contextual_data["npc_list"]
                    if 1 <= selection <= len(npc_list):
                        npc = npc_list[selection - 1]
                        self.contextual_data["npc_scelto"] = npc
                        # Confirm before attacking
                        game.io.show_message(f"Are you sure you want to attack {npc.name}?")
                        self.last_input = game.io.request_input("(y/n): ")
                        return
                    elif selection == len(npc_list) + 1:
                        # Return to the main menu
                        self.phase = "main_menu"
                        self.contextual_data.clear()
                        return
                    else:
                        game.io.show_message("Invalid choice.")
                        self.phase = "main_menu"
                        self.contextual_data.clear()
                        return
                else:  # type_list == "locale"
                    if 1 <= selection <= len(self.present_npcs):
                        npc_name = list(self.present_npcs.keys())[selection - 1]
                        npc = self.present_npcs[npc_name]
                        self.contextual_data["npc_scelto"] = npc
                        self.contextual_data["npc_name"] = npc_name
                        # Confirm before attacking
                        game.io.show_message(f"Are you sure you want to attack {npc_name}?")
                        self.last_input = game.io.request_input("(y/n): ")
                        return
                    elif selection == len(self.present_npcs) + 1:
                        # Return to the main menu
                        self.phase = "main_menu"
                        self.contextual_data.clear()
                        return
                    else:
                        game.io.show_message("Invalid choice.")
                        self.phase = "main_menu"
                        self.contextual_data.clear()
                        return
            except ValueError:
                game.io.show_message("You must enter a number.")
                self.phase = "main_menu"
                self.contextual_data.clear()
                return

        # If we have a selected NPC, verify the confirmation
        if self.contextual_data.get("npc_scelto"):
            npc = self.contextual_data["npc_scelto"]
            confirm = self.last_input.lower()
            if confirm == "y":
                from core.quests import build_ally_party
                from states.combat import CombatState

                game.push_state(
                    CombatState(
                        hostile_npc=npc,
                        allies=build_ally_party(game.player),
                    )
                )
            else:
                game.io.show_message("You have decided not to fight.")

        # Finally, restore the state
        self.phase = "main_menu"
        self.contextual_data.clear()

    def _explore_items(self, game):
        # Check whether we have already shown the item list
        if "items_list_mostrata" not in self.contextual_data:
            # Try to use the objects on the map
            if game.player.current_map:
                nearby_items = game.player.get_nearby_items(game.map_manager)
                if nearby_items:
                    game.io.show_message("\nNearby objects:")
                    items_list = []
                    for pos, obj in nearby_items.items():
                        items_list.append((pos, obj))
                        x, y = pos
                        game.io.show_message(f"{len(items_list)}. {obj.name} [{obj.state}] at ({x}, {y})")
                    game.io.show_message(f"{len(items_list) + 1}. Go back")

                    self.contextual_data["items_list_mostrata"] = True
                    self.contextual_data["type_list"] = "map"
                    self.contextual_data["items_list"] = items_list
                    self.last_input = game.io.request_input("\nWhich object do you want to interact with? ")
                    return

            # Fall back to the original method
            game.io.show_message("\nObjects in the tavern:")
            for i, name in enumerate(self.interactive_objects.keys(), 1):
                item = self.interactive_objects[name]
                game.io.show_message(f"{i}. {item.name} [{item.state}]")
            game.io.show_message(f"{len(self.interactive_objects) + 1}. Go back")

            self.contextual_data["items_list_mostrata"] = True
            self.contextual_data["type_list"] = "local"
            self.last_input = game.io.request_input("\nWhich object do you want to interact with? ")
            return

        # Process the object selection
        try:
            selection = int(self.last_input)

            if self.contextual_data["type_list"] == "map":
                items_list = self.contextual_data["items_list"]
                if 1 <= selection <= len(items_list):
                    _, item = items_list[selection - 1]
                    item.describe(game)
                    item.interact(game.player, game)
                elif selection == len(items_list) + 1:
                    # Return to the main menu
                    pass
                else:
                    game.io.show_message("Invalid choice.")
            else:  # type_list == "locale"
                if 1 <= selection <= len(self.interactive_objects):
                    item_name = list(self.interactive_objects.keys())[selection - 1]
                    item = self.interactive_objects[item_name]
                    item.describe(game)
                    item.interact(game.player, game)
                elif selection == len(self.interactive_objects) + 1:
                    # Return to the main menu
                    pass
                else:
                    game.io.show_message("Invalid choice.")

        except ValueError:
            game.io.show_message("You must enter a number.")

        # Finally, restore the state
        self.phase = "main_menu"
        self.contextual_data.clear()

    def _display_map(self, game):
        """Display the tavern map"""
        from states.map_state import MapState

        game.push_state(MapState(origin_state=self))
        self.phase = "main_menu"

    def _move_on_map(self, game):
        """Open the map directly in movement mode"""
        from states.map_state import MapState

        map_state = MapState(origin_state=self)
        map_state.phase = "move"
        game.push_state(map_state)
        self.phase = "main_menu"

    def _interact_environment(self, game):
        """Open the map directly in interaction mode"""
        from states.map_state import MapState

        map_state = MapState(origin_state=self)
        map_state.phase = "interact"
        game.push_state(map_state)
        self.phase = "main_menu"

    def _save_game(self, game):
        """Save the current game"""
        game.save()
        game.io.show_message("Game saved!")
        press_enter(game)

        # Return to the main menu
        self.phase = "main_menu"

    def pause(self, game):
        """
        When the tavern is paused (e.g. during a dialogue)
        we save the current state
        """
        game.io.show_message("\nThe tavern remains waiting...")

    def resume(self, game):
        """
        When the tavern resumes after a pause
        we show a resume message
        """
        game.io.show_message("\nYou return to the tavern...")
        # When we resume, we always return to the main menu
        self.phase = "main_menu"

    def to_dict(self):
        """
        Convert the tavern state into a dictionary for serialization.

        Returns:
            dict: Dictionary representation of the state
        """
        # Get the base dictionary
        data = super().to_dict()

        # Remove the present_npcs dictionary first, since it will be serialized separately
        if "present_npcs" in data:
            del data["present_npcs"]

        # Manually serialize the NPCs to avoid serialization issues
        npc_dict = {}
        try:
            for name, npc in self.present_npcs.items():
                if hasattr(npc, 'to_dict') and callable(getattr(npc, 'to_dict')):
                    npc_dict[name] = npc.to_dict()
        except:
            # In case of error, we save only the NPC names
            npc_dict = {name: {"name": name} for name in self.present_npcs.keys()}

        # Add specific attributes
        data.update({
            "phase": self.phase,
            "last_input": self.last_input,
            "last_selection": self.last_selection,
            "npc_names": list(self.present_npcs.keys())  # Save only the NPC names
            # Do not serialize interactive_objects since they are generated dynamically
        })

        return data

    @classmethod
    def from_dict(cls, data, game=None):
        """
        Create an instance of TavernState from a dictionary.

        Args:
            data (dict): Dictionary with the state data
            game: Game instance (optional)

        Returns:
            TavernState: New instance of TavernState
        """
        # Create an object without calling __init__ to avoid the missing-parameter error
        state = object.__new__(cls)

        # Manually initialize the basic attributes
        state.state_name = "tavern"
        state.last_selection = None
        state.first_visit = False  # It is not the first visit during a load
        state.phase = "main_menu"
        state.last_input = None
        state.contextual_data = {}
        state.game = game

        # Recreate the NPCs from their names
        state.present_npcs = {}
        npc_names = data.get("npc_names", ["Durnan", "Elminster", "Mirt"])
        for name in npc_names:
            from entities.npc import NPC
            state.present_npcs[name] = NPC(name)

        # Initialize empty interactive objects (they will be loaded by the JSON system)
        state.interactive_objects = {}

        # Load other attributes from the dictionary if present
        state.phase = data.get("phase", "main_menu")
        state.last_input = data.get("last_input")
        state.last_selection = data.get("last_selection")
        state.active_npc_name = None
        state.conversation_state = "start"
        state.previous_state = None
        state.show_map = False

        # Movement directions
        state.directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0)
        }

        # Initialize menu and commands
        if hasattr(state, '_init_commands'):
            state._init_commands()

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

    def _choose_enemy(self, game):
        """
        Allow the user to choose an enemy to fight.
        """
        from core.quests import build_ally_party
        from entities.enemy import Enemy
        from states.combat import CombatState

        # Check the state of the selection
        if "phase_selection" not in self.contextual_data:
            # First phase: choosing the mode (random or selection)
            game.io.show_message("\nHow do you want to choose the enemy?")
            game.io.show_message("1. Random enemy")
            game.io.show_message("2. Random easy enemy")
            game.io.show_message("3. Random medium enemy")
            game.io.show_message("4. Random hard enemy")
            game.io.show_message("5. Choose a specific type")
            game.io.show_message("6. Return to the main menu")
            game.io.show_message("7. Fight a pair of goblins")
            game.io.show_message("8. Fight a curated encounter")

            self.contextual_data["phase_selection"] = "mode"
            game.io.request_input("Choice: ")
            return

        elif self.contextual_data["phase_selection"] == "mode":
            # Process the mode selection
            selection = game.io.last_input

            if selection == "1":
                # Random enemy of any difficulty
                enemy = Enemy.create_random()
                game.io.show_message(f"\nYou are about to face a {enemy.name}!")
                press_enter(game)
                game.push_state(
                    CombatState(
                        enemy=enemy, allies=build_ally_party(game.player)
                    )
                )
                self.phase = "main_menu"
                self.contextual_data.clear()
                return

            elif selection == "2":
                # Random easy enemy
                enemy = Enemy.create_random("easy")
                game.io.show_message(f"\nYou are about to face a {enemy.name} (easy)!")
                press_enter(game)
                game.push_state(
                    CombatState(
                        enemy=enemy, allies=build_ally_party(game.player)
                    )
                )
                self.phase = "main_menu"
                self.contextual_data.clear()
                return

            elif selection == "3":
                # Random medium enemy
                enemy = Enemy.create_random("medium")
                game.io.show_message(f"\nYou are about to face a {enemy.name} (medium)!")
                press_enter(game)
                game.push_state(
                    CombatState(
                        enemy=enemy, allies=build_ally_party(game.player)
                    )
                )
                self.phase = "main_menu"
                self.contextual_data.clear()
                return

            elif selection == "4":
                # Random hard enemy
                enemy = Enemy.create_random("hard")
                game.io.show_message(f"\nYou are about to face a {enemy.name} (hard)!")
                press_enter(game)
                game.push_state(
                    CombatState(
                        enemy=enemy, allies=build_ally_party(game.player)
                    )
                )
                self.phase = "main_menu"
                self.contextual_data.clear()
                return

            elif selection == "5":
                # Move to the specific selection phase
                monster_types = Enemy.get_monster_types()

                if not monster_types:
                    game.io.show_message("\nThere are no monster types available.")
                    self.phase = "main_menu"
                    self.contextual_data.clear()
                    return

                game.io.show_message("\nChoose a monster type:")
                for i, type in enumerate(monster_types, 1):
                    game.io.show_message(f"{i}. {type.replace('_', ' ').title()}")
                game.io.show_message(f"{len(monster_types) + 1}. Go back")

                self.contextual_data["phase_selection"] = "specific_type"
                self.contextual_data["monster_types"] = monster_types
                game.io.request_input("Choice: ")
                return

            elif selection == "6":
                # Return to the main menu
                self.phase = "main_menu"
                self.contextual_data.clear()
                return

            elif selection == "7":
                enemies = []
                for suffix in ("A", "B"):
                    enemy = Enemy(name="", monster_type="goblin")
                    enemy.name = f"Goblin {suffix}"
                    enemies.append(enemy)
                game.io.show_message(
                    "\nTwo goblins bar your way, blades drawn!"
                )
                press_enter(game)
                game.push_state(
                    CombatState(
                        enemies=enemies,
                        allies=build_ally_party(game.player),
                    )
                )
                self.phase = "main_menu"
                self.contextual_data.clear()
                return

            elif selection == "8":
                from core.encounters import encounter_catalogue

                catalogue = encounter_catalogue("tavern")
                if not catalogue:
                    game.io.show_message("\nNo curated encounters are available.")
                    self.phase = "main_menu"
                    self.contextual_data.clear()
                    return

                game.io.show_message("\nChoose an encounter:")
                for index, (encounter_id, data) in enumerate(
                    catalogue.items(), 1
                ):
                    title = (
                        data.get("title", encounter_id)
                        if isinstance(data, dict)
                        else encounter_id
                    )
                    difficulty = (
                        data.get("difficulty", "medium")
                        if isinstance(data, dict)
                        else "medium"
                    )
                    game.io.show_message(f"{index}. {title} ({difficulty})")
                game.io.show_message(f"{len(catalogue) + 1}. Go back")

                self.contextual_data["phase_selection"] = "encounters"
                self.contextual_data["encounter_ids"] = list(catalogue)
                game.io.request_input("Choice: ")
                return

            else:
                game.io.show_message("Invalid choice.")
                self.contextual_data.clear()
                self.phase = "choose_enemy"
                return

        elif self.contextual_data["phase_selection"] == "encounters":
            try:
                selection = int(game.io.last_input)
                encounter_ids = self.contextual_data.get("encounter_ids", [])

                if 1 <= selection <= len(encounter_ids):
                    from core.encounters import build_encounter

                    encounter = build_encounter(encounter_ids[selection - 1])
                    if not encounter:
                        game.io.show_message(
                            "\nThat encounter could not be prepared."
                        )
                        self.phase = "main_menu"
                        self.contextual_data.clear()
                        return

                    game.io.show_message(
                        f"\n{encounter['title']}: {encounter['description']}"
                    )
                    names = ", ".join(
                        enemy.name for enemy in encounter["enemies"]
                    )
                    game.io.show_message(f"Enemies: {names}")
                    game.io.show_message(
                        f"Difficulty: {encounter.get('difficulty', 'medium')}"
                    )
                    reward = encounter.get("reward", {})
                    parts = []
                    if isinstance(reward, dict):
                        if reward.get("gold"):
                            parts.append(f"{reward['gold']} gold")
                        if reward.get("experience"):
                            parts.append(f"{reward['experience']} XP")
                    if parts:
                        game.io.show_message(
                            "Completion bonus: " + ", ".join(parts) + "."
                        )

                    press_enter(game)
                    game.push_state(
                        CombatState(
                            enemies=encounter["enemies"],
                            allies=build_ally_party(game.player),
                            encounter=encounter,
                        )
                    )
                    self.phase = "main_menu"
                    self.contextual_data.clear()
                    return

                elif selection == len(encounter_ids) + 1:
                    self.contextual_data.clear()
                    self.phase = "choose_enemy"
                    return

                game.io.show_message("Invalid choice.")
                game.io.request_input("Choice: ")
                return

            except ValueError:
                game.io.show_message("You must enter a number.")
                game.io.request_input("Choice: ")
                return

        elif self.contextual_data["phase_selection"] == "specific_type":
            # Process the selection of the specific monster type
            try:
                selection = int(game.io.last_input)
                monster_types = self.contextual_data.get("monster_types", [])

                if 1 <= selection <= len(monster_types):
                    monster_type = monster_types[selection - 1]
                    enemy = Enemy(name="", monster_type=monster_type)

                    # Show information about the monster
                    game.io.show_message(f"\nYou have chosen to face a {enemy.name}!")
                    game.io.show_message(enemy.description)
                    game.io.show_message(f"HP: {enemy.hp}/{enemy.hp_max}, Strength: {enemy.strength_base}")

                    # Start the combat
                    press_enter(game)
                    game.push_state(
                        CombatState(
                            enemy=enemy,
                            allies=build_ally_party(game.player),
                        )
                    )
                    self.phase = "main_menu"
                    self.contextual_data.clear()
                    return

                elif selection == len(monster_types) + 1:
                    # Return to mode selection
                    self.contextual_data.clear()
                    self.phase = "choose_enemy"
                    return

                else:
                    game.io.show_message("Invalid choice.")
                    # Stay in the same phase
                    game.io.request_input("Choice: ")
                    return

            except ValueError:
                game.io.show_message("You must enter a number.")
                # Stay in the same phase
                game.io.request_input("Choice: ")
                return

        # If this point is reached, return to the main menu
        self.phase = "main_menu"
        self.contextual_data.clear()