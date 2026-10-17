from __future__ import annotations

import math
import random

from typing import Dict, Iterable, Iterator, KeysView, List, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import tcod

from entity import EntityCategory, Item, SpatialContainer
from render_order import RenderOrder
import tile_types

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity
    from components.unit import Unit
    from components.plant import Plant


def distance(p1, p2, diag=True, euclidean=False):
    if diag:
        return max(abs(p1.x - p2.x), abs(p1.y - p2.y))
    if euclidean:
        return math.sqrt(math.pow((p1.x - p2.x), 2) + math.pow((p1.y - p2.y), 2))
    
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)


class GameMap(SpatialContainer):
    """One map: terrain arrays plus the entities on it.

    The map is the only place that adds, moves or removes entities, and it keeps these indexes in sync:
    `_by_pos` ((x, y) -> entities, insertion ordered), per-category collections (`units`, `plants`, `items`),
    `actors` (entities with an AI), render buckets per `RenderOrder`, and `blocked` (count of movement-blocking
    entities per tile). Iteration order is insertion order, so it is deterministic.
    """

    def __init__(self, engine: Engine, landscape: np.ndarray, entities: Iterable[Entity] = ()):
        self.engine = engine
        self.tiles = landscape
        self.width, self.height = landscape.shape

        self.visible = np.full(
            (self.width, self.height), fill_value=False, order="F"
        )  # Tiles the player can currently see
        self.explored = np.full(
            (self.width, self.height), fill_value=False, order="F"
        )  # Tiles the player has seen before

        self.downstairs_location = (0, 0)

        self._entities: Dict[Entity, None] = {}
        self._by_pos: Dict[Tuple[int, int], List[Entity]] = {}
        self._by_category: Dict[EntityCategory, Dict[Entity, None]] = {c: {} for c in EntityCategory}
        self._actors: Dict[Entity, None] = {}
        self._buckets: Dict[RenderOrder, Dict[Entity, None]] = {r: {} for r in RenderOrder}
        self.blocked = np.zeros((self.width, self.height), dtype=np.int16, order="F")

        for entity in entities:
            self.add_entity(entity, entity.x, entity.y)

    @property
    def game_map(self) -> GameMap:
        return self

    # ── collections (live, read-only views) ───────────────────────────────────────────
    @property
    def entities(self) -> KeysView[Entity]:
        return self._entities.keys()

    @property
    def units(self) -> KeysView[Unit]:
        """All units on this map, living and dead."""
        return self._by_category[EntityCategory.UNIT].keys()

    @property
    def plants(self) -> KeysView[Plant]:
        return self._by_category[EntityCategory.PLANT].keys()

    @property
    def items(self) -> KeysView[Item]:
        return self._by_category[EntityCategory.ITEM].keys()

    @property
    def actors(self) -> KeysView[Entity]:
        """Entities that currently have an AI."""
        return self._actors.keys()

    def entities_in_render_order(self) -> Iterator[Entity]:
        for order in RenderOrder:
            yield from self._buckets[order]

    # ── mutation API ──────────────────────────────────────────────────────────────
    def add_entity(self, entity: Entity, x: int, y: int) -> None:
        """Put `entity` on this map at (x, y), detaching it from any previous container."""
        if entity.parent is self:
            self.move_entity(entity, x, y)
            return
        if entity.parent is not None:
            entity.parent.remove_entity(entity)
        entity.parent = self
        entity._x, entity._y = x, y
        self._entities[entity] = None
        self._by_pos.setdefault((x, y), []).append(entity)
        self._by_category[entity.category][entity] = None
        self._buckets[entity.render_order][entity] = None
        if entity.ai:
            self._actors[entity] = None
        if entity.blocks_movement and self.in_bounds(x, y):
            self.blocked[x, y] += 1
        entity.on_added_to_map(self)

    def remove_entity(self, entity: Entity) -> None:
        """Take `entity` off this map (no-op if it is not here). Its `parent` becomes None."""
        if entity not in self._entities:
            return
        del self._entities[entity]
        self._unindex_position(entity)
        self._by_category[entity.category].pop(entity, None)
        self._buckets[entity.render_order].pop(entity, None)
        self._actors.pop(entity, None)
        if entity.blocks_movement and self.in_bounds(entity.x, entity.y):
            self.blocked[entity.x, entity.y] -= 1
        entity.parent = None

    def move_entity(self, entity: Entity, x: int, y: int) -> None:
        old = (entity.x, entity.y)
        if old == (x, y):
            return
        self._unindex_position(entity)
        if entity.blocks_movement:
            if self.in_bounds(*old):
                self.blocked[old] -= 1
            if self.in_bounds(x, y):
                self.blocked[x, y] += 1
        entity._x, entity._y = x, y
        self._by_pos.setdefault((x, y), []).append(entity)

    def _unindex_position(self, entity: Entity) -> None:
        key = (entity.x, entity.y)
        bucket = self._by_pos[key]
        bucket.remove(entity)
        if not bucket:
            del self._by_pos[key]

    def _entity_changed(self, entity: Entity, attribute: str, old, new) -> None:
        if attribute == "render_order":
            self._buckets[old].pop(entity, None)
            self._buckets[new][entity] = None
        elif attribute == "blocks_movement":
            if self.in_bounds(entity.x, entity.y):
                self.blocked[entity.x, entity.y] += 1 if new else -1
        elif attribute == "ai":
            if new:
                self._actors[entity] = None
            else:
                self._actors.pop(entity, None)

    # ── queries ──────────────────────────────────────────────────────────────────
    def get_entities_at_location(
        self, location_x: int, location_y: int, check_block: bool = False
    ) -> List[Entity]:
        """Return every entity at the location (only blocking ones if `check_block`). Never None."""
        here = self._by_pos.get((location_x, location_y), ())
        if check_block:
            return [entity for entity in here if entity.blocks_movement]
        return list(here)

    def get_unit_at_location(self, x: int, y: int) -> Optional[Unit]:
        for entity in self._by_pos.get((x, y), ()):
            if entity.category is EntityCategory.UNIT:
                return entity
        return None

    def is_blocked(self, x: int, y: int) -> bool:
        """True if a movement-blocking entity stands on (x, y)."""
        return bool(self.blocked[x, y]) if self.in_bounds(x, y) else False

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height

    def render(self, console: tcod.console.Console) -> None:
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

        visible = self.visible
        for entity in self.entities_in_render_order():
            # Only print entities that are in the FOV
            if visible[entity.x, entity.y]:
                char = entity.char
                if isinstance(entity.char, int):
                    char = chr(entity.char)
                    if entity.mirrored:
                        char = chr(entity.char_right)
                console.print(
                    x=entity.x, y=entity.y, text=char, fg=entity.shade
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

        if unit == self.engine.player:
            self.current_time += time
            if not self.current_time % 4:
                unit.handle_hunger(-1)
            if not self.current_time % 2:
                unit.handle_thirst(-1)

            self.engine.handle_enemy_turns()
            self.engine.update_fov()
            
        return self.current_time