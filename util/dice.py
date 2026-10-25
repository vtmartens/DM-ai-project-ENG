import random

class Dice:
    """
    Class representing an N-sided die usable for D&D-style rolls.
    Supports single rolls, multiple rolls and rolls with advantage/disadvantage.
    """
    def __init__(self, faces):
        """Initializes a die with the specified number of faces."""
        self.faces = faces
    
    def roll(self):
        """Performs a single die roll."""
        return random.randint(1, self.faces)
    
    def multiple_rolls(self, number_of_rolls):
        """Performs multiple die rolls and returns a list of the results."""
        return [self.roll() for _ in range(number_of_rolls)]
    
    def roll_with_advantage(self):
        """Performs two die rolls and returns the better result (advantage in D&D)."""
        roll1 = self.roll()
        roll2 = self.roll()
        return max(roll1, roll2), roll1, roll2
    
    def roll_with_disadvantage(self):
        """Performs two die rolls and returns the worse result (disadvantage in D&D)."""
        roll1 = self.roll()
        roll2 = self.roll()
        return min(roll1, roll2), roll1, roll2

def roll_dice(formula):
    """
    Performs a dice roll according to a formula, for example "2d6+3" or "1d20-1".

    Args:
        formula (str): The dice roll formula (e.g. "2d6+3")

    Returns:
        tuple: (total_result, rolls_list, modifier)
    """
    # Parse the formula
    if "+" in formula:
        dice_formula, mod_str = formula.split("+")
        modifier = int(mod_str)
    elif "-" in formula:
        dice_formula, mod_str = formula.split("-")
        modifier = -int(mod_str)
    else:
        dice_formula = formula
        modifier = 0
    
    # Extract the number and type of dice
    if "d" in dice_formula:
        num_dice, faces = dice_formula.split("d")
        num_dice = int(num_dice) if num_dice else 1
        faces = int(faces)
    else:
        # If there is no 'd', we assume it is just a number
        return int(dice_formula) + modifier, [], modifier
    
    # Perform the rolls
    dice = Dice(faces)
    rolls = dice.multiple_rolls(num_dice)
    total_result = sum(rolls) + modifier
    
    return total_result, rolls, modifier
