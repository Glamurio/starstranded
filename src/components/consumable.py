from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Union

import actions
import color
import components.ai
import components.inventory
from entity import Item

from exceptions import Impossible
from input_handlers import (
    ActionOrHandler,
    AreaRangedAttackHandler,
    SingleRangedAttackHandler,
)

if TYPE_CHECKING:
    from entity import Unit
    from world import GameMap
    from components.inventory import Inventory


class Consumable(Item):
    def __init__(self):
        Item.__init__(self)

    def activate(self) -> None:
        """Invoke this items ability.

        `action` is the context for this activation.
        """
        self.deplete()

    def deplete(self) -> None:
        """Remove the consumed item from its containing inventory."""
        entity = self
        inventory = entity
        if isinstance(inventory, components.inventory.Inventory):
            inventory.items.remove(entity)


class ConfusionConsumable(Consumable):
    def __init__(self):
        Consumable.__init__(self)
        self.number_of_turns: int = 0

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
    def __init__(self):
        Consumable.__init__(self)
        self.amount: int = 0

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        amount_recovered = consumer.heal(self.amount)

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
        HealingConsumable.__init__(self)
        self.amount = 4
        self.color = (127, 0, 255)
        self.type = "Health Potion"
        self.char = "!"

class FoodConsumable(Consumable):
    def __init__(self):
        Consumable.__init__(self)
        self.hunger_amount: int = 0
        self.thirst_amount: int = 0

    def activate(self, user: Unit) -> None:
        self.consume(user)

    def consume(self, user: Unit) -> None:
        user.handle_hunger(self.hunger_amount)
        user.handle_thirst(self.thirst_amount)

        hunger_restore = f' and lose {self.hunger_amount} hunger' if self.hunger_amount < 0 else f' and restore {self.hunger_amount} hunger' if self.hunger_amount > 0 else ''
        thirst_restore = f' and lose {self.thirst_amount} thirst' if self.thirst_amount < 0 else f' and restore {self.thirst_amount} thirst' if self.thirst_amount > 0 else ''

        self.engine.message_log.add_message(
            f"You consume {self.get_title()}{hunger_restore if hunger_restore else ''}{thirst_restore if thirst_restore else ''}.",
            color.health_recovered,
        )
        self.deplete()

class Meat(FoodConsumable):
    def __init__(self, material: str, parent: Union[GameMap, Inventory]):
        FoodConsumable.__init__(self)
        self.char = "d"
        self.hunger_amount = 10
        self.type = "Meat"
        self.color = color.red
        self.material = material
        self.parent = parent

class FireballDamageConsumable(Consumable):
    def __init__(self):
        Consumable.__init__(self)
        self.damage: int = 0
        self.radius: int = 0

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
        for unit in self.engine.game_map.units:
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
    def __init__(self):
        Consumable.__init__(self)
        self.damage: int = 0
        self.maximum_range: int = 0

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