from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING
import color
import exceptions

if TYPE_CHECKING:
    from components.unit import Unit
    from engine import Engine
    from entity import Entity, Item
    from crafting import Recipe


class Action:
    def __init__(self, entity: Unit) -> None:
        super().__init__()
        self.entity = entity

    @property
    def engine(self) -> Engine:
        """Return the engine this action belongs to."""
        return self.entity.game_map.engine

    @property
    def target_unit(self) -> Optional[Unit]:
        """Return the unit at this actions destination."""
        return self.engine.game_map.get_unit_at_location(*self.dest_xy)

    def perform(self) -> bool:
        """Perform this action with the objects needed to determine its scope.

        `self.engine` is the scope this action is being performed in.

        `self.entity` is the object performing the action.

        If the action is supposed to pass time, it must be inherited via `super().perform()`.

        If the action is supposed to repeat, return `True`.
        """
        # Always pass time when an action occurs
        self.engine.game_world.pass_time(unit=self.entity, time=1)

        return False


class PickupAction(Action):
    """Pickup an item and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Unit, item: Item):
        super().__init__(entity)

        self.item = item

    def perform(self) -> None:
        # super().perform()

        self.entity.inventory.loot(self.item)
        self.engine.message_log.add_message(f"You picked up {self.item.get_title()}!")

class MassPickupAction(Action):
    """Pickup a list of items and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Unit, items: List[Item]):
        super().__init__(entity)
        self.items = items

    # TODO: Rework so that it takes more time per item, also fix multi-pickup
    def perform(self) -> None:
        # item = self.items.pop()
        # if not item:
        #     return False
        # if not hasattr(item, 'inventory'):
        #     return False
        # self.entity.inventory.loot(item)
        # self.engine.message_log.add_message(f"You picked up {item.get_title()}!")
        # return True
        for item in reversed(self.items):
            if hasattr(item, 'inventory'):
                continue
            self.entity.inventory.loot(item)
            self.engine.message_log.add_message(f"You picked up {item.get_title()}!")
            


class ItemAction(Action):
    def __init__(self, entity: Unit, item: Item, target_xy: Optional[Tuple[int, int]] = None):
        super().__init__(entity)
        self.action = 'activate'
        self.item = item
        
        if not target_xy:
            target_xy = entity.x, entity.y
        self.target_xy = target_xy

    def perform(self) -> None:
        """Invoke the items ability, this action will be given to provide context."""
        super().perform()

        if self.item and self.action == 'activate':
            self.item.activate(self.entity)


class DropItem(ItemAction):
    def __init__(self, entity: Unit, item: Item, target_xy: Optional[Tuple[int, int]] = None):
        super().__init__(entity, item, target_xy)
        self.action = 'drop'

    def perform(self) -> None:
        super().perform()

        if hasattr(self.item, 'equipped') and self.item.equipped:
            self.entity.equipment.toggle_equip(self.item)

        self.entity.inventory.drop(self.item, self.target_xy)


class EquipAction(Action):
    def __init__(self, entity: Unit, item: Item):
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
    def __init__(self, entity: Unit, dest_x: int, dest_y: int):
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
        return self.engine.game_map.get_entities_at_location(*self.dest_xy, True)

    def get_path(self, ai, x: int, y: int) -> List[Tuple]:
        return self.engine.get_path_to(ai, x, y)

    def perform(self) -> None:
        super().perform()


class MeleeAction(ActionWithDirection):
    def perform(self) -> None:

        attacker: Unit = self.entity
        target: Unit = self.target_unit

        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        if attacker == target:
            return

        damage = attacker.power - target.defense

        attack_desc = f"{attacker.get_title()} attacks {target.get_title()}"
        if attacker is self.engine.player:
            attack_color = color.player_atk
        else:
            attack_color = color.enemy_atk
        if damage > 0:
            self.engine.message_log.add_message(
                f"{attack_desc} for {damage} hit points.", attack_color
            )
            target.handle_health(-damage, attacker)
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.", attack_color
            )
            
        self.engine.game_world.pass_time(unit=self.entity, time=1)

class MovementAction(ActionWithDirection):

    def __init__(self, entity: Unit, dest_x: int, dest_y: int, path: List[Tuple] = []):
        super().__init__(entity, dest_x, dest_y)

        self.dest_x = dest_x
        self.dest_y = dest_y
        self.path = path

    def perform(self) -> bool:

        if not self.path:
            raise exceptions.Impossible("That way is blocked.")

        self.dest_x, self.dest_y = self.path.pop(0)

        if not self.engine.can_move(self.dest_x, self.dest_y):
            raise exceptions.Impossible("That way is blocked.")

        self.entity.move(self.dest_x, self.dest_y)
        self.engine.game_world.pass_time(unit=self.entity, time=1)

        if not self.entity == self.engine.player:
            return

        # Move player until an enemy is visible
        for enemy in self.engine.game_map.entities:
            if self.entity == enemy:
                continue
            if hasattr(enemy, "material"):
                continue
            if hasattr(enemy, "growth_cycle"):
                continue
            if hasattr(enemy, "ai"):
                if not enemy.ai or not enemy.ai.is_hostile:
                    continue
            
            if self.engine.can_see(self.entity.x, self.entity.y, enemy.x, enemy.y, 8):
                return False

        return True


class BumpAction(ActionWithDirection):

    def perform(self) -> None:
        path: List[Tuple] = self.get_path(self.entity.ai, self.dest_x, self.dest_y)

        distance = max(abs(self.dest_x - self.entity.x), abs(self.dest_y - self.entity.y))  # Chebyshev distance.

        if self.target_unit and not self.target_unit == self.entity and self.target_unit.is_alive and distance <= 1:
            return MeleeAction(self.entity, self.dest_x, self.dest_y).perform()

        return MovementAction(self.entity, self.dest_x, self.dest_y, path).perform()
    
class CraftAction(Action):
    """Craft a recipe from the player's inventory."""

    def __init__(self, entity: Unit, recipe: Recipe):
        super().__init__(entity)
        self.recipe = recipe

    def perform(self) -> None:

        inventory = self.entity.inventory

        if not self.recipe.can_craft(inventory):
            raise exceptions.Impossible("You don't have the required materials.")

        result = self.recipe.craft(inventory)

        if self.recipe.is_placeable:
            # Place it at the player's feet
            result.place(self.entity.x, self.entity.y, self.engine.game_map)
            self.engine.message_log.add_message(
                f"You crafted a {self.recipe.name} and placed it at your feet.",
                color.white,
            )
        else:
            inventory.add(result)
            self.engine.message_log.add_message(
                f"You crafted a {self.recipe.name}!",
                color.white,
            )

        self.engine.game_world.pass_time(unit=self.entity, time=1)


class InteractAction(Action):
    """Interact with an entity at the player's location (e.g. toggle a campfire)."""

    def __init__(self, entity: Unit):
        super().__init__(entity)

    def perform(self) -> None:
        from crafting import Campfire

        entities = self.engine.game_map.get_entities_at_location(
            self.entity.x, self.entity.y
        )

        for target in entities:
            if isinstance(target, Campfire):
                message = target.toggle()
                self.engine.message_log.add_message(message, color.orange if target.is_lit else color.white)
                self.engine.update_fov()  # Refresh FOV to show/hide campfire light
                self.engine.game_world.pass_time(unit=self.entity, time=1)
                return

        raise exceptions.Impossible("There's nothing to interact with here.")