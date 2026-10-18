from __future__ import annotations

import random
import color
from typing import List, Optional, Tuple, TYPE_CHECKING

from actions import Action, BumpAction, MeleeAction, MovementAction, WaitAction
from entity import EntityCategory
import exceptions

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
        """Survival upkeep up to now (hunger every 4th turn, thirst every 2nd; catches up after an absence)."""
        from simulation import upkeep
        upkeep(self.entity, self.engine.game_world.current_time)

    def get_path(self, dest_x: int, dest_y: int) -> List[Tuple[int, int]]:
        """Perform movement action"""
        return self.engine.get_path_to(self.entity, dest_x, dest_y)

    def wander(self) -> None:
        """Choose a random tile to wander to if no relevant entities are within range."""
        if not self.path:  # keep walking to the chosen spot; only pick a new one when there is none
            dest_x, dest_y = self.get_random_tile(walkable=True)
            self.path = self.get_path(dest_x, dest_y)
        dest_x, dest_y = self.path[-1] if self.path else (self.entity.x, self.entity.y)
        try:
            return MovementAction(self.entity, dest_x, dest_y, self.path).perform()
        except exceptions.Impossible:
            self.path = []  # blocked or no path: choose again next turn
            raise

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

class CreatureAI(BaseAI):
    """Every living creature's brain: upkeep, then `behavior.act` (flee / hunt / feed / idle)."""

    def perform(self) -> None:
        super().perform()
        import behavior
        behavior.act(self.entity, self, cheap=False)


class PassiveAI(CreatureAI):
    """Not hostile to the player: it flees from what hunts it and otherwise minds its own needs."""


class HostileAI(CreatureAI):
    """Hostile to the player: chases and attacks them on sight; otherwise lives like any other creature."""
    is_hostile = True
