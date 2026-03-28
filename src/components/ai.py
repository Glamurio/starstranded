from __future__ import annotations

import random
import color
from typing import List, Optional, Tuple, TYPE_CHECKING

from actions import Action, BumpAction, MeleeAction, MovementAction, WaitAction

if TYPE_CHECKING:
    from entity import Unit, Entity, Item
    from components.plant import Plant
    from components.consumable import FoodConsumable
    from components.inventory import Inventory

class BaseAI(Action):
    entity: Unit
    path: List[Tuple[int, int]] = []
    is_hostile: bool = False
    directions: List[Tuple[int, int]] = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]

    def perform(self) -> None:
        time = self.engine.game_world.current_time
        if time % 4 == 0:
            self.entity.handle_hunger(-1)
        if time % 2 == 0:
            self.entity.handle_thirst(-1)

    def get_path(self, dest_x: int, dest_y: int) -> List[Tuple[int, int]]:
        """Perform movement action"""
        return self.engine.get_path_to(self, dest_x, dest_y)

    def wander(self) -> None:
        """Choose a random tile to wander to if no relevant entities are within range."""
        dest_x, dest_y = self.get_random_tile(walkable=True)
        self.path = self.get_path(dest_x, dest_y)
        return MovementAction(self.entity, dest_x, dest_y, self.path).perform()

    def flee(self, entity: Entity, distance: int = 10) -> None:
        """Choose a random tile that's at least `distance` tiles away from `entity` and return its coordinates."""
        while True:
            dx = random.randint(0, self.engine.game_map.width - 1)
            dy = random.randint(0, self.engine.game_map.height - 1)
            if self.engine.game_map.tiles["walkable"][dx, dy] and self.engine.distance((dx, dy), (entity.x, entity.y)) >= distance:
                self.path = self.get_path(dx, dy)

                player = self.engine.player
                if self.engine.can_see(player.x, player.y, self.entity.x, self.entity.y, player.radius):
                    self.engine.message_log.add_message(
                        f"{self.entity.get_title()} is fleeing from {entity.get_title()}!"
                    )
                return MovementAction(self.entity, dx, dy, self.path).perform()

    def seek_food(self) -> None:
        """Attempt to find food, either in inventory or nearby."""
        if not self.entity.inventory.is_empty():
            for item in self.entity.inventory.items:
                if hasattr(item, "hunger_amount") or hasattr(item, "thirst_amount"):
                    self.entity.inventory.loot(item)
                    return self.eat_food(item)

        closest_plant: Plant = None
        closest_food: Item = None
        plants = list(self.engine.game_map.plants)
        items = list(self.engine.game_map.items)
        max_radius = self.entity.radius  # Maximum radius to search for plants within
        for radius in range(0, max_radius + 1):
            # Find the closest plant within the current radius
            for item in items:
                distance = self.engine.distance((self.entity.x, self.entity.y), (item.x, item.y))
                if not distance == radius:
                    continue
                if not hasattr(item, 'hunger_amount'):
                    continue

                closest_food = item
                break

            if closest_food:
                break

            for plant in plants:
                distance = self.engine.distance((self.entity.x, self.entity.y), (plant.x, plant.y))
                if not distance == radius:
                    continue
                if not plant.fruit:
                    continue
                if plant.inventory.is_empty():
                    continue

                closest_plant = plant
                break

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
        if not food and container:
            for item in container.items:
                if hasattr(item, "hunger_amount") or hasattr(item, "thirst_amount"):
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

    def get_random_tile(self, walkable: bool = False) -> Tuple[int, int]:
        """
        Choose a random tile within the map coordinates.
        
        Supply `walkable` to check if tile should be walkable.
        """
        tiles = self.engine.game_map.tiles["walkable"] if walkable else self.engine.game_map.tiles
        while True:
            x = random.randint(0, self.engine.game_map.width - 1)
            y = random.randint(0, self.engine.game_map.height - 1)
            if tiles[x, y]:
                return x, y

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

        if not self.seeking and self.entity.hunger <= 90 or self.entity.thirst <= 90:
            self.seeking = True
            return self.seek_food()

        if self.path:
            dest_x, dest_y = self.path[-1]
            return MovementAction(self.entity, dest_x, dest_y, self.path).perform()

        # Run away from the closest unit that's not own species
        for unit in self.engine.game_map.units:
            if unit.species == self.entity.species:
                continue
            
            if self.engine.distance((self.entity.x, self.entity.y), (unit.x, unit.y)) <= 3:
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

        if self.engine.game_map.visible[self.entity.x, self.entity.y]:
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