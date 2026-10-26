from util.dice import Dice
from util.data_manager import get_data_manager

class InteractiveObject:
    def __init__(self, name, description="", state="closed", content=None, position=None, token="?"):
        """
        Initializes an interactive object in the game world.

        Args:
            name: Name of the object
            description: Textual description of the object
            state: Current state of the object (e.g. "closed", "open", "active", "broken")
            content: List of contained objects (if applicable)
            position: Position of the object in the game world (e.g. "tavern", "market", or coordinates)
            token: Token for the map representation
        """
        self.name = name
        self.description = description
        self.state = state
        self.content = content or []  # List of contained objects
        self.linked_items = {}  # Dictionary of objects that can be influenced by this one
        self.position = position  # Position of the object in the world
        self.token = token  # Token for the map representation

        # New attributes
        self.state_descriptions = {state: description}  # Descriptions for each state
        self.possible_states = {}  # Dictionary of possible transitions
        self.required_abilities = {}  # Abilities required for specific interactions
        self.ability_difficulty = {}  # Difficulty for each ability
        self.interaction_messages = {}  # Narrative feedback for interactions
        self.events = {}  # Events to trigger on state change
        self.type = "interactive_object"  # Object type, useful for serialization
    
    def __getstate__(self):
        """
        Prepares the object for serialization with pickle.

        Returns:
            dict: Object state to serialize
        """
        # Create a copy of the state dictionary
        state = self.__dict__.copy()
        
        # Remove non-serializable attributes (such as functions)
        if 'events' in state:
            del state['events']
        
        # Remove other non-serializable elements
        non_serializable = []
        for key, value in state.items():
            if callable(value) or key.startswith('__'):
                non_serializable.append(key)
        
        for key in non_serializable:
            del state[key]
        
        return state

    def __setstate__(self, state):
        """
        Restores the object state after deserialization.

        Args:
            state: Deserialized state to restore
        """
        # Initialize empty events
        state['events'] = {}
        
        # Update the object state
        self.__dict__.update(state)
    
    def interact(self, player, game=None):
        """
        Main interaction method. It should be overridden in subclasses.
        """
        if game:
            game.io.show_message(f"Nothing happens with {self.name}...")
    
    def describe(self, game=None):
        """
        Shows the object's description and its current state.
        """
        if game:
            game.io.show_message(f"{self.name}: {self.description} [{self.state}]")
            if self.position:
                game.io.show_message(f"Located in: {self.position}")
    
    def link_item(self, connection_name, item):
        """
        Links another interactive object to this one (e.g. a lever to a door).
        """
        self.linked_items[connection_name] = item
    
    def move(self, new_position, game=None):
        """
        Moves the object to a new position.
        """
        self.position = new_position
        if game:
            game.io.show_message(f"{self.name} has been moved to: {new_position}")
        
    def interact_specific(self, player, ability, game=None):
        """
        Handles interactions based on specific abilities.
        """
        if ability not in self.required_abilities:
            if game:
                game.io.show_message(f"You cannot use {ability} with {self.name} right now.")
            return False
            
        # Get the narrative message if available
        if ability in self.interaction_messages and game:
            game.io.show_message(self.interaction_messages[ability])
        
        # State transition if necessary
        if ability in self.required_abilities:
            new_state = self.required_abilities[ability]
            if new_state in self.possible_states.get(self.state, []):
                self.change_state(new_state, game)
                return True
        
        return False
    
    def change_state(self, new_state, game=None):
        """
        Changes the object's state and triggers events in the world.
        """
        old_state = self.state
        if new_state in self.possible_states.get(old_state, []):
            self.state = new_state
            
            # Show the new state's description
            if game:
                if new_state in self.state_descriptions:
                    game.io.show_message(self.state_descriptions[new_state])
                else:
                    game.io.show_message(f"{self.name} is now {new_state}.")

            # Trigger events in the world
            if game and new_state in self.events:
                for event in self.events[new_state]:
                    event(game)
            
            return True
        else:
            if game:
                game.io.show_message(f"Cannot change {self.name} from {old_state} to {new_state}.")
            return False
    
    def add_transition(self, current_state, new_state):
        """
        Defines a possible transition between states.
        """
        if current_state not in self.possible_states:
            self.possible_states[current_state] = []
        
        if new_state not in self.possible_states[current_state]:
            self.possible_states[current_state].append(new_state)
    
    def set_state_description(self, state, description):
        """
        Defines a description for a specific state.
        """
        self.state_descriptions[state] = description
    
    def request_ability(self, ability, resulting_state, difficulty=10, message=None):
        """
        Defines an ability that can be used with this object.
        """
        self.required_abilities[ability] = resulting_state
        self.ability_difficulty[ability] = difficulty
        
        if message:
            self.interaction_messages[ability] = message
    
    def link_event(self, state, event):
        """
        Links an event to trigger when the object enters a certain state.
        """
        if state not in self.events:
            self.events[state] = []
        
        self.events[state].append(event)
        
    def to_dict(self):
        """
        Converts the interactive object into a dictionary for serialization.

        Returns:
            dict: Dictionary representation of the object
        """
        # Serialize the fundamental attributes
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "state": self.state,
            "position": self.position,
            "token": self.token,
            "state_descriptions": self.state_descriptions,
            "possible_states": self.possible_states,
            "required_abilities": self.required_abilities,
            "ability_difficulty": self.ability_difficulty,
            "interaction_messages": self.interaction_messages,
        }
        
        # Add the content if present
        if self.content:
            result["content"] = [obj.to_dict() if hasattr(obj, 'to_dict') else {"name": obj.name} for obj in self.content]
        
        return result
    
    @classmethod
    def from_dict(cls, data):
        """
        Creates an InteractiveObject instance from a dictionary.

        Args:
            data (dict): Dictionary with the object's data

        Returns:
            InteractiveObject: New InteractiveObject instance
        """
        from items.item import Item
        
        new_object = cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            state=data.get("state", "closed"),
            position=data.get("position"),
            token=data.get("token", "?")
        )
        
        # Set the type
        new_object.type = data.get("type", "interactive_object")
        
        # Setting the content
        content_raw = data.get("content", [])
        content = []
        
        for item in content_raw:
            if isinstance(item, dict):
                content.append(Item.from_dict(item))
            elif isinstance(item, str):
                # Create a generic object if only the name is available
                content.append(Item(item, "common"))
        
        new_object.content = content
        
        # Loading the other properties
        new_object.state_descriptions = data.get("state_descriptions", {new_object.state: new_object.description})
        new_object.possible_states = data.get("possible_states", {})
        new_object.required_abilities = data.get("required_abilities", {})
        new_object.ability_difficulty = data.get("ability_difficulty", {})
        new_object.interaction_messages = data.get("interaction_messages", {})
        
        return new_object

    @classmethod
    def load_from_json(cls, object_name):
        """
        Loads an interactive object from the JSON file.

        Args:
            object_name (str): Name of the object to load.

        Returns:
            InteractiveObject: Instance of the loaded interactive object.
        """
        data_manager = get_data_manager()
        item_data = data_manager.get_interactive_objects(object_name)
        
        if not item_data:
            return None
            
        # Determine the class type to instantiate
        object_type = item_data.get("type", "interactive_object")
        
        if object_type == "chest":
            return Chest.from_dict(item_data)
        elif object_type == "door":
            return Door.from_dict(item_data)
        elif object_type == "lever":
            return Lever.from_dict(item_data)
        elif object_type == "trap":
            return Trap.from_dict(item_data)
        elif object_type == "breakable_object":
            return BreakableObject.from_dict(item_data)
        else:
            return InteractiveObject.from_dict(item_data)

    def save_to_json(self):
        """
        Saves the interactive object to a JSON file.

        Returns:
            bool: True if the save succeeded, False otherwise.
        """
        data_manager = get_data_manager()
        items = data_manager.get_interactive_objects()

        # Convert the object to a dictionary
        item_dict = self.to_dict()
        
        # Look for whether the object already exists and update it
        existing_item = False
        for i, item in enumerate(items):
            if item.get("name") == self.name:
                items[i] = item_dict
                existing_item = True
                break
                
        # If the object does not exist, add it
        if not existing_item:
            items.append(item_dict)
            
        # Save the updated objects
        return data_manager.save_interactive_objects(items)


class Chest(InteractiveObject):
    def __init__(self, name, description="", state="closed", content=None, requires_key=False, position=None, token="C"):
        super().__init__(name, description, state, content, position, token)
        self.requires_key = requires_key
        self.type = "chest"
    
    def interact(self, player, game=None):
        if self.state == "closed":
            if self.requires_key:
                # Check whether the player has a key
                found_key = False
                for item in player.inventory:
                    if isinstance(item, str):
                        item_name = item
                    else:
                        item_name = item.name
                    
                    if "key" in item_name.lower():
                        found_key = True
                        break
                
                if not found_key:
                    if game:
                        game.io.show_message("The chest is locked. You need a key to open it.")
                    return
                if game:
                    game.io.show_message("You use the key to open the chest...")
            
            if game:
                game.io.show_message(f"You open {self.name}...")
            self.state = "open"
            if self.content:
                if game:
                    game.io.show_message("Inside you find:")
                    for content_item in self.content:
                        game.io.show_message(f"- {content_item.name}")
                player.add_item(item)
                self.content = []
            else:
                if game:
                    game.io.show_message("It is empty.")
        else:
            if game:
                game.io.show_message(f"{self.name} is already open.")

    def to_dict(self):
        """Extends the base class's to_dict method to add specific attributes."""
        data = super().to_dict()
        data["requires_key"] = self.requires_key
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Creates a Chest instance from a dictionary."""
        chest = super(Chest, cls).from_dict(data)
        chest.requires_key = data.get("requires_key", False)
        return chest


class Door(InteractiveObject):
    def __init__(self, name, description="", state="closed", requires_key=False, position=None, destination_position=None, token="D"):
        super().__init__(name, description, state, None, position, token)
        self.requires_key = requires_key
        self.destination_position = destination_position  # Where this door leads
        self.type = "door"
    
    def interact(self, player, game=None):
        if self.state == "closed":
            if self.requires_key:
                # Check whether the player has a key
                found_key = False
                for item in player.inventory:
                    if isinstance(item, str):
                        item_name = item
                    else:
                        item_name = item.name
                    
                    if "key" in item_name.lower():
                        found_key = True
                        break
                
                if not found_key:
                    if game:
                        game.io.show_message("The door is locked. You need a key to open it.")
                    return
                if game:
                    game.io.show_message("You use the key to open the door...")
            
            if game:
                game.io.show_message(f"You open {self.name}...")
            self.state = "open"
            if self.destination_position and game:
                game.io.show_message(f"You can go toward: {self.destination_position}")
        elif self.state == "open":
            if game:
                game.io.show_message(f"You close {self.name}...")
            self.state = "closed"
        else:
            if game:
                game.io.show_message(f"{self.name} is {self.state}.")

    def to_dict(self):
        """Extends the base class's to_dict method to add specific attributes."""
        data = super().to_dict()
        data["requires_key"] = self.requires_key
        data["destination_position"] = self.destination_position
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Creates a Door instance from a dictionary."""
        door = super(Door, cls).from_dict(data)
        door.requires_key = data.get("requires_key", False)
        door.destination_position = data.get("destination_position")
        return door


class Lever(InteractiveObject):
    def __init__(self, name, description="", state="deactivated", position=None, token="L"):
        super().__init__(name, description, state, None, position, token)
        self.type = "lever"
    
    def interact(self, player, game=None):
        if self.state == "deactivated":
            if game:
                game.io.show_message(f"You activate {self.name}...")
            self.state = "activated"

            # Activate/deactivate linked objects
            for name, item in self.linked_items.items():
                if item.state == "closed" or item.state == "closed":
                    if game:
                        game.io.show_message(f"{self.name} unlocks {item.name}!")
                    item.state = "open" if item.name.lower() == "chest" else "open"
                elif item.state == "active":
                    if game:
                        game.io.show_message(f"{self.name} deactivates {item.name}!")
                    item.state = "deactivated"
        else:
            if game:
                game.io.show_message(f"You deactivate {self.name}...")
            self.state = "deactivated"

            # Restore the state of the linked objects
            for name, item in self.linked_items.items():
                if item.state == "open" or item.state == "open":
                    if game:
                        game.io.show_message(f"{self.name} blocks {item.name}!")
                    item.state = "closed" if item.name.lower() == "chest" else "closed"
                elif item.state == "deactivated":
                    if game:
                        game.io.show_message(f"{self.name} activates {item.name}!")
                    item.state = "active"


class Trap(InteractiveObject):
    def __init__(self, name, description="", state="active", damage=10, position=None, saving_throw_difficulty=10, token="T"):
        super().__init__(name, description, state, None, position, token)
        self.damage = damage
        self.saving_throw_difficulty = saving_throw_difficulty
        self.type = "trap"
    
    def interact(self, player, game=None):
        if self.state == "active":
            if game:
                game.io.show_message(f"You triggered {self.name}!")
            dice = Dice(20)
            roll = dice.roll()
            modifier = player.dexterity  # Assume the saving throw is based on dexterity
            result = roll + modifier
            if game:
                game.io.show_message(f"Saving throw: {roll} + {modifier} = {result}")
            if result < self.saving_throw_difficulty:
                if game:
                    game.io.show_message(f"You take {self.damage} damage!")
                player.take_damage(self.damage)
            else:
                if game:
                    game.io.show_message("You avoided the trap!")
        else:
            if game:
                game.io.show_message(f"{self.name} is deactivated.")
    
    def deactivate(self, game=None):
        if self.state == "active":
            if game:
                game.io.show_message(f"You deactivate {self.name}.")
            self.state = "deactivated"
        else:
            if game:
                game.io.show_message(f"{self.name} is already deactivated.")

    def to_dict(self):
        """Extends the base class's to_dict method to add specific attributes."""
        data = super().to_dict()
        data["damage"] = self.damage
        data["saving_throw_difficulty"] = self.saving_throw_difficulty
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Creates a Trap instance from a dictionary."""
        trap = super(Trap, cls).from_dict(data)
        trap.damage = data.get("damage", 10)
        trap.saving_throw_difficulty = data.get("saving_throw_difficulty", 10)
        return trap


class BreakableObject(InteractiveObject):
    def __init__(self, name, description="", state="intact", materials=None, required_strength=5, position=None, token="?"):
        super().__init__(name, description, state, None, position, token)
        self.materials = materials or []  # List of objects obtained by breaking
        self.required_strength = required_strength
        self.type = "breakable_object"
    
    def interact(self, player, game=None):
        if self.state == "intact":
            if hasattr(player, 'strength') and player.strength >= self.required_strength:
                if game:
                    game.io.show_message(f"You break {self.name}!")
                self.state = "broken"
                if self.materials:
                    if game:
                        game.io.show_message("You obtain:")
                        for item in self.materials:
                            game.io.show_message(f"- {item.name}")
                    player.add_item(item)
            else:
                if game:
                    game.io.show_message(f"You are not strong enough to break {self.name}.")
        else:
            if game:
                game.io.show_message(f"{self.name} is already broken.")

    def to_dict(self):
        """Extends the base class's to_dict method to add specific attributes."""
        data = super().to_dict()
        data["required_strength"] = self.required_strength
        data["materials"] = [obj.to_dict() if hasattr(obj, 'to_dict') else {"name": obj.name} for obj in self.materials]
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Creates a BreakableObject instance from a dictionary."""
        from items.item import Item
        
        new_object = super(BreakableObject, cls).from_dict(data)
        new_object.required_strength = data.get("required_strength", 5)
        
        # Load the materials
        materials_raw = data.get("materials", [])
        materials = []
        
        for item in materials_raw:
            if isinstance(item, dict):
                materials.append(Item.from_dict(item))
            elif isinstance(item, str):
                materials.append(Item(item, "common"))
        
        new_object.materials = materials
        return new_object
