from __future__ import annotations

import color
from entity import Item
from equipment_types import EquipmentType
from typing import TYPE_CHECKING, Union
from utilities import map_codepoints

if TYPE_CHECKING:
    from components.unit import Unit
    from world import GameMap
    from components.inventory import Inventory

# TODO: Rename Equippable to "Equipment" once I refactored that
class Equippable(Item):
    def __init__(self):
        Item.__init__(self)
        self.equipment_type: EquipmentType = None
        self.power_bonus: int = 0
        self.defense_bonus: int = 0
        self.equipped: bool = False

    def activate(self, user: Unit) -> None:
        """Invoke this items ability.

        `action` is the context for this activation.
        """
        # self.toggle_equip()
        pass

    def toggle_equip(self):
        self.equipped = not self.equipped

class Dagger(Equippable):
    def __init__(self, parent: Union[GameMap, Inventory]) -> None:
        Equippable.__init__(self)
        self.parent = parent
        self.equipment_type = EquipmentType.WEAPON
        self.power_bonus = 2
        self.material="Bronze"
        self.object_type="Dagger"
        self.sprite_pos = (44, 21)
        char_info = map_codepoints(self.object_type, self.sprite_pos)
        self.char = char_info["sprite"]
        self.color=(0, 191, 255)


class Sword(Equippable):
    def __init__(self, parent: Union[GameMap, Inventory]) -> None:
        Equippable.__init__(self)
        self.parent = parent
        self.equipment_type = EquipmentType.WEAPON
        self.power_bonus = 4
        self.material="Iron"
        self.object_type="Sword"
        self.char="\\"
        self.color=(0, 191, 255)

class LeatherArmor(Equippable):
    def __init__(self, parent: Union[GameMap, Inventory]) -> None:
        Equippable.__init__(self)
        self.parent = parent
        self.equipment_type = EquipmentType.ARMOR
        self.defense_bonus = 1
        self.material="Leather"
        self.object_type="Armor"
        self.sprite_pos = (31, 23)
        char_info = map_codepoints(self.object_type, self.sprite_pos)
        self.char = char_info["sprite"]
        self.color=color.brown

class ChainMail(Equippable):
    def __init__(self, parent: Union[GameMap, Inventory]) -> None:
        Equippable.__init__(self)
        self.parent = parent
        self.equipment_type = EquipmentType.ARMOR
        self.defense_bonus = 3
        self.material="Iron"
        self.object_type="Chain Mail"
        self.char="]"
        self.color=(139, 69, 19)