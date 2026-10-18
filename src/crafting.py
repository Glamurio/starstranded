from __future__ import annotations

from typing import List, Dict, TYPE_CHECKING

from components.inventory import Inventory
from components.consumable import Consumable
from components.equippable import Axe, Equippable
from equipment_types import EquipmentType
from entity import Constructable
import species as defs

from utilities import get_shade, get_gaussian_shade

if TYPE_CHECKING:
    from components.plant import Plant


# ─── Base crafting material ──────────────────────────────────────────

class CraftingConsumable(Consumable):
    def activate(self) -> None:
        """Invoke this items ability.

        `action` is the context for this activation.
        """
        self.deplete()

    def deplete(self) -> None:
        """Remove the consumed item from its containing inventory."""
        inventory: Inventory = self.parent
        if isinstance(inventory, Inventory):
            inventory.remove(self)


class Branch(CraftingConsumable):
    def __init__(self, source: Plant):
        """A branch dropped by `source`; it takes its material name and a darker tint from the plant."""
        CraftingConsumable.__init__(self, defs.BRANCH)
        self.material = source.species.split()[0]
        self.color = get_shade(source.color)
        self.shade = get_gaussian_shade(self.color, self.kind.shade_sigma)


# ─── Crafted: Wooden Spear (Equippable weapon) ──────────────────────

class WoodenSpear(Equippable):
    def __init__(self, parent=None):
        Equippable.__init__(self, defs.WOODEN_SPEAR, parent)


# ─── Crafted: Campfire (Constructable, placeable light source) ──────

class Campfire(Constructable):
    """
    A placeable structure that can be lit or extinguished.
    When lit, it extends the player's line of sight around it.
    """
    def __init__(self, parent=None):
        Constructable.__init__(self, defs.CAMPFIRE)
        self.parent = parent
        self.is_lit: bool = False
        self.shade = self.kind.color

    @property
    def emits_light(self) -> bool:
        return self.is_lit and self.is_placed

    def toggle(self) -> str:
        """Toggle the campfire on/off. Returns a message string."""
        self.is_lit = not self.is_lit
        if self.is_lit:
            self.color = self.shade = self.kind.lit_color
            return "You light the campfire. Warm light fills the area."
        else:
            self.color = self.shade = self.kind.color
            return "You extinguish the campfire."

    def get_title(self, exclude_attributes: bool = False) -> str:
        state = "lit" if self.is_lit else "unlit"
        return f"Campfire ({state})"


# ─── Recipe system ───────────────────────────────────────────────────

class Recipe:
    """
    Defines a crafting recipe.
    
    `ingredients`: dict of {object_type: count} required from inventory.
    `result_class`: the class to instantiate when crafted.
    `is_placeable`: if True, the result is a Constructable that goes to 
                    inventory first, then the player can place it via activation.
    """
    def __init__(
        self,
        name: str,
        description: str,
        ingredients: Dict[str, int],
        result_class,
        is_placeable: bool = False,
    ):
        self.name = name
        self.description = description
        self.ingredients = ingredients
        self.result_class = result_class
        self.is_placeable = is_placeable

    def can_craft(self, inventory: Inventory) -> bool:
        for item_type, count in self.ingredients.items():
            available = sum(
                1 for item in inventory.items
                if item.object_type == item_type
            )
            if available < count:
                return False
        return True

    def get_missing(self, inventory: Inventory) -> Dict[str, int]:
        missing = {}
        for item_type, count in self.ingredients.items():
            available = sum(
                1 for item in inventory.items
                if item.object_type == item_type
            )
            if available < count:
                missing[item_type] = count - available
        return missing

    def consume_ingredients(self, inventory: Inventory) -> None:
        for item_type, count in self.ingredients.items():
            removed = 0
            for item in list(inventory.items):
                if item.object_type == item_type:
                    inventory.remove(item)
                    removed += 1
                    if removed >= count:
                        break

    def craft(self, inventory: Inventory):
        """Consume ingredients and return the crafted item."""
        self.consume_ingredients(inventory)
        result = self.result_class(inventory)
        return result


# ─── Recipe Registry ─────────────────────────────────────────────────

RECIPES: List[Recipe] = [
    Recipe(
        name="Wooden Spear",
        description="A sharpened branch. Better than fists.",
        ingredients={"Branch": 2},
        result_class=WoodenSpear,
        is_placeable=False,
    ),
    Recipe(
        name="Axe",
        description="A crude wooden axe. Sharp enough to cut down trees.",
        ingredients={"Branch": 3},
        result_class=Axe,
        is_placeable=False,
    ),
    Recipe(
        name="Campfire",
        description="Provides light and warmth. Place from inventory.",
        ingredients={"Branch": 3},
        result_class=Campfire,
        is_placeable=True,
    ),
]