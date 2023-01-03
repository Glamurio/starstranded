from __future__ import annotations
from time import sleep

from typing import List, Optional, Tuple, TYPE_CHECKING
import color
import exceptions
import time

from utilities import can_move
from entity import Actor

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity, Item


class Action:
    def __init__(self, entity: Actor) -> None:
        super().__init__()
        self.entity = entity

    @property
    def engine(self) -> Engine:
        """Return the engine this action belongs to."""
        return self.entity.game_map.engine

    def perform(self) -> bool:
        """Perform this action with the objects needed to determine its scope.

        `self.engine` is the scope this action is being performed in.

        `self.entity` is the object performing the action.

        If the action is supposed to pass time, it must be inherited via `super().perform()`.

        If the action is supposed to repeat, return `True`.
        """
        # Always pass time when an action occurs
        self.engine.game_world.pass_time(actor=self.entity, time=1)

        return False


class PickupAction(Action):
    """Pickup an item and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Actor, item: Item):
        super().__init__(entity)

        self.item = item

    def perform(self) -> None:
        super().perform()

        if len(self.entity.inventory.items) >= self.entity.inventory.capacity:
            raise exceptions.Impossible("Your inventory is full.")

        self.entity.inventory.loot(self.item)

        self.engine.message_log.add_message(f"You picked up {self.item.get_title()}!")


class ItemAction(Action):
    def __init__(
        self, entity: Actor, item: Item, target_xy: Optional[Tuple[int, int]] = None
    ):
        super().__init__(entity)
        self.item = item
        if not target_xy:
            target_xy = entity.x, entity.y
        self.target_xy = target_xy

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

    def perform(self) -> None:
        """Invoke the items ability, this action will be given to provide context."""
        super().perform()

        if self.item.consumable:
            self.item.consumable.activate(self)


class DropItem(ItemAction):
    def perform(self) -> None:
        super().perform()

        if self.entity.equipment.item_is_equipped(self.item):
            self.entity.equipment.toggle_equip(self.item)

        self.entity.inventory.drop(self.item)


class EquipAction(Action):
    def __init__(self, entity: Actor, item: Item):
        super().__init__(entity)

        self.item = item

    def perform(self) -> None:
        self.entity.equipment.toggle_equip(self.item)


class WaitAction(Action):
    def perform(self) -> None:
        super().perform()


class TakeStairsAction(Action):
    def perform(self) -> None:
        """
        Take the stairs, if any exist at the entity's location.
        """
        # TODO: Rework into general transition action
        super().perform()

        if (self.entity.x, self.entity.y) == self.engine.game_map.downstairs_location:
            self.engine.game_world.generate_floor()
            self.engine.message_log.add_message(
                "You descend the staircase.", color.descend
            )
        else:
            raise exceptions.Impossible("There are no stairs here.")


class ActionWithDirection(Action):
    def __init__(self, entity: Actor, dest_x: int, dest_y: int):
        super().__init__(entity)

        self.dest_x = dest_x
        self.dest_y = dest_y

    @property
    def dest_xy(self) -> Tuple[int, int]:
        """Returns this action's destination."""
        return self.dest_x, self.dest_y

    @property
    def blocking_entity(self) -> Optional[Entity]:
        """Return the blocking entity at this actions destination.."""
        return self.engine.game_map.get_blocking_entity_at_location(*self.dest_xy)

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.dest_xy)

    def get_path(self, ai, x: int, y: int) -> List[Tuple]:
        from utilities import get_path_to

        return get_path_to(self.engine, ai, x, y)

    def perform(self) -> None:
        super().perform()


class MeleeAction(ActionWithDirection):
    def perform(self) -> None:
        super().perform()

        target = self.target_actor

        if not target:
            raise exceptions.Impossible("Nothing to attack.")
        if self.entity == target:
            return WaitAction(self.entity).perform()

        damage = self.entity.unit.power - target.unit.defense

        attack_desc = f"{self.entity.get_title()} attacks {target.get_title()}"
        if self.entity is self.engine.player:
            attack_color = color.player_atk
        else:
            attack_color = color.enemy_atk
        if damage > 0:
            self.engine.message_log.add_message(
                f"{attack_desc} for {damage} hit points.", attack_color
            )
            target.unit.hp -= damage
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.", attack_color
            )


class MovementAction(ActionWithDirection):

    def __init__(self, entity: Actor, dest_x: int, dest_y: int, path: List[Tuple] = []):
        super().__init__(entity, dest_x, dest_y)

        self.dest_x = dest_x
        self.dest_y = dest_y
        self.path = path

    def perform(self) -> bool:

        if not self.path:
            raise exceptions.Impossible("That way is blocked.")

        self.dest_x, self.dest_y = self.path.pop(0)

        if not can_move(self.engine, self.dest_x, self.dest_y):
            raise exceptions.Impossible("That way is blocked.")

        self.entity.move(self.dest_x, self.dest_y)
        self.engine.game_world.pass_time(actor=self.entity, time=1)

        if not self.entity.type == "Player":
            return

        # Move player until an enemy is visible
        for enemy in self.engine.game_map.entities:
            if not isinstance(enemy, Actor):
                continue
            if self.entity == enemy:
                continue
            if not enemy.has_ai:
                continue
            if self.engine.can_see(self.entity.x, self.entity.y, enemy.x, enemy.y, 8):
                return False

        # TODO: Stagger player movement
        return True


class BumpAction(ActionWithDirection):

    def perform(self) -> None:
        path: List[Tuple] = self.get_path(self.entity.ai, self.dest_x, self.dest_y)

        distance = max(abs(self.dest_x - self.entity.x), abs(self.dest_y - self.entity.y))  # Chebyshev distance.
        
        if self.target_actor and distance <= 1:
            return MeleeAction(self.entity, self.dest_x, self.dest_y).perform()

        return MovementAction(self.entity, self.dest_x, self.dest_y, path).perform()