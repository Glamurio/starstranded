from __future__ import annotations

from typing import List, TYPE_CHECKING

from components.base_component import BaseComponent
from world import GameMap
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

    def loot(self, item: Item) -> None:
        """
        Adds an item to the inventory and removes it from the original location.
        """
        if isinstance(item.parent, GameMap):
            self.game_map.entities.remove(item)
        elif isinstance(item.parent, Inventory):
            item.parent.items.remove(item)

        item.parent = self.parent.inventory
        self.add(item)

        # self.engine.message_log.add_message(f"You looted {item.get_title()}.")

    def drop(self, item: Item) -> None:
        """
        Removes an item from the inventory and restores it to the game map, at the unit's current location.
        """
        if item in self.items:
            self.items.remove(item)
        item.place(self.parent.x, self.parent.y, self.game_map)

        self.engine.message_log.add_message(f"You dropped {item.get_title()}.")

    def add(self, item: Item, placeholder: bool = False) -> None:
        contents = self.items + self.placeholders
        if len(contents) >= self.capacity:
            if self.parent == self.engine.player:
                raise exceptions.Impossible("Your Inventory is full.")
            return

        item.parent = self
        if placeholder:
            self.placeholders.append(item)
        else:
            self.items.append(item)