from __future__ import annotations

from typing import List, Dict, Optional, TYPE_CHECKING

from components.inventory import Inventory
from components.consumable import Consumable
from components.equippable import Axe, Equippable
from equipment_types import EquipmentType
from entity import Constructable, Item
import species as defs
import tile_types

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


class Leather(CraftingConsumable):
    def __init__(self, source_species: str = "", parent=None):
        """A piece of leather from the creature `source_species`."""
        CraftingConsumable.__init__(self, defs.LEATHER)
        self.material = source_species or None
        self.parent = parent


# ─── Crafted: Flask (carries liquid) ─────────────────────────────────

class Flask(Item):
    """A leather flask: three sips of one liquid. What the liquid really is stays unknown until it is drunk."""

    def __init__(self, parent=None):
        Item.__init__(self, defs.FLASK)
        self.parent = parent
        self.liquid: int = 0  # liquids.LiquidKind of the contents (0 = empty)
        self.sips: int = 0
        self.boiled: bool = False

    def get_title(self, exclude_attributes: bool = False) -> str:
        if not self.sips:
            return "Leather flask (empty)"
        what = "boiled liquid" if self.boiled else "liquid"
        return f"Leather flask ({what}, {self.sips} sip{'s' if self.sips != 1 else ''})"

    def activate(self, user):
        from actions import UseFlaskAction
        return UseFlaskAction(user, self)


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


# ─── Crafted: building pieces (they change the terrain instead of becoming an entity) ──────

class BuildingPiece(Constructable):
    """A constructable that is built into the terrain of a tile next to the player and used up."""

    def can_place_at(self, game_map, x: int, y: int) -> Optional[str]:
        """None if the piece can be built at (x, y) of `game_map`, otherwise the reason it cannot."""
        raise NotImplementedError

    def build(self, game_map, x: int, y: int) -> None:
        raise NotImplementedError

    def place_on_map(self, x: int, y: int, game_map) -> None:
        if isinstance(self.parent, Inventory):
            self.parent.remove(self)
        self.build(game_map, x, y)


class WoodenFloor(BuildingPiece):
    """Lays a floor where there is none (open air above a lower layer), so that you can walk there."""

    def __init__(self, parent=None):
        Constructable.__init__(self, defs.WOODEN_FLOOR)
        self.parent = parent

    def can_place_at(self, game_map, x: int, y: int) -> Optional[str]:
        tile = game_map.tile_at(x, y)
        if tile is None or not tile["open"]:
            return "There is nothing to build on there: floors go where there is open air."
        return None

    def build(self, game_map, x: int, y: int) -> None:
        game_map.set_tile(x, y, tile_types.built_floor.get_array())


class WoodenStairs(BuildingPiece):
    """A staircase up from a floor tile to the layer above (which gets the way down at the same place)."""

    def __init__(self, parent=None):
        Constructable.__init__(self, defs.WOODEN_STAIRS)
        self.parent = parent

    def can_place_at(self, game_map, x: int, y: int) -> Optional[str]:
        tile = game_map.tile_at(x, y)
        if tile is None or not tile["walkable"] or tile["stairs"] or game_map.get_entities_at_location(x, y, True):
            return "Stairs need a free floor tile."
        above = game_map.engine.game_world.tile_on_layer(game_map.z + 1, x, y)
        if above is None or not (above["open"] or above["walkable"]) or above["stairs"]:
            return "There is no room above for the stairs to lead to."
        return None

    def build(self, game_map, x: int, y: int) -> None:
        game_map.set_tile(x, y, tile_types.up_stairs.get_array())
        game_map.engine.game_world.edit_tile(game_map.z + 1, x, y, tile_types.down_stairs.get_array())


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
        name="Flask",
        description="A leather flask. Use it next to a liquid to fill it, next to a lit campfire to boil it, else to drink.",
        ingredients={"Leather": 1},
        result_class=Flask,
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
    Recipe(
        name="Wooden Floor",
        description="A plank floor for open air: build it next to you, then walk out onto it.",
        ingredients={"Branch": 2},
        result_class=WoodenFloor,
        is_placeable=True,
    ),
    Recipe(
        name="Wooden Stairs",
        description="A staircase up to the layer above (the way down appears there too).",
        ingredients={"Branch": 4},
        result_class=WoodenStairs,
        is_placeable=True,
    ),
]