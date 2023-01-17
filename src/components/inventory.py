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
        self.contents: List[Item] = self.items + self.placeholders

    def loot(self, item: Item) -> None:
        """
        Adds an item to the inventory and removes it from the original location.
        """
        if isinstance(item.parent, GameMap):
            self.game_map.entities.remove(item)
        elif isinstance(item.parent, Inventory):
            item.parent.items.remove(item)

        self.add(item)
        # self.engine.message_log.add_message(f"You looted {item.get_title()}.")

    def drop(self, item: Item) -> None:
        """
        Removes an item from the inventory and restores it to the game map, at the unit's current location.
        """
        if item in self.items:
            self.items.remove(item)
        item.place(self.parent.x, self.parent.y, self.game_map)
        self.contents = self.items + self.placeholders
        
        self.engine.message_log.add_message(f"You dropped {item.get_title()}.")

    def add(self, item: Item, placeholder: bool = False) -> None:
        self.contents = self.items + self.placeholders
        if len(self.contents) >= self.capacity:
            if self.parent == self.engine.player:
                raise exceptions.Impossible("Your Inventory is full.")
            return
        
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

    def instantiate_placeholders(self):
        for placeholder in self.placeholders:
            self.items.append(placeholder(self))
            self.placeholders.remove(placeholder)

    def is_empty(self):
        return not bool(len(self.contents))