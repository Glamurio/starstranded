from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from components.inventory import Inventory
from components.consumable import Consumable

from components.equippable import Equippable
from entity import Entity
from equipment_types import EquipmentType
from render_order import RenderOrder
from utilities import map_codepoints, get_shade, get_gaussian_shade

if TYPE_CHECKING:
    from components.plant import Tree


class Recipe:
    """
    Defines a crafting recipe.
    
    `ingredients` is a dict of {object_type: count} required.
    `result_class` is a callable that creates the crafted item.
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
        self.ingredients = ingredients  # {"Branch": 2}
        self.result_class = result_class
        self.is_placeable = is_placeable

    def can_craft(self, inventory: Inventory) -> bool:
        """Check if the inventory has all required ingredients."""
        for item_type, count in self.ingredients.items():
            available = sum(
                1 for item in inventory.items
                if item.object_type == item_type
            )
            if available < count:
                return False
        return True

    def get_missing(self, inventory: Inventory) -> Dict[str, int]:
        """Return a dict of {item_type: missing_count} for items not yet available."""
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
        """Remove the required ingredients from the inventory."""
        for item_type, count in self.ingredients.items():
            removed = 0
            for item in list(inventory.items):  # Copy list since we modify during iteration
                if item.object_type == item_type:
                    inventory.remove(item)
                    removed += 1
                    if removed >= count:
                        break

    def craft(self, inventory: Inventory):
        """Consume ingredients and return the crafted item/entity."""
        self.consume_ingredients(inventory)
        result = self.result_class()
        if not self.is_placeable:
            result.parent = inventory
        return result

class CraftingConsumable(Consumable):
    def __init__(self):
        Consumable.__init__(self)
        self.object_type = "Craftable"

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
    def __init__(self, parent: Tree):
        CraftingConsumable.__init__(self)
        self.sprite_pos=(15, 5)
        self.object_type = "Branch"
        self.material = parent.species.split()[0]
        char_info = map_codepoints(self.object_type, self.sprite_pos)
        self.char = char_info["sprite"]
        self.color = get_shade(parent.color)
        self.shade = get_gaussian_shade(self.color, 10)

class WoodenSpear(Equippable):
    def __init__(self, parent=None):
        Equippable.__init__(self)
        self.parent = parent
        self.equipment_type = EquipmentType.WEAPON
        self.power_bonus = 3
        self.material = "Wooden"
        self.object_type = "Spear"
        self.sprite_pos = (45, 21)  # Adjust to your tileset
        char_info = map_codepoints(self.object_type, self.sprite_pos)
        self.char = char_info["sprite"]
        self.color = (0x8B, 0x6B, 0x3D)  # Warm wood brown

class Campfire(Entity):
    def __init__(self):
        Entity.__init__(self)
        self.object_type = "Campfire"
        self.species = "Campfire"
        self.is_lit: bool = False
        self.light_radius: int = 8
        self.blocks_movement: bool = False
        self.blocks_sight: bool = False
        self.render_order = RenderOrder.ITEM

        import color as c
        self.color_lit = c.orange
        self.color_unlit = c.white
        self.color = self.color_unlit
        self.shade = self.color_unlit

        self.sprite_pos = (7, 29)  # Adjust to your tileset
        char_info = map_codepoints("Campfire", self.sprite_pos)
        self.char = char_info["sprite"]

    def toggle(self) -> str:
        self.is_lit = not self.is_lit
        if self.is_lit:
            self.color = self.color_lit
            self.shade = self.color_lit
            return "You light the campfire. Warm light fills the area."
        else:
            self.color = self.color_unlit
            self.shade = self.color_unlit
            return "You extinguish the campfire."

    def get_title(self, exclude_attributes: bool = False) -> str:
        state = "lit" if self.is_lit else "unlit"
        return f"Campfire ({state})"
    
RECIPE_LIST: List[Recipe] = [
    Recipe(
        name="Wooden Spear",
        description="A sharpened branch. Better than fists.",
        ingredients={"Branch": 2},
        result_class=WoodenSpear,
        is_placeable=False,
    ),
    Recipe(
        name="Campfire",
        description="Provides light and warmth. Needs to be placed.",
        ingredients={"Branch": 3},
        result_class=Campfire,
        is_placeable=True,
    ),
]