from __future__ import annotations

import random
import color
from typing import List, Optional, Tuple, TYPE_CHECKING

from actions import Action, BumpAction, MeleeAction, MovementAction, WaitAction
from entity import EntityCategory

if TYPE_CHECKING:
    from entity import Unit, Entity, Item
    from components.plant import Plant
    from components.consumable import FoodConsumable
    from components.inventory import Inventory

class BaseAI(Action):
    entity: Unit
    path: List[Tuple[int, int]]
    is_hostile: bool = False
    directions: List[Tuple[int, int]] = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]

    def __init__(self, entity: Unit) -> None:
        super().__init__(entity)
        self.path = []  # per-instance; a class-level list would be shared by every AI

    def perform(self) -> None:
        time = self.engine.game_world.current_time
        if time % 4 == 0:
            self.entity.handle_hunger(-1)
        if time % 2 == 0:
            self.entity.handle_thirst(-1)

    def get_path(self, dest_x: int, dest_y: int) -> List[Tuple[int, int]]:
        """Perform movement action"""
        return self.engine.get_path_to(self.entity, dest_x, dest_y)

    def wander(self) -> None:
        """Choose a random tile to wander to if no relevant entities are within range."""
        dest_x, dest_y = self.get_random_tile(walkable=True)
        self.path = self.get_path(dest_x, dest_y)
        return MovementAction(self.entity, dest_x, dest_y, self.path).perform()

    def flee(self, entity: Entity, distance: int = 10) -> None:
        """Move towards a random walkable tile at least `distance` tiles away from `entity`.

        Tries `config.flee_attempts` random tiles (the old loop could spin forever); if none qualifies, wanders.
        """
        world = self.engine.game_map
        reach = 2 * distance
        for _ in range(self.engine.config.flee_attempts):
            dx = self.entity.x + random.randint(-reach, reach)
            dy = self.entity.y + random.randint(-reach, reach)
            if world.is_walkable(dx, dy) and self.engine.distance((dx, dy), (entity.x, entity.y)) >= distance:
                self.path = self.get_path(dx, dy)

                player = self.engine.player
                if self.engine.can_see(player.x, player.y, self.entity.x, self.entity.y, player.radius):
                    self.engine.message_log.add_message(
                        f"{self.entity.get_title()} is fleeing from {entity.get_title()}!"
                    )
                return MovementAction(self.entity, dx, dy, self.path).perform()
        return self.wander()

    def seek_food(self) -> None:
        """Attempt to find food, either in inventory or nearby."""
        from components.consumable import FoodConsumable
        if not self.entity.inventory.is_empty():
            for item in self.entity.inventory.items:
                if isinstance(item, FoodConsumable):
                    self.entity.inventory.loot(item)
                    return self.eat_food(item)

        closest_plant: Plant = None
        closest_food: Item = None
        game_map = self.engine.game_map
        max_radius = self.entity.radius  # Maximum radius to search for plants within
        # Scan Chebyshev rings outwards through the spatial index. At each radius food items on the ground win
        # over fruiting plants, as before; ties within a ring are resolved in ring order.
        for radius in range(0, max_radius + 1):
            ring = game_map.entities_on_ring(self.entity.x, self.entity.y, radius)
            closest_food = next((e for e in ring if isinstance(e, FoodConsumable)), None)
            if closest_food:
                break
            closest_plant = next(
                (e for e in ring if e.category is EntityCategory.PLANT and e.fruit and not e.inventory.is_empty()),
                None,
            )
            if closest_plant:
                break
        
        if closest_food and self.engine.distance((self.entity.x, self.entity.y), (closest_food.x, closest_food.y)) <= 1:
            return self.forage_food(closest_food)

        if closest_plant and self.engine.distance((self.entity.x, self.entity.y), (closest_plant.x, closest_plant.y)) <= 1:
            return self.forage_food(container=closest_plant.inventory)
            
        if not closest_plant or not closest_food:
            return self.wander()

        adjacent_tiles = self.engine.get_adjacent_tiles(closest_plant.x, closest_plant.y)
        tile = self.engine.get_closest_tile(adjacent_tiles, self.entity.x, self.entity.y)
        self.path = self.get_path(tile[0], tile[1])
        return MovementAction(self.entity, tile[0], tile[1], self.path).perform()

    def forage_food(self, food: FoodConsumable = None, container: Inventory = None):
        from components.consumable import FoodConsumable
        if not food and container:
            for item in container.items:
                if isinstance(item, FoodConsumable):
                    food = item
                    break

        if not food:
            return self.wander()

        self.entity.inventory.loot(food)

        player = self.engine.player
        if self.engine.can_see(player.x, player.y, self.entity.x, self.entity.y, player.radius):
            self.engine.message_log.add_message(
                f"{self.entity.get_title()} begins eating the {food.get_title()}."
            )
        return WaitAction(self.entity).perform()

    def eat_food(self, item: FoodConsumable):
        item.consume(self.entity)
        player = self.engine.player
        if self.engine.can_see(player.x, player.y, self.entity.x, self.entity.y, player.radius):
            self.engine.message_log.add_message(
                f"{self.entity.get_title()} has eaten the {item.get_title()}."
            )
        return WaitAction(self.entity).perform()

    WANDER_RADIUS = 12

    def get_random_tile(self, walkable: bool = False) -> Tuple[int, int]:
        """
        Choose a random loaded tile within `WANDER_RADIUS` of the entity (the world has no edges to pick between).

        Supply `walkable` to check if tile should be walkable. Gives up after `config.flee_attempts` tries and
        returns the entity's own position (the old loop over the whole map could spin forever).
        """
        world = self.engine.game_map
        r = self.WANDER_RADIUS
        for _ in range(self.engine.config.flee_attempts):
            x = self.entity.x + random.randint(-r, r)
            y = self.entity.y + random.randint(-r, r)
            if world.is_walkable(x, y) if walkable else world.in_bounds(x, y):
                return x, y
        return self.entity.x, self.entity.y

class ConfusedEnemy(BaseAI):
    """
    A confused enemy will stumble around aimlessly for a given number of turns, then revert back to its previous AI.
    If a unit occupies a tile it is randomly moving into, it will attack.
    """

    def __init__(
        self, entity: Unit, previous_ai: Optional[BaseAI], turns_remaining: int
    ):
        super().__init__(entity)

        self.previous_ai = previous_ai
        self.turns_remaining = turns_remaining

    def perform(self) -> None:
        super().perform()

        # Revert the AI back to the original state if the effect has run its course.
        if self.turns_remaining <= 0:
            self.engine.message_log.add_message(
                f"{self.entity.get_title()} is no longer confused."
            )
            self.entity.ai = self.previous_ai
        else:
            # Pick a random direction
            direction_x, direction_y = random.choice(self.directions)
            self.turns_remaining -= 1

            # The unit will either try to move or attack in the chosen random direction.
            # Its possible the unit will just bump into the wall, wasting a turn.
            return BumpAction(self.entity, direction_x, direction_y,).perform()


class PassiveAI(BaseAI):
    def __init__(self, entity: Unit):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []
        self.seeking: bool = False

    def perform(self) -> None:
        super().perform()

        if self.entity.hunger <= 90 or self.entity.thirst <= 90:
            self.seeking = True
            return self.seek_food()

        self.seeking = False  # reset when no longer hungry/thirsty

        if self.path:
            dest_x, dest_y = self.path[-1]
            return MovementAction(self.entity, dest_x, dest_y, self.path).perform()

        # Run away from the closest unit (within 3 tiles) that's not own species
        world = self.engine.game_map
        for radius in range(1, 4):
            for unit in world.entities_on_ring(self.entity.x, self.entity.y, radius):
                if unit.category is not EntityCategory.UNIT:
                    continue
                if unit.species == self.entity.species or not unit.is_alive:  # corpses are not a threat
                    continue
                return self.flee(unit, self.entity.radius)

        action = WaitAction(self.entity).perform() if bool(random.getrandbits(1)) else self.wander()
        return action

class HostileAI(BaseAI):
    def __init__(self, entity: Unit):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []
        self.is_hostile = True

    def perform(self) -> None:
        super().perform()

        target = self.engine.player

        # Use relative offset only for distance check
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        distance = max(abs(dx), abs(dy))  # Chebyshev distance

        if self.engine.game_map.is_visible(self.entity.x, self.entity.y):
            if distance <= 1:
                # Attack at the player's ABSOLUTE position
                return MeleeAction(self.entity, target.x, target.y).perform()

            # Path toward the player's ABSOLUTE position
            self.path = self.get_path(target.x, target.y)

        if self.path:
            # Let MovementAction pop the next step from the path
            dest_x, dest_y = self.path[0]
            return MovementAction(self.entity, dest_x, dest_y, self.path).perform()

        return WaitAction(self.entity).perform()

class PlantAI(BaseAI):
    def __init__(self, entity: Unit):
        super().__init__(entity)
        self.entity: Plant

    def perform(self) -> None:
        time = self.engine.game_world.current_time
        if time % 2 == 0:
            self.entity.handle_growth()