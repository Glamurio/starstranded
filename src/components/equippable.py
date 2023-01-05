from __future__ import annotations

import color
from entity import Item
from equipment_types import EquipmentType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from components.unit import Unit

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
    def __init__(self) -> None:
        Equippable.__init__(self)
        self.equipment_type = EquipmentType.WEAPON
        self.power_bonus = 2
        self.char="/"
        self.color=(0, 191, 255)
        self.material="Bronze"
        self.kind="Dagger"


class Sword(Equippable):
    def __init__(self) -> None:
        Equippable.__init__(self)
        self.equipment_type = EquipmentType.WEAPON
        self.power_bonus = 4
        self.char="\\"
        self.color=(0, 191, 255)
        self.material="Iron"
        self.kind="Sword"

class LeatherArmor(Equippable):
    def __init__(self) -> None:
        Equippable.__init__(self)
        self.equipment_type = EquipmentType.ARMOR
        self.defense_bonus = 1
        self.char="["
        self.color=color.brown
        self.material="Leather"
        self.kind="Armor"

class ChainMail(Equippable):
    def __init__(self) -> None:
        Equippable.__init__(self)
        self.equipment_type = EquipmentType.ARMOR
        self.defense_bonus = 3
        self.char="]"
        self.color=(139, 69, 19)
        self.material="Iron"
        self.kind="Chain Mail"