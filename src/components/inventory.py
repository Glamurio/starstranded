from __future__ import annotations

from typing import List, TYPE_CHECKING

from components.base_component import BaseComponent
from world import GameMap

if TYPE_CHECKING:
    from entity import Entity, Item


class Inventory(BaseComponent):
    parent: Entity

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.items: List[Item] = []

    def loot(self, item: Item) -> None:
        """
        Adds an item to the inventory and removes it from the original location.
        """

        if isinstance(item.parent, GameMap):
            self.gamemap.entities.remove(item)
        elif isinstance(item.parent, Inventory):
            item.parent.items.remove(item)

        item.parent = self.parent.inventory
        self.items.append(item)

        # self.engine.message_log.add_message(f"You looted {item.get_title()}.")

    def drop(self, item: Item) -> None:
        """
        Removes an item from the inventory and restores it to the game map, at the player's current location.
        """
        self.items.remove(item)
        item.place(self.parent.x, self.parent.y, self.gamemap)

        self.engine.message_log.add_message(f"You dropped {item.get_title()}.")