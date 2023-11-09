from __future__ import annotations

from typing import TYPE_CHECKING

from components.inventory import Inventory
from components.consumable import Consumable

from utilities import map_codepoints, get_shade, get_gaussian_shade

if TYPE_CHECKING:
    from components.plant import Tree


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