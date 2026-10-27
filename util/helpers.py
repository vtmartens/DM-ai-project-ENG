def press_enter(game=None, message="Press Enter to continue..."):
    """
    Utility function to wait for user input before advancing.
    Useful for giving the user time to read the messages on screen.

    Args:
        game: The game instance (optional if not required)
        message: Prompt shown when the IO blocks for confirmation
    """
    # Use the game context if available. Web sessions do not block on a
    # press-enter confirmation; the next command naturally continues.
    if game:
        if getattr(game.io, "pause_for_confirmation", True):
            game.io.request_input(message)
    else:
        input(message)

def show_stats(entity, game=None):
    """
    Shows the stats of an entity.

    Args:
        entity: The entity whose stats should be shown
        game: The game instance (optional if the context is stored in the entity)
    """
    # Use the entity's game context if available
    game_ctx = game
    if not game_ctx and hasattr(entity, 'game') and entity.game:
        game_ctx = entity.game
        
    if game_ctx:
        game_ctx.io.show_message(f"Name: {entity.name}")
        game_ctx.io.show_message(f"HP: {entity.hp}/{entity.hp_max}")
        game_ctx.io.show_message(f"STR: {entity.strength_base} ({entity.modifier_strength:+d})")
        game_ctx.io.show_message(f"DEX: {entity.dexterity_base} ({entity.modifier_dexterity:+d})")
        game_ctx.io.show_message(f"CON: {entity.constitution_base} ({entity.modifier_constitution:+d})")
        game_ctx.io.show_message(f"INT: {entity.intelligence_base} ({entity.modifier_intelligence:+d})")
        game_ctx.io.show_message(f"WIS: {entity.wisdom_base} ({entity.modifier_wisdom:+d})")
        game_ctx.io.show_message(f"CHA: {entity.charisma_base} ({entity.modifier_charisma:+d})")
        game_ctx.io.show_message(f"Armor Class: {entity.armor_class}")
        game_ctx.io.show_message(f"Attack Bonus: {entity.attack_bonus:+d}")
        if hasattr(entity, 'level'):
            game_ctx.io.show_message(f"Level: {entity.level}")
        if hasattr(entity, 'gold'):
            game_ctx.io.show_message(f"Gold: {entity.gold}")
        if hasattr(entity, 'experience'):
            game_ctx.io.show_message(f"Experience: {entity.experience}/{100 * entity.level}")
    else:
        # Fallback if there is no game context
        print(f"Name: {entity.name}")
        print(f"HP: {entity.hp}/{entity.hp_max}")
        print(f"STR: {entity.strength_base} ({entity.modifier_strength:+d})")
        print(f"DEX: {entity.dexterity_base} ({entity.modifier_dexterity:+d})")
        print(f"CON: {entity.constitution_base} ({entity.modifier_constitution:+d})")
        print(f"INT: {entity.intelligence_base} ({entity.modifier_intelligence:+d})")
        print(f"WIS: {entity.wisdom_base} ({entity.modifier_wisdom:+d})")
        print(f"CHA: {entity.charisma_base} ({entity.modifier_charisma:+d})")
        print(f"Armor Class: {entity.armor_class}")
        print(f"Attack Bonus: {entity.attack_bonus:+d}")
        if hasattr(entity, 'level'):
            print(f"Level: {entity.level}")
        if hasattr(entity, 'gold'):
            print(f"Gold: {entity.gold}")
        if hasattr(entity, 'experience'):
            print(f"Experience: {entity.experience}/{100 * entity.level}")

def show_inventory(entity, game=None):
    """
    Shows the inventory of an entity.

    Args:
        entity: The entity whose inventory should be shown
        game: The game instance (optional if the context is stored in the entity)
    """
    # Use the entity's game context if available
    game_ctx = game
    if not game_ctx and hasattr(entity, 'game') and entity.game:
        game_ctx = entity.game
    
    if not hasattr(entity, 'inventory'):
        if game_ctx:
            game_ctx.io.show_message(f"{entity.name} has no inventory.")
        else:
            print(f"{entity.name} has no inventory.")
        return
        
    if len(entity.inventory) == 0:
        if game_ctx:
            game_ctx.io.show_message(f"{entity.name}'s inventory is empty.")
        else:
            print(f"{entity.name}'s inventory is empty.")
        return
    
    if game_ctx:
        game_ctx.io.show_message(f"\n=== INVENTORY OF {entity.name.upper()} ===")
        
        for i, item in enumerate(entity.inventory, 1):
            # Handle different types of items
            if isinstance(item, str):
                game_ctx.io.show_message(f"{i}. {item}")
            elif hasattr(item, 'name'):
                description = f"{item.name}"
                
                if hasattr(item, 'description') and item.description:
                    description += f" - {item.description}"
                
                if hasattr(item, 'value') and item.value:
                    description += f" (Value: {item.value} gold)"
                    
                if hasattr(item, 'equipped') and item.equipped:
                    description += " [Equipped]"
                    
                game_ctx.io.show_message(f"{i}. {description}")
            else:
                game_ctx.io.show_message(f"{i}. {str(item)}")
                
        if hasattr(entity, 'gold'):
            game_ctx.io.show_message(f"\nGold: {entity.gold}")
    else:
        # Fallback if there is no game context
        print(f"\n=== INVENTORY OF {entity.name.upper()} ===")
        
        for i, item in enumerate(entity.inventory, 1):
            # Handle different types of items
            if isinstance(item, str):
                print(f"{i}. {item}")
            elif hasattr(item, 'name'):
                description = f"{item.name}"
                
                if hasattr(item, 'description') and item.description:
                    description += f" - {item.description}"
                
                if hasattr(item, 'value') and item.value:
                    description += f" (Value: {item.value} gold)"
                    
                if hasattr(item, 'equipped') and item.equipped:
                    description += " [Equipped]"
                    
                print(f"{i}. {description}")
            else:
                print(f"{i}. {str(item)}")
                
        if hasattr(entity, 'gold'):
            print(f"\nGold: {entity.gold}")
