from __future__ import annotations

from entity import Item
from equipment_types import EquipmentType
from typing import TYPE_CHECKING, Optional, Union
import species as defs
from species import ItemKind

if TYPE_CHECKING:
    from components.unit import Unit
    from world import GameMap
    from components.inventory import Inventory

# TODO: Rename Equippable to "Equipment" once I refactored that
class Equippable(Item):
    """An item that can be worn or wielded. Bonuses come from the kind; `equipped` is per instance."""

    def __init__(self, kind: ItemKind, parent: Union[GameMap, Inventory, None] = None):
        Item.__init__(self, kind)
        self.parent = parent
        self.equipped: bool = False

    @property
    def equipment_type(self) -> Optional[EquipmentType]:
        return self.kind.equipment_type

    @property
    def power_bonus(self) -> int:
        return self.kind.power_bonus

    @property
    def defense_bonus(self) -> int:
        return self.kind.defense_bonus

    @property
    def damage_type(self):
        return self.kind.damage_type

    def activate(self, user: Unit) -> None:
        """Invoke this items ability.

        `action` is the context for this activation.
        """
        # self.toggle_equip()
        pass

    def toggle_equip(self):
        self.equipped = not self.equipped

class Dagger(Equippable):
    def __init__(self, parent: Union[GameMap, Inventory, None] = None) -> None:
        Equippable.__init__(self, defs.DAGGER, parent)


class Axe(Equippable):
    def __init__(self, parent: Union[GameMap, Inventory, None] = None) -> None:
        Equippable.__init__(self, defs.AXE, parent)

class LeatherArmor(Equippable):
    def __init__(self, parent: Union[GameMap, Inventory, None] = None) -> None:
        Equippable.__init__(self, defs.LEATHER_ARMOR, parent)

