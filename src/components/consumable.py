from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Union

import actions
import color
import components.ai
from components.inventory import Inventory
from entity import Item
import species as defs
from species import ItemKind

from exceptions import Impossible

if TYPE_CHECKING:
    from entity import Unit
    from world import GameMap


class Consumable(Item):
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


class FoodConsumable(Consumable):
    @property
    def hunger_amount(self) -> int:
        return self.kind.hunger_amount

    @property
    def thirst_amount(self) -> int:
        return self.kind.thirst_amount

    def activate(self, user: Unit) -> None:
        message = self.consume(user)
        if user == self.engine.player and message:
            self.engine.message_log.add_message(message, color.health_recovered)

    def consume(self, user: Unit) -> str:
        user.handle_hunger(self.hunger_amount)
        user.handle_thirst(self.thirst_amount)

        hunger_restore = f' and loses {self.hunger_amount} hunger' if self.hunger_amount < 0 else f' and restores {self.hunger_amount} hunger' if self.hunger_amount > 0 else ''
        thirst_restore = f' and loses {self.thirst_amount} thirst' if self.thirst_amount < 0 else f' and restores {self.thirst_amount} thirst' if self.thirst_amount > 0 else ''

        self.deplete()

        message = f"{user.get_title()} consumes {self.get_title()}{hunger_restore if hunger_restore else ''}{thirst_restore if thirst_restore else ''}."
        return message


class Meat(FoodConsumable):
    def __init__(self, material: str, parent: Union[GameMap, Inventory, None] = None):
        FoodConsumable.__init__(self, defs.MEAT)
        self.material = material  # which creature it came from
        self.parent = parent


class Fruit(FoodConsumable):
    def __init__(self, parent: Union[GameMap, Inventory, None] = None, kind: Optional[ItemKind] = None):
        """`kind` is the fruit kind of the plant that grew it; without one a random fruit is rolled."""
        FoodConsumable.__init__(self, kind or defs.make_fruit_kind())
        self.parent = parent

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        material_type = f'{self.material} {self.species}' if self.material else self.species
        description = f'{" ".join(attributes)} {material_type}' if attributes else material_type
        return f'{self.name}, the {description}' if self.name else description
