from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING
import color
import exceptions
from entity import EntityCategory

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

    @property
    def target_plant(self) -> Optional[Entity]:
        """Return the living plant at this actions destination (the one that blocks movement first)."""
        plants = [e for e in self.engine.game_map.get_entities_at_location(*self.dest_xy)
                  if e.category is EntityCategory.PLANT and not e.dead]
        return next((p for p in plants if p.blocks_movement), plants[0] if plants else None)

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
        for item in reversed(self.items):
            if item.has_inventory:  # units/plants are containers, not loot
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

        from components.equippable import Equippable
        if isinstance(self.item, Equippable) and self.item.equipped:
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
    """Use the staircase under the entity: `direction` +1 climbs, -1 descends, 0 (default) takes whichever is here."""

    def __init__(self, entity: Unit, direction: int = 0):
        super().__init__(entity)
        self.direction = direction

    def perform(self) -> None:
        super().perform()
        game_world = self.engine.game_world
        before = game_world.current_z
        game_world.take_stairs(self.direction)
        self.engine.message_log.add_message(
            "You climb the staircase." if game_world.current_z > before else "You descend the staircase.", color.descend
        )


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

    def get_path(self, x: int, y: int) -> List[Tuple]:
        return self.engine.get_path_to(self.entity, x, y)

    def perform(self) -> None:
        super().perform()


class MeleeAction(ActionWithDirection):
    """Hit the unit (or, failing that, the plant) at the destination with the attacker's damage type."""

    def perform(self) -> None:
        from damage import resolve

        attacker: Unit = self.entity
        target = self.target_unit or self.target_plant

        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        if attacker == target:
            return

        damage_type = attacker.damage_type
        damage = resolve(attacker.power, getattr(target, "defense", 0), damage_type, target.resistances())

        attack_desc = f"{attacker.get_title()} attacks {target.get_title()}"
        if attacker is self.engine.player:
            attack_color = color.player_atk
        else:
            attack_color = color.enemy_atk
        world = self.engine.game_map  # fights the player cannot see are not reported
        seen = target is self.engine.player or world.is_visible(attacker.x, attacker.y) or world.is_visible(target.x, target.y)
        if damage > 0:
            if seen:
                self.engine.message_log.add_message(
                    f"{attack_desc} for {damage} {damage_type} damage.", attack_color
                )
            target.handle_health(-damage, attacker)
        elif seen:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.", attack_color
            )

        self.engine.game_world.pass_time(unit=self.entity, time=1)

class MovementAction(ActionWithDirection):

    def __init__(self, entity: Unit, dest_x: int, dest_y: int, path: Optional[List[Tuple]] = None):
        super().__init__(entity, dest_x, dest_y)

        self.dest_x = dest_x
        self.dest_y = dest_y
        self.path = path if path is not None else []

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

        # Move player until an enemy is visible (an enemy = a unit with a hostile AI)
        for enemy in self.engine.game_map.actors:
            if enemy is self.entity or enemy.category is not EntityCategory.UNIT:
                continue
            if not enemy.ai.is_hostile:
                continue
            if max(abs(enemy.x - self.entity.x), abs(enemy.y - self.entity.y)) > 8:
                continue  # cheap reject before the line-of-sight test

            if self.engine.can_see(self.entity.x, self.entity.y, enemy.x, enemy.y, 8):
                return False

        return True


class BumpAction(ActionWithDirection):

    def perform(self) -> None:
        path: List[Tuple] = self.get_path(self.dest_x, self.dest_y)

        distance = max(abs(self.dest_x - self.entity.x), abs(self.dest_y - self.entity.y))  # Chebyshev distance.

        if self.target_unit and not self.target_unit == self.entity and self.target_unit.is_alive and distance <= 1:
            return MeleeAction(self.entity, self.dest_x, self.dest_y).perform()

        # A wielded weapon (an axe, say) lets you cut down a plant that is in the way; bare hands just bump.
        plant = self.target_plant
        if plant is not None and plant.blocks_movement and distance <= 1 and self.entity.equipment.weapon is not None:
            return MeleeAction(self.entity, self.dest_x, self.dest_y).perform()

        return MovementAction(self.entity, self.dest_x, self.dest_y, path).perform()
    
class CraftAction(Action):
    """Craft a recipe and add the result to inventory."""

    def __init__(self, entity: Unit, recipe):
        super().__init__(entity)
        self.recipe = recipe

    def perform(self) -> None:
        inventory = self.entity.inventory

        if not self.recipe.can_craft(inventory):
            raise exceptions.Impossible("You don't have the required materials.")

        result = self.recipe.craft(inventory)
        inventory.add(result)

        hint = " Use it from your inventory to place it." if self.recipe.is_placeable else ""
        self.engine.message_log.add_message(
            f"You crafted a {self.recipe.name}!{hint}",
            color.menu_text,
        )

        self.engine.game_world.pass_time(unit=self.entity, time=1)


class InteractAction(Action):
    """Interact with an entity at the player's location."""

    def __init__(self, entity: Unit):
        super().__init__(entity)

    def perform(self) -> None:
        from crafting import Campfire

        entities = self.engine.game_map.get_entities_at_location(
            self.entity.x, self.entity.y
        )

        for target in entities:
            if isinstance(target, Campfire) and target.is_placed:
                message = target.toggle()
                self.engine.message_log.add_message(
                    message,
                    color.orange if target.is_lit else color.white,
                )
                self.engine.update_fov()
                self.engine.game_world.pass_time(unit=self.entity, time=1)
                return

        raise exceptions.Impossible("There's nothing to interact with here.")
    
class PlaceConstructableAction(Action):
    """Place a constructable item from inventory onto the map."""

    def __init__(self, entity: Unit, item, dest_x: int, dest_y: int):
        super().__init__(entity)
        self.item = item
        self.dest_x = dest_x
        self.dest_y = dest_y

    def perform(self) -> None:
        # Check distance — must be current tile or adjacent
        dx = abs(self.dest_x - self.entity.x)
        dy = abs(self.dest_y - self.entity.y)
        if dx > 1 or dy > 1:
            raise exceptions.Impossible("Too far away to place that.")

        check = getattr(self.item, "can_place_at", None)
        if check is not None:  # building pieces change the terrain and have their own rules
            reason = check(self.engine.game_map, self.dest_x, self.dest_y)
            if reason:
                raise exceptions.Impossible(reason)
        elif not self.engine.can_move(self.dest_x, self.dest_y):
            # Allow placing on own tile even if "blocked" by self
            if not (self.dest_x == self.entity.x and self.dest_y == self.entity.y):
                raise exceptions.Impossible("Can't place that there.")

        self.item.place_on_map(self.dest_x, self.dest_y, self.engine.game_map)
        self.engine.message_log.add_message(
            f"You build the {self.item.get_title()}." if check is not None else f"You place the {self.item.get_title()}.",
            color.menu_text,
        )
        self.engine.game_world.pass_time(unit=self.entity, time=1)