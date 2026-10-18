from __future__ import annotations
from entity import EntityCategory

from typing import List, TYPE_CHECKING

from components.base_component import BaseComponent
from entity import SpatialContainer
import exceptions

if TYPE_CHECKING:
    from entity import Entity, Item


class Inventory(BaseComponent):
    """
    Component that represents an entity's inventory
    
    `self.items` are instantiated items
    `self.placeholders` are uninstantiated items
    """
    def __init__(self, parent: Entity, capacity: int):
        self.parent = parent
        self.capacity = capacity
        self.items: List[Item] = []
        self.placeholders: List[Item] = []
        self.contents: List[Item] = self.items + self.placeholders

    def loot(self, item: Item) -> None:
        """
        Adds an item to the inventory and removes it from the original location.
        """
        self.contents = self.items + self.placeholders
        if self.is_full():
            if self.parent == self.engine.player:
                raise exceptions.Impossible("Your Inventory is full.")
            return

        source_plant = getattr(item.parent, "parent", None) if item.parent is not self else None
        if item.parent is not None:
            item.parent.remove_entity(item)  # map or inventory (possibly this one)

        self.add(item)
        if source_plant is not None and getattr(source_plant, "category", None) is EntityCategory.PLANT:
            self._harvest_bonus(item, source_plant)
        # self.engine.message_log.add_message(f"You looted {item.get_title()}.")

    def _harvest_bonus(self, item: Item, plant) -> None:
        """Race modifiers on harvesting: `crop_yield` adds extra pieces (a deterministic remainder is carried, so 1.5
        means every second harvest gives one more), `crop_growth` marks the plant as tended so it grows faster."""
        unit = self.parent
        if not getattr(unit, "kind", None) or not getattr(unit.kind, "grants", None):
            return
        caps = unit.capabilities
        plant.growth_bonus = max(plant.growth_bonus, caps.stat("crop_growth") - 1.0)
        unit.yield_debt = getattr(unit, "yield_debt", 0.0) + caps.stat("crop_yield") - 1.0
        while unit.yield_debt >= 1.0 - 1e-9 and not self.is_full():
            unit.yield_debt -= 1.0
            from components.consumable import Fruit
            extra = type(item)(self, item.kind) if isinstance(item, Fruit) else plant.yield_piece()
            self.add(extra)

    def drop(self, item: Item, target_xy: tuple[int, int]) -> None:
        """
        Removes an item from the inventory and restores it to the game map, at the given location.

        If no location is given, defaults to unit's location.
        """
        if item in self.items:
            self.items.remove(item)

        tile = target_xy if target_xy else (self.parent.x, self.parent.y)
        item.place(tile[0], tile[1], self.game_map)
        self.contents = self.items + self.placeholders
        
        if self.parent is self.engine.player:  # plants drop fruit too; only the player's own drops are announced
            self.engine.message_log.add_message(f"You dropped {item.get_title()}.")

    def add(self, item: Item, placeholder: bool = False) -> None:
        self.contents = self.items + self.placeholders
        if self.is_full():
            if self.parent == self.engine.player:
                raise exceptions.Impossible("Your Inventory is full.")
            return
        
        if isinstance(item.parent, SpatialContainer):
            item.parent.remove_entity(item)
        item.parent = self
        if placeholder:
            self.placeholders.append(item)
        else:
            self.items.append(item)
        self.contents.append(item)

    def remove(self, item: Item, placeholder: bool = False) -> None:
        self.contents = self.items + self.placeholders

        if placeholder:
            self.placeholders.remove(item)
        else:
            self.items.remove(item)
        self.contents.remove(item)

    def remove_entity(self, item: Item) -> None:
        """Container protocol: take `item` out if present (no-op otherwise)."""
        if item in self.items:
            self.remove(item)
        elif item in self.placeholders:
            self.remove(item, placeholder=True)

    def instantiate_placeholders(self):
        for placeholder in self.placeholders:
            self.items.append(placeholder(self))
            self.placeholders.remove(placeholder)

    def is_empty(self):
        return not bool(len(self.contents))

    def is_full(self):
        return len(self.contents) >= self.capacity