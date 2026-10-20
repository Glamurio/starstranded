from __future__ import annotations

import random
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
    nutrition = "plant"  # what kind of eater can digest it: "plant" or "meat"

    @property
    def hunger_amount(self) -> int:
        return self.kind.hunger_amount

    @property
    def thirst_amount(self) -> int:
        return self.kind.thirst_amount

    def activate(self, user: Unit) -> None:
        if not user.can_eat(self):
            raise Impossible(f"{user.get_title()} cannot digest {self.get_title()}.")
        message = self.consume(user)
        if user == self.engine.player and message:
            self.engine.message_log.add_message(message, color.health_recovered)

    def consume(self, user: Unit) -> str:
        user.handle_hunger(self.hunger_amount)
        user.handle_thirst(self.thirst_amount)

        hunger_restore = f' and loses {self.hunger_amount} hunger' if self.hunger_amount < 0 else f' and restores {self.hunger_amount} hunger' if self.hunger_amount > 0 else ''
        thirst_restore = f' and loses {self.thirst_amount} thirst' if self.thirst_amount < 0 else f' and restores {self.thirst_amount} thirst' if self.thirst_amount > 0 else ''

        self.deplete()
        poison = int(getattr(self.kind, "toxicity", 0) or 0) * 2          # (a toxic fruit poisons: one damage a turn)
        if poison:
            user.apply_poison(poison)

        message = f"{user.get_title()} consumes {self.get_title()}{hunger_restore if hunger_restore else ''}{thirst_restore if thirst_restore else ''}."
        if poison:
            message += " It was poisonous!"
        return message


MEAT_HUNGER = (7, 8, 9, 10, 11, 12, 14)
"""How much hunger a piece of meat restores: rolled per piece."""


class Meat(FoodConsumable):
    nutrition = "meat"

    def __init__(self, material: str, parent: Union[GameMap, Inventory, None] = None, source=None):
        FoodConsumable.__init__(self, defs.MEAT)
        self._material = material  # which creature it came from
        self.source = source       # that creature's kind: the name is looked up live, so it updates once the species is learned
        self.parent = parent
        self.nourishment = random.choice(MEAT_HUNGER)       # every carcass is a little different

    @property
    def hunger_amount(self) -> int:
        return getattr(self, "nourishment", None) or self.kind.hunger_amount

    @property
    def material(self) -> str:
        key = getattr(self.source, "key", None)
        if isinstance(key, str) and key.startswith("planet:"):
            import lore
            return lore.species_name(lore.run_of(self), self.source)
        return self._material

    @material.setter
    def material(self, value) -> None:
        self._material = value


class Ration(FoodConsumable):
    """Processed food from a sponsor's supply crate: any race digests it."""
    nutrition = "ration"

    def __init__(self, parent: Union[GameMap, Inventory, None] = None):
        FoodConsumable.__init__(self, defs.RATION)
        self.parent = parent


class Fruit(FoodConsumable):
    def __init__(self, parent: Union[GameMap, Inventory, None] = None, kind: Optional[ItemKind] = None):
        """`kind` is the fruit kind of the plant that grew it; without one a random fruit is rolled."""
        FoodConsumable.__init__(self, kind or defs.make_fruit_kind())
        self.parent = parent

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        species = self.species
        if getattr(self.kind, "parent_key", None):        # a fruit is only called by its name once it has been scanned
            import lore
            species = lore.fruit_name(lore.run_of(self), self.kind)
        material_type = f'{self.material} {species}' if self.material else species
        description = f'{" ".join(attributes)} {material_type}' if attributes else material_type
        import naming
        return f'{self.name}, the {description}' if self.name else (naming.lower_first(description) if self.kind.key else description)
