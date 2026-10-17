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
from input_handlers import (
    ActionOrHandler,
    AreaRangedAttackHandler,
    SingleRangedAttackHandler,
)

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


class ConfusionConsumable(Consumable):
    """Unspawned content (kept from the tutorial)."""

    def __init__(self, kind: ItemKind = defs.CONFUSION_SCROLL):
        Consumable.__init__(self, kind)

    @property
    def number_of_turns(self) -> int:
        return self.kind.turns

    def get_action(self, consumer: Unit) -> Optional[ActionOrHandler]:
        self.engine.message_log.add_message(
            "Select a target location.", color.needs_target
        )
        return SingleRangedAttackHandler(
            self.engine,
            callback=lambda xy: actions.ItemAction(consumer, self, xy),
        )

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        target = action.target_unit

        if not self.engine.game_map.visible[action.target_xy]:
            raise Impossible("You cannot target an area that you cannot see.")
        if not target:
            raise Impossible("You must select an enemy to target.")
        if target is consumer:
            raise Impossible("You cannot confuse yourself!")

        self.engine.message_log.add_message(
            f"The eyes of {target.get_title()} look vacant, as it starts to stumble around!",
            color.status_effect_applied,
        )
        target.ai = components.ai.ConfusedEnemy(
            entity=target, previous_ai=target.ai, turns_remaining=self.number_of_turns,
        )
        self.deplete()


class HealingConsumable(Consumable):
    @property
    def amount(self) -> int:
        return self.kind.heal_amount

    def activate(self, user: Unit) -> None:
        amount_recovered = user.heal(self.amount)

        if amount_recovered > 0:
            self.engine.message_log.add_message(
                f"You use {self.get_title()}, and recover {amount_recovered} HP!",
                color.health_recovered,
            )
            self.deplete()
        else:
            raise Impossible(f"Your health is alreadest_y full.")


class HealthPotion(HealingConsumable):
    def __init__(self):
        HealingConsumable.__init__(self, defs.HEALTH_POTION)


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


class FireballDamageConsumable(Consumable):
    """Unspawned content (kept from the tutorial; `take_damage` does not exist on Unit)."""

    def __init__(self, kind: ItemKind = defs.FIREBALL_SCROLL):
        Consumable.__init__(self, kind)

    @property
    def damage(self) -> int:
        return self.kind.damage

    @property
    def radius(self) -> int:
        return self.kind.radius

    def get_action(self, consumer: Unit) -> AreaRangedAttackHandler:
        self.engine.message_log.add_message(
            "Select a target location.", color.needs_target
        )
        return AreaRangedAttackHandler(
            self.engine,
            radius=self.radius,
            callback=lambda xy: actions.ItemAction(consumer, self, xy),
        )

    def activate(self, action: actions.ItemAction) -> None:
        target_xy = action.target_xy

        if not self.engine.game_map.visible[target_xy]:
            raise Impossible("You cannot target an area that you cannot see.")

        targets_hit = False
        for unit in list(self.engine.game_map.units):
            if unit.distance(*target_xy) <= self.radius:
                self.engine.message_log.add_message(
                    f"{unit.get_title()} is engulfed in a fiery explosion, taking {self.damage} damage!"
                )
                unit.take_damage(self.damage)
                targets_hit = True

        if not targets_hit:
            raise Impossible("There are no targets in the radius.")
        self.deplete()


class LightningDamageConsumable(Consumable):
    """Unspawned content (kept from the tutorial; `take_damage` does not exist on Unit)."""

    def __init__(self, kind: ItemKind = defs.LIGHTNING_SCROLL):
        Consumable.__init__(self, kind)

    @property
    def damage(self) -> int:
        return self.kind.damage

    @property
    def maximum_range(self) -> int:
        return self.kind.max_range

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        target = None
        closest_distance = self.maximum_range + 1.0

        for unit in self.engine.game_map.units:
            if unit is not consumer and self.game_map.visible[unit.x, unit.y]:
                distance = consumer.distance(unit.x, unit.y)

                if distance < closest_distance:
                    target = unit
                    closest_distance = distance

        if target:
            self.engine.message_log.add_message(
                f"A lighting bolt strikes {target.get_title()} with a loud thunder, for {self.damage} damage!"
            )
            target.take_damage(self.damage)
            self.deplete()
        else:
            raise Impossible("No enemy is close enough to strike.")
