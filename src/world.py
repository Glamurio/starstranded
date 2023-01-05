from __future__ import annotations

import math
import random

from typing import Iterable, Iterator, Optional, TYPE_CHECKING

import numpy as np  # type: ignore
from tcod.console import Console

from entity import Item
import tile_types

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity
    from components.unit import Unit


def distance(p1, p2, diag=True, euclidean=False):
    if diag:
        return max(abs(p1.x - p2.x), abs(p1.y - p2.y))
    if euclidean:
        return math.sqrt(math.pow((p1.x - p2.x), 2) + math.pow((p1.y - p2.y), 2))
    
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)


class GameMap:
    def __init__(
        self, world: GameWorld, landscape: np.ndarray, engine: Engine, width: int, height: int, entities: Iterable[Entity] = ()
    ):  
        self.world = world
        self.engine = engine
        self.width, self.height = width, height
        self.entities = set(entities)
        self.tiles = landscape

        self.visible = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player can currently see
        self.explored = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player has seen before

        self.downstairs_location = (0, 0)

    @property
    def game_map(self) -> GameMap:
        return self

    @property
    def units(self) -> Iterator[Unit]:
        """Iterate over this maps living units."""
        yield from (
            entity
            for entity in self.entities
            if hasattr(entity, "is_alive")
        )

    @property
    def items(self) -> Iterator[Item]:
        yield from (entity for entity in self.entities if isinstance(entity, Item))

    def get_entity_at_location(
        self, location_x: int, location_y: int, check_block: bool = False
    ) -> Optional[Entity]:
        for entity in self.entities:
            checker = entity.blocks_movement if check_block else True
            if (
                checker
                and entity.x == location_x
                and entity.y == location_y
            ):
                return entity

        return None

    def get_unit_at_location(self, x: int, y: int) -> Optional[Unit]:
        for unit in self.units:
            if unit.x == x and unit.y == y:
                return unit

        return None

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height

    def render(self, console: Console) -> None:
        """
        Renders the map.

        If a tile is in the "visible" array, then draw it with the "light" colors.
        If it isn't, but it's in the "explored" array, then draw it with the "dark" colors.
        Otherwise, the default is "SHROUD".
        """
        console.rgb[0 : self.width, 0 : self.height] = np.select(
            condlist=[self.visible, self.explored],
            choicelist=[self.tiles["light"], self.tiles["dark"]],
            default=tile_types.SHROUD,
        )

        entities_sorted_for_rendering = sorted(
            self.entities, key=lambda x: x.render_order.value
        )

        for entity in entities_sorted_for_rendering:
            # Only print entities that are in the FOV
            if self.visible[entity.x, entity.y]:
                char = entity.char
                if isinstance(entity.char, int):
                    char = chr(entity.char)
                    if entity.mirrored:
                        char = chr(entity.char_right)
                console.print(
                    x=entity.x, y=entity.y, string=char, fg=entity.shade
                )

class GameWorld:
    """
    Holds the settings for the GameMap, and generates new maps when moving down the stairs.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        map_width: int,
        map_height: int,
        max_rooms: int,
        room_min_size: int,
        room_max_size: int,
        current_floor: int = 0,
        current_time: int = 0
    ):
        self.engine = engine

        self.map_width = map_width
        self.map_height = map_height

        self.max_rooms = max_rooms

        self.room_min_size = room_min_size
        self.room_max_size = room_max_size

        self.current_floor = current_floor
        self.current_time = current_time

        self.game_maps = []

    def generate_floor(self) -> None:
        from procgen import generate_noise

        self.current_floor += 1

        self.engine.game_map = generate_noise(
            map_width=self.map_width,
            map_height=self.map_height,
            engine=self.engine,
            world=self
        )

    def pass_time(self, unit: Unit, time: int) -> int:
        """Passes game time in minutes after every player turn. Returns current game time"""

        if unit.kind == "Player":
            self.current_time += time
            if self.current_time % 4 == 0:
                unit.handle_hunger(-1)
            if self.current_time % 2 == 0:
                unit.handle_thirst(-1)

            self.engine.handle_enemy_turns()
            self.engine.update_fov()
            
        return self.current_time