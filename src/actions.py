from __future__ import annotations
from time import sleep

from typing import List, Optional, Tuple, TYPE_CHECKING
import color
import exceptions

if TYPE_CHECKING:
    from engine import Engine
    from entity import Actor, Entity, Item


class Action:
    def __init__(self, entity: Actor) -> None:
        super().__init__()
        self.entity = entity

    @property
    def engine(self) -> Engine:
        """Return the engine this action belongs to."""
        return self.entity.gamemap.engine

    def perform(self) -> None:
        """Perform this action with the objects needed to determine its scope.

        `self.engine` is the scope this action is being performed in.

        `self.entity` is the object performing the action.

        This method must be overridden by Action subclasses.
        """
        raise NotImplementedError()


class PickupAction(Action):
    """Pickup an item and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Actor):
        super().__init__(entity)

    def perform(self) -> None:
        actor_location_x = self.entity.x
        actor_location_y = self.entity.y
        actor_inventory = self.entity.inventory

        if len(actor_inventory.items) >= actor_inventory.capacity:
            raise exceptions.Impossible("Your inventory is full.")

        for entity in self.engine.game_map.entities:
            if entity.type == "Player":
                continue
            
            if not (actor_location_x == entity.x and actor_location_y == entity.y):
                continue

            if not entity.inventory:
                continue
                
            for item in entity.inventory.items:

                #TODO: Inventory Screen for looting

                entity.inventory.items.remove(item)
                item.parent = self.entity.inventory
                actor_inventory.items.append(item)

                self.engine.message_log.add_message(f"You looted {item.get_title()} from {entity.get_title()} !")
            return

        for item in self.engine.game_map.items:

            if not (actor_location_x == item.x and actor_location_y == item.y):
                continue

            self.engine.game_map.entities.remove(item)
            item.parent = self.entity.inventory
            actor_inventory.items.append(item)

            self.engine.message_log.add_message(f"You picked up {item.get_title()}!")
            return

        raise exceptions.Impossible("There is nothing here to pick up.")


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

        if self.item.consumable:
            self.item.consumable.activate(self)


class DropItem(ItemAction):
    def perform(self) -> None:
        self.engine.game_world.pass_time(actor=self.entity, time=1)

        if self.entity.equipment.item_is_equipped(self.item):
            self.entity.equipment.toggle_equip(self.item)

        self.entity.inventory.drop(self.item)


class EquipAction(Action):
    def __init__(self, entity: Actor, item: Item):
        super().__init__(entity)

        self.item = item

    def perform(self) -> None:
        self.engine.game_world.pass_time(actor=self.entity, time=1)

        self.entity.equipment.toggle_equip(self.item)


class WaitAction(Action):
    def perform(self) -> None:
        self.engine.game_world.pass_time(actor=self.entity, time=1)


class TakeStairsAction(Action):
    def perform(self) -> None:
        """
        Take the stairs, if any exist at the entity's location.
        """
        self.engine.game_world.pass_time(actor=self.entity, time=1)

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

        return get_path_to(ai, x, y)

    def perform(self) -> None:
        raise NotImplementedError()


class MeleeAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        damage = self.entity.unit.power - target.unit.defense

        attack_desc = f"{self.entity.get_title().capitalize()} attacks {target.get_title()}"
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

    def perform(self) -> None:
        from utilities import can_move

        if self.path:
            x, y = self.path.pop()
            return MovementAction(self.entity, x, y, self.path).perform()

        if can_move(self.engine, self.dest_x, self.dest_y):
            self.entity.move(self.dest_x, self.dest_y)
        
        else:
            raise exceptions.Impossible("That way is blocked.")


class BumpAction(ActionWithDirection):

    def perform(self) -> None:
        
        self.engine.game_world.pass_time(actor=self.entity, time=1)
        path: List[Tuple] = self.get_path(self.entity.ai, self.dest_x, self.dest_y)

        distance = max(abs(self.dest_x - self.entity.x), abs(self.dest_y - self.entity.y))  # Chebyshev distance.
        
        if self.target_actor and distance <= 1:
            return MeleeAction(self.entity, self.dest_x, self.dest_y).perform()

        return MovementAction(self.entity, self.dest_x, self.dest_y, path).perform()