from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from components.base_component import BaseComponent
from equipment_types import EquipmentType

if TYPE_CHECKING:
    from entity import Unit
    from components.equippable import Equippable

# TODO: Rename Equipment to "EquipSlots" or something
class Equipment(BaseComponent):
    parent: Unit

    def __init__(self, weapon: Optional[Equippable] = None, armor: Optional[Equippable] = None):
        self.weapon = weapon
        self.armor = armor

    @property
    def defense_bonus(self) -> int:
        bonus = 0

        if self.weapon is not None and self.weapon is not None:
            bonus += self.weapon.defense_bonus

        if self.armor is not None and self.armor is not None:
            bonus += self.armor.defense_bonus

        return bonus

    @property
    def power_bonus(self) -> int:
        bonus = 0

        if self.weapon is not None and self.weapon is not None:
            bonus += self.weapon.power_bonus

        if self.armor is not None and self.armor is not None:
            bonus += self.armor.power_bonus

        return bonus

    def unequip_message(self, item_name: str) -> None:
        self.game_map.engine.message_log.add_message(
            f"You remove {item_name}."
        )

    def equip_message(self, item_name: str) -> None:
        self.game_map.engine.message_log.add_message(
            f"You equip {item_name}."
        )

    def equip_to_slot(self, slot: str, item: Equippable, add_message: bool) -> None:
        current_item: Equippable = getattr(self, slot)

        if current_item is not None:
            self.unequip_from_slot(slot, add_message)
            current_item.equipped = False

        setattr(self, slot, item)
        item.equipped = True

        if add_message:
            self.equip_message(item.get_title())

    def unequip_from_slot(self, slot: str, add_message: bool) -> None:
        current_item: Equippable = getattr(self, slot)
        current_item.equipped = False

        if add_message:
            self.unequip_message(current_item.get_title())

        setattr(self, slot, None)

    def toggle_equip(self, equippable_item: Equippable, add_message: bool = True) -> None:
        if (
            equippable_item
            and equippable_item.equipment_type == EquipmentType.WEAPON
        ):
            slot = "weapon"
        else:
            slot = "armor"

        equippable_item.toggle_equip()

        if getattr(self, slot) == equippable_item:
            self.unequip_from_slot(slot, add_message)
        else:
            self.equip_to_slot(slot, equippable_item, add_message)