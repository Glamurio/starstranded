from __future__ import annotations

import math
import random

from typing import Dict, Iterable, Iterator, KeysView, List, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import pygame

import atlas as atlas_module
import blend
from atlas import TILE
from chunks import CHUNK_H, CHUNK_W, Chunk, ChunkKey, chebyshev, chunk_key, keys_around
from config import DEFAULT_CONFIG, GameConfig
from entity import EntityCategory, Item, SpatialContainer
from render_order import GROUND_LAYERS, LAYERS, MAX_GROUND_OBJECTS_PER_TILE, RenderOrder
import allegiance
import lighting
import tile_types
from simulation import PlantQueue
from view import Camera, Rect, ViewWindow

if TYPE_CHECKING:
    from engine import Engine
    from ui import Canvas
    from entity import Entity
    from components.unit import Unit
    from components.plant import Plant


def distance(p1, p2, diag=True, euclidean=False):
    if diag:
        return max(abs(p1.x - p2.x), abs(p1.y - p2.y))
    if euclidean:
        return math.sqrt(math.pow((p1.x - p2.x), 2) + math.pow((p1.y - p2.y), 2))
    
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)


# Terrain cells are grouped by one packed int64 key: sprite id + 1 (14 bits), flip (1), foreground rgb (24), background rgb (24).
BLEND_BORDERS = True      # ease ground colours across biome borders when drawing (blend.py)
SPRITE_BITS = 14
SPRITE_MASK = (1 << SPRITE_BITS) - 1
FLIP_SHIFT = SPRITE_BITS
FG_SHIFT = FLIP_SHIFT + 1
BG_SHIFT = FG_SHIFT + 24
assert atlas_module.COLUMNS * atlas_module.ROWS < SPRITE_MASK, "the sprite sheet outgrew the terrain render key; widen SPRITE_BITS"


class ChunkSource:
    """Where a World's chunks come from. `generate` makes the terrain; `populate` adds the generated entities."""

    bounds: Optional[Rect] = None
    """For bounded maps: the (x0, y0, width, height) of the map; None for an unbounded world."""

    def can_load(self, key: ChunkKey) -> bool:
        return True

    def mask(self, key: ChunkKey):
        """Which tiles of the chunk belong to the map (True, or a bool array for partial chunks)."""
        return True

    def generate(self, world: World, key: ChunkKey) -> Chunk:
        raise NotImplementedError

    def populate(self, world: World, chunk: Chunk) -> None:
        """Add the chunk's generated entities (called once, right after `generate`, with the chunk registered)."""


class FixedLandscape(ChunkSource):
    """A bounded map: one landscape array placed at world (0, 0); it must fit chunk (0, 0). Tests and the benchmark
    scenario use it; the rest of chunk (0, 0) is void (unwalkable, opaque, outside the map)."""

    def __init__(self, landscape: np.ndarray):
        width, height = landscape.shape
        assert width <= CHUNK_W and height <= CHUNK_H, f"a fixed landscape must fit one chunk, got {landscape.shape}"
        self.landscape = landscape
        self.bounds = (0, 0, width, height)
        self._mask = np.zeros((CHUNK_W, CHUNK_H), dtype=bool, order="F")
        self._mask[:width, :height] = True

    def can_load(self, key: ChunkKey) -> bool:
        return key == (0, 0)

    def mask(self, key: ChunkKey):
        return self._mask

    def generate(self, world: World, key: ChunkKey) -> Chunk:
        tiles = np.full((CHUNK_W, CHUNK_H), fill_value=tile_types.VOID, dtype=tile_types.tile_dt, order="F")
        width, height = self.landscape.shape
        tiles[:width, :height] = self.landscape
        return Chunk(key, tiles)


class _LoadedView:
    """Live, read-only collection over one per-chunk index of every loaded chunk (iteration snapshots each chunk)."""

    def __init__(self, world: World, getter):
        self._world = world
        self._getter = getter

    def __iter__(self) -> Iterator[Entity]:
        for chunk in list(self._world.chunks.values()):
            yield from list(self._getter(chunk))

    def __len__(self) -> int:
        return sum(len(self._getter(chunk)) for chunk in self._world.chunks.values())

    def __contains__(self, entity) -> bool:
        chunk = self._world.chunk_of(entity)
        return chunk is not None and entity in self._getter(chunk)

    def __bool__(self) -> bool:
        return any(self._getter(chunk) for chunk in self._world.chunks.values())


LOOK_DOWN = 3  # how many layers deep an open tile shows
NIGHT_TINT = (6, 8, 30, 255)
EXPLORED_DIM = 0.45
"""Brightness of remembered terrain (explored, not in sight) relative to its already dim `dark` look."""
NIGHT_ALPHA = 150  # opacity of the night shade at midnight (0-255)


class World(SpatialContainer):
    """One floor: the loaded chunks, the entities on them (world coordinates) and the view window.

    The World is the only place that adds, moves or removes map entities (`Entity.parent` is the World). It keeps
    `_by_pos` ((x, y) -> entities, insertion ordered) for every loaded entity and routes the per-chunk index
    (categories, actors, render layers, `blocked`) to the chunk under the entity. An entity that walks over a
    chunk border is re-indexed in the other chunk: the same object, nothing is copied.

    Chunks are loaded around the player (`update_tiers`); a chunk that is not loaded does not exist for queries
    (`in_bounds` is False there), so nothing can step into it. Unloaded chunks that were generated are kept as
    serialised bytes in `stored` (and written to disk by the save code).
    """

    def __init__(self, engine: Engine, source: ChunkSource, *, floor: int = 1, seed: int = 0, z: int = 0):
        self._soft_stamp, self._soft_result = None, None   # the last border-softened colours (see _soften_borders)
        self.engine = engine
        self.z = z  # the layer: 0 surface, < 0 caves, > 0 upper floors
        self.source = source
        self.floor = floor
        self.seed = seed
        self.bounds: Optional[Rect] = source.bounds
        self.chunks: Dict[ChunkKey, Chunk] = {}
        self.stored: Dict[ChunkKey, bytes] = {}
        self._terrain_cache: Dict[ChunkKey, tuple] = {}
        self.plant_queue = PlantQueue(self)
        self.entity_version = 0  # bumped whenever an entity is added or removed (cache key for derived lookups)
        self._by_pos: Dict[Tuple[int, int], List[Entity]] = {}
        self.window = ViewWindow(self)
        self.downstairs_location: Optional[Tuple[int, int]] = None
        self.has_sky = z >= 0  # open to the sun (and the dark): caves only have the night radius
        self.loads = 0
        self.unloads = 0

    def init_loaded(self, engine: Engine, source: ChunkSource, *, floor: int, seed: int, z: int = 0) -> None:
        """Initialise a World object created empty while loading a save (entities already point at it)."""
        World.__init__(self, engine, source, floor=floor, seed=seed, z=z)

    def find_uid(self, uid: int) -> Optional[Entity]:
        """The loaded entity with this uid (linear scan; only used for rare cross-chunk references in saves)."""
        for entity in self.entities:
            if entity.uid == uid:
                return entity
        return None

    @property
    def game_map(self) -> World:
        return self

    @property
    def config(self) -> GameConfig:
        return getattr(self.engine, "config", DEFAULT_CONFIG)

    # ── chunks ─────────────────────────────────────────────────────────────────────
    def chunk_of(self, entity: Entity) -> Optional[Chunk]:
        if entity.parent is not self:
            return None
        return self.chunks.get(chunk_key(entity.x, entity.y))

    def chunk_mask(self, key: ChunkKey):
        return self.source.mask(key)

    def center_key(self) -> ChunkKey:
        """The chunk the view window and the tiers are centred on: the player's, if the player is on this world."""
        player = getattr(self.engine, "player", None)
        if player is not None and player.parent is self:
            return chunk_key(player.x, player.y)
        return getattr(self, "_center", (0, 0))

    def load_chunk(self, key: ChunkKey) -> Optional[Chunk]:
        """Make chunk `key` resident: from the store if it was generated before, otherwise generate it."""
        chunk = self.chunks.get(key)
        if chunk is not None or not self.source.can_load(key):
            return chunk
        blob = self.stored.pop(key, None)
        if blob is not None:
            import savegame
            savegame.restore_chunk(self, blob)
            chunk = self.chunks[key]
        else:
            chunk = self.source.generate(self, key)
            self.chunks[key] = chunk
            self.source.populate(self, chunk)
        self.loads += 1
        return chunk

    def unload_chunk(self, key: ChunkKey) -> None:
        """Serialise chunk `key` into `stored` and drop it with all its entities (the player never is)."""
        chunk = self.chunks.get(key)
        if chunk is None:
            return
        player = getattr(self.engine, "player", None)
        assert player is None or player not in chunk.entities, "the player's chunk cannot be unloaded"
        import savegame
        self.stored[key] = savegame.serialize_chunk(self, chunk)
        for entity in list(chunk.entities):
            self._drop_position(entity)
            entity.parent = None
        del self.chunks[key]
        self.entity_version += 1
        self.unloads += 1

    def suspend(self) -> None:
        """Store every chunk (the player has left this layer): nothing here is simulated until it is entered again."""
        for key in list(self.chunks):
            self.unload_chunk(key)

    def terrain_tiles(self, key: ChunkKey) -> Optional[np.ndarray]:
        """The tiles of chunk `key` without loading it: from the resident chunk, from its stored bytes, or as the source
        generates them. Used to look down onto this layer from the one above (read-only)."""
        chunk = self.chunks.get(key)
        if chunk is not None:
            return chunk.tiles
        blob = self.stored.get(key)
        if blob is not None:
            cached = self._terrain_cache.get(key)
            if cached is None or cached[0] is not blob:
                import savegame
                cached = self._terrain_cache[key] = (blob, savegame.blob_tiles(blob))
            return cached[1]
        if not self.source.can_load(key) or not hasattr(self.source, "terrain"):
            return None
        return self.source.terrain(key)

    def terrain_region(self, field: str, rect: Rect) -> np.ndarray:
        """Like `region` for a tile field, but for chunks that are not loaded too (see `terrain_tiles`)."""
        x0, y0, width, height = rect
        fill = tile_types.SHROUD if field in ("light", "dark") else 0
        out = np.full((width, height), fill_value=fill, dtype=tile_types.tile_dt[field], order="F")
        for ky in range(y0 // CHUNK_H, (y0 + height - 1) // CHUNK_H + 1):
            for kx in range(x0 // CHUNK_W, (x0 + width - 1) // CHUNK_W + 1):
                tiles = self.terrain_tiles((kx, ky))
                if tiles is None:
                    continue
                cx0, cy0 = kx * CHUNK_W, ky * CHUNK_H
                ix0, iy0 = max(x0, cx0), max(y0, cy0)
                ix1, iy1 = min(x0 + width, cx0 + CHUNK_W), min(y0 + height, cy0 + CHUNK_H)
                out[ix0 - x0:ix1 - x0, iy0 - y0:iy1 - y0] = tiles[field][ix0 - cx0:ix1 - cx0, iy0 - cy0:iy1 - cy0]
        return out

    def update_tiers(self) -> None:
        """Load every chunk within `load_radius` (the simulated radius) of the centre; unload those beyond `unload_radius`."""
        config = self.config
        center = self.center_key()
        self._center = center
        for key in keys_around(center, config.load_radius):
            self.load_chunk(key)
        unload_radius = max(config.unload_radius, config.load_radius)
        for key in [k for k in self.chunks if chebyshev(k, center) > unload_radius]:
            self.unload_chunk(key)

    def chunks_in_rect(self, rect: Rect) -> List[Chunk]:
        x0, y0, width, height = rect
        found = []
        for ky in range(y0 // CHUNK_H, (y0 + height - 1) // CHUNK_H + 1):
            for kx in range(x0 // CHUNK_W, (x0 + width - 1) // CHUNK_W + 1):
                chunk = self.chunks.get((kx, ky))
                if chunk is not None:
                    found.append(chunk)
        return found

    # ── terrain ────────────────────────────────────────────────────────────────────
    def in_bounds(self, x: int, y: int) -> bool:
        """True if (x, y) is a tile of a loaded chunk (and inside the map, for bounded maps)."""
        if self.bounds is not None:
            bx, by, bw, bh = self.bounds
            if not (bx <= x < bx + bw and by <= y < by + bh):
                return False
        return chunk_key(x, y) in self.chunks

    def tile_at(self, x: int, y: int):
        """The tile record at (x, y) (a copy); None if the tile is not loaded."""
        if not self.in_bounds(x, y):
            return None
        chunk = self.chunks[chunk_key(x, y)]
        return chunk.tiles[x - chunk.x0, y - chunk.y0].copy()

    def is_walkable(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        chunk = self.chunks[chunk_key(x, y)]
        return bool(chunk.tiles["walkable"][x - chunk.x0, y - chunk.y0])

    def is_transparent(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        chunk = self.chunks[chunk_key(x, y)]
        return bool(chunk.tiles["transparent"][x - chunk.x0, y - chunk.y0])

    def is_explored(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        chunk = self.chunks[chunk_key(x, y)]
        return bool(chunk.explored[x - chunk.x0, y - chunk.y0])

    def is_visible(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.window.ensure().is_visible(x, y)

    def is_blocked(self, x: int, y: int) -> bool:
        """True if a movement-blocking entity stands on (x, y)."""
        chunk = self.chunks.get(chunk_key(x, y))
        return bool(chunk.blocked[x - chunk.x0, y - chunk.y0]) if chunk is not None else False

    def modify_tile(self, x: int, y: int, **fields) -> None:
        """Change fields of the tile at (x, y) (e.g. `walkable=False`, `dark=...`); invalidates the view window."""
        chunk = self.chunks[chunk_key(x, y)]
        record = chunk.tiles[x - chunk.x0, y - chunk.y0]
        for name, value in fields.items():
            record[name] = value
        chunk.tiles[x - chunk.x0, y - chunk.y0] = record
        chunk.terrain_version += 1

    def set_tile(self, x: int, y: int, tile: np.ndarray) -> None:
        chunk = self.chunks[chunk_key(x, y)]
        chunk.tiles[x - chunk.x0, y - chunk.y0] = tile
        chunk.terrain_version += 1

    def terrain_changed(self) -> None:
        """Call after mutating chunk terrain arrays directly (marks every loaded chunk changed)."""
        for chunk in self.chunks.values():
            chunk.terrain_version += 1

    def region(self, field: str, rect: Rect, fill=None) -> np.ndarray:
        """A world rectangle of one per-tile field, assembled from the loaded chunks.

        `field` is a tile field ("walkable", "transparent", "light", "dark") or "explored" / "blocked";
        tiles of chunks that are not loaded get `fill` (default: False / 0 / SHROUD).
        """
        x0, y0, width, height = rect
        if field in ("explored", "blocked"):
            dtype = bool if field == "explored" else np.int16
        else:
            dtype = tile_types.tile_dt[field]
        if fill is None:
            fill = tile_types.SHROUD if field in ("light", "dark") else 0
        out = np.full((width, height), fill_value=fill, dtype=dtype, order="F")
        for chunk in self.chunks_in_rect(rect):
            ix0, iy0 = max(x0, chunk.x0), max(y0, chunk.y0)
            ix1, iy1 = min(x0 + width, chunk.x0 + CHUNK_W), min(y0 + height, chunk.y0 + CHUNK_H)
            source = getattr(chunk, field) if field in ("explored", "blocked") else chunk.tiles[field]
            out[ix0 - x0:ix1 - x0, iy0 - y0:iy1 - y0] = source[ix0 - chunk.x0:ix1 - chunk.x0, iy0 - chunk.y0:iy1 - chunk.y0]
        return out

    def mark_explored(self) -> None:
        """`explored |= visible` for every loaded chunk in the view window."""
        window = self.window
        ox, oy = window.origin
        for chunk in self.chunks_in_rect(window.rect):
            sx = slice(chunk.x0 - ox, chunk.x0 - ox + CHUNK_W)
            sy = slice(chunk.y0 - oy, chunk.y0 - oy + CHUNK_H)
            chunk.explored |= window.visible[sx, sy]

    # ── collections (live, read-only views over the loaded chunks) ───────────────────
    @property
    def entities(self) -> _LoadedView:
        return _LoadedView(self, lambda chunk: chunk.entities)

    @property
    def units(self) -> _LoadedView:
        """All units on loaded chunks, living and dead."""
        return _LoadedView(self, lambda chunk: chunk.by_category[EntityCategory.UNIT])

    @property
    def plants(self) -> _LoadedView:
        return _LoadedView(self, lambda chunk: chunk.by_category[EntityCategory.PLANT])

    @property
    def items(self) -> _LoadedView:
        return _LoadedView(self, lambda chunk: chunk.by_category[EntityCategory.ITEM])

    @property
    def actors(self) -> _LoadedView:
        """Entities that currently have an AI."""
        return _LoadedView(self, lambda chunk: chunk.actors)

    def entities_in_render_order(self) -> Iterator[Entity]:
        chunks = list(self.chunks.values())
        for order in LAYERS:
            for chunk in chunks:
                yield from chunk.buckets[order]

    def stack_at(self, x: int, y: int) -> List[Entity]:
        """Entities on a tile, topmost layer first (the order you would see them in); newer arrivals first within a layer."""
        here = self._by_pos.get((x, y), ())
        return sorted(reversed(here), key=lambda entity: -entity.render_order.value)

    def hidden_ground_counts(self, rect: Optional[Rect] = None) -> Dict[Tuple[int, int], int]:
        """With the clutter safeguard on: `{(x, y): number of hidden ground objects}` for visible tiles piled too high
        (within `rect`, if given)."""
        if not self.config.clutter_safeguard:
            return {}
        chunks = self.chunks_in_rect(rect) if rect is not None else list(self.chunks.values())
        window = self.window.ensure()
        counts: Dict[Tuple[int, int], int] = {}
        for chunk in chunks:
            for order in GROUND_LAYERS:
                for entity in chunk.buckets[order]:
                    position = (entity.x, entity.y)
                    if rect is not None and not (rect[0] <= position[0] < rect[0] + rect[2] and rect[1] <= position[1] < rect[1] + rect[3]):
                        continue
                    if window.is_visible(*position):
                        counts[position] = counts.get(position, 0) + 1
        return {position: n - MAX_GROUND_OBJECTS_PER_TILE for position, n in counts.items() if n > MAX_GROUND_OBJECTS_PER_TILE}

    # ── mutation API ──────────────────────────────────────────────────────────────
    def add_entity(self, entity: Entity, x: int, y: int) -> None:
        """Put `entity` on this world at (x, y), detaching it from any previous container. The chunk must be loaded."""
        if entity.parent is self:
            self.move_entity(entity, x, y)
            return
        chunk = self.chunks.get(chunk_key(x, y))
        if chunk is None:
            raise ValueError(f"cannot place {entity!r} at {(x, y)}: chunk {chunk_key(x, y)} is not loaded")
        if entity.parent is not None:
            entity.parent.remove_entity(entity)
        entity.parent = self
        entity._x, entity._y = x, y
        self._by_pos.setdefault((x, y), []).append(entity)
        chunk.index(entity)
        self.entity_version += 1
        entity.on_added_to_map(self)
        if entity.category is EntityCategory.PLANT:
            self.plant_queue.track(entity, self._now())

    def _now(self) -> int:
        game_world = getattr(self.engine, "game_world", None)
        return getattr(game_world, "current_time", 0)

    def remove_entity(self, entity: Entity) -> None:
        """Take `entity` off this world (no-op if it is not here). Its `parent` becomes None."""
        chunk = self.chunk_of(entity)
        if chunk is None or entity not in chunk.entities:
            return
        chunk.unindex(entity)
        self._drop_position(entity)
        self.entity_version += 1
        entity.parent = None

    def _drop_position(self, entity: Entity) -> None:
        key = (entity.x, entity.y)
        bucket = self._by_pos[key]
        bucket.remove(entity)
        if not bucket:
            del self._by_pos[key]

    def move_entity(self, entity: Entity, x: int, y: int) -> None:
        old = (entity.x, entity.y)
        if old == (x, y):
            return
        old_chunk = self.chunks[chunk_key(*old)]
        new_key = chunk_key(x, y)
        if new_key == old_chunk.key:
            self._drop_position(entity)
            old_chunk.moved_within(entity, old, (x, y))
            entity._x, entity._y = x, y
            self._by_pos.setdefault((x, y), []).append(entity)
            return
        new_chunk = self.chunks.get(new_key)
        if new_chunk is None:
            raise ValueError(f"cannot move {entity!r} to {(x, y)}: chunk {new_key} is not loaded")
        # crossing a border: the same object moves from one chunk's index to the other's
        old_chunk.unindex(entity)
        self._drop_position(entity)
        entity._x, entity._y = x, y
        self._by_pos.setdefault((x, y), []).append(entity)
        new_chunk.index(entity)
        if entity is getattr(self.engine, "player", None):
            self.update_tiers()

    def _entity_changed(self, entity: Entity, attribute: str, old, new) -> None:
        chunk = self.chunk_of(entity)
        if chunk is not None:
            chunk.entity_changed(entity, attribute, old, new)

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
        """The unit at (x, y), preferring a living one over a corpse; None if there is no unit."""
        corpse = None
        for entity in self._by_pos.get((x, y), ()):
            if entity.category is EntityCategory.UNIT:
                if entity.is_alive:
                    return entity
                corpse = corpse or entity
        return corpse

    def entities_on_ring(self, x: int, y: int, radius: int) -> List[Entity]:
        """Entities at Chebyshev distance exactly `radius` from (x, y) (radius 0 = the tile itself)."""
        by_pos = self._by_pos
        if radius == 0:
            return list(by_pos.get((x, y), ()))
        found: List[Entity] = []
        for dx in range(-radius, radius + 1):
            found.extend(by_pos.get((x + dx, y - radius), ()))
            found.extend(by_pos.get((x + dx, y + radius), ()))
        for dy in range(-radius + 1, radius):
            found.extend(by_pos.get((x - radius, y + dy), ()))
            found.extend(by_pos.get((x + radius, y + dy), ()))
        return found

    # ── drawing ──────────────────────────────────────────────────────────────────
    def render(self, canvas: Canvas, camera: Optional[Camera] = None) -> None:
        """
        Draws the part of the world under `camera` (default: the engine's, following the player) into the viewport.

        If a tile is in the "visible" array, then draw it with the "light" graphics.
        If it isn't, but it's in the "explored" array, then draw it with the "dark" graphics.
        Otherwise nothing is drawn (the canvas is cleared to black beforehand).

        Terrain is drawn in one batched blit: tiles are grouped by their distinct graphic (sprite, flip, tint,
        background), each group is a cached surface from the sprite atlas, and `Surface.blits` draws them all.
        Entities then follow layer by layer (see `RenderOrder`) from the chunks under the camera, each tinted with its
        own shade and mirrored by its own flag. Piles of ground objects are capped by the clutter safeguard
        (`GameConfig.clutter_safeguard`): the bottom ones of an over-full tile are skipped and a stack marker is drawn.
        """
        if camera is None:
            camera = self.engine.camera
        atlas = canvas.sprites
        surface = canvas.surface
        rect = camera.rect
        window = self.window.ensure()
        visible = window.visible_region(rect)
        explored = self.region("explored", rect)
        shown = visible | explored
        xs, ys = np.nonzero(shown)
        if xs.size:
            light = self.region("light", rect)
            open_here = visible & self.region("open", rect)
            if open_here.any():
                self._look_down(light, open_here, rect)
            gfx = np.select(
                condlist=[visible, explored],
                choicelist=[light, self.region("dark", rect)],
                default=tile_types.SHROUD,
            )
            self._clear_dots_under_objects(gfx, rect)
            fg = gfx["fg"].astype(np.int64)
            bg = gfx["bg"].astype(np.int64)
            remembered = (~visible)[..., None]
            fg = np.where(remembered, (fg * EXPLORED_DIM).astype(np.int64), fg)       # (seen before but not in sight: well below anything in sight, even at night)
            bg = np.where(remembered, (bg * EXPLORED_DIM).astype(np.int64), bg)
            if BLEND_BORDERS:
                bg, fg = self._soften_borders(bg, fg, visible | explored, rect)
            keys = (
                (gfx["sprite"].astype(np.int64) + 1)
                | (gfx["flip"].astype(np.int64) << FLIP_SHIFT)
                | (((fg[..., 0] << 16) | (fg[..., 1] << 8) | fg[..., 2]) << FG_SHIFT)
                | (((bg[..., 0] << 16) | (bg[..., 1] << 8) | bg[..., 2]) << BG_SHIFT)
            )[xs, ys]
            unique, inverse = np.unique(keys, return_inverse=True)
            tiles = []
            for key in unique.tolist():
                fg_packed = (key >> FG_SHIFT) & 0xFFFFFF
                bg_packed = key >> BG_SHIFT
                tiles.append(atlas.get_on(
                    (key & SPRITE_MASK) - 1,
                    bool((key >> FLIP_SHIFT) & 1),
                    (fg_packed >> 16, (fg_packed >> 8) & 255, fg_packed & 255),
                    (bg_packed >> 16, (bg_packed >> 8) & 255, bg_packed & 255),
                ))
            surface.blits(
                [(tiles[i], (x * TILE, y * TILE)) for i, x, y in zip(inverse.reshape(-1).tolist(), xs.tolist(), ys.tolist())],
                doreturn=False,
            )

        get = atlas.get
        hidden = self.hidden_ground_counts(rect)
        skip = dict(hidden)  # how many of the lowest ground objects of a tile are still to be skipped
        x0, y0, width, height = rect
        chunks = self.chunks_in_rect(rect)
        entity_blits = []
        for order in LAYERS:
            ground = order in GROUND_LAYERS and bool(skip)
            for chunk in chunks:
                for entity in chunk.buckets[order]:
                    sx, sy = entity.x - x0, entity.y - y0
                    # Only draw entities in the viewport that are in the FOV
                    if not (0 <= sx < width and 0 <= sy < height) or not visible[sx, sy]:
                        continue
                    if ground and skip.get((entity.x, entity.y)):
                        skip[(entity.x, entity.y)] -= 1
                        continue
                    if getattr(entity, "decal", False):
                        picture = atlas.get_decal(entity.pattern, entity.variant, entity.shade)
                    elif getattr(entity, "skeleton", None):
                        import decay
                        picture = get(entity.sprite_id, False, decay.BONE_COLOR)
                    elif entity.is_corpse and entity.category is EntityCategory.UNIT:
                        picture = atlas.get_remains(entity.sprite_id, entity.mirrored and getattr(entity.kind, "mirror", False), entity.shade)
                    elif getattr(entity, "scenery", False):
                        picture = atlas.get_foliage(entity.sprite_id, entity.flipped, entity.shade, 0)
                    elif entity.category is EntityCategory.PLANT:
                        picture = atlas.get_foliage(entity.sprite_id, entity.flipped, entity.shade, entity.prominence)
                    elif getattr(entity, "rotation", 0):
                        picture = atlas.get_rotated(entity.sprite_id, getattr(entity, "pose_flip", False), entity.shade, entity.rotation)
                    else:
                        picture = get(entity.sprite_id, entity.flipped, entity.shade)
                    entity_blits.append((picture, (sx * TILE, sy * TILE)))
        surface.blits(entity_blits, doreturn=False)
        for x, y in hidden:
            canvas.badge(x - x0, y - y0)
        self._render_night(canvas, rect, visible, window.lit_region(rect))

    def _clear_dots_under_objects(self, gfx: np.ndarray, rect: Rect) -> None:
        """Where something stands on bare ground (the plain dotted floor), draw no dot under it: the object sits on blank ground."""
        x0, y0, width, height = rect
        dot = int(tile_types.floor.sprite)
        bare = gfx["sprite"] == dot
        if not bare.any():
            return
        occupied = np.zeros((width, height), dtype=bool)
        for chunk in self.chunks_in_rect(rect):
            for entity in chunk.entities:
                sx, sy = entity.x - x0, entity.y - y0
                if 0 <= sx < width and 0 <= sy < height and not getattr(entity, "decal", False):
                    occupied[sx, sy] = True
        gfx["sprite"][occupied & bare] = tile_types.NO_SPRITE

    def _soften_borders(self, bg: np.ndarray, fg: np.ndarray, shown: np.ndarray, rect: Rect) -> Tuple[np.ndarray, np.ndarray]:
        """Ease the ground colours across biome borders (see `blend.soften`). The ground tiles are the walkable dry ones, taken
        from a window a few tiles wider than the view, so the result does not change as the camera moves."""
        m = blend.RADIUS
        x0, y0, width, height = rect
        stamp = (rect, tuple((c.key, c.terrain_version) for c in self.chunks_in_rect(rect)), hash(shown.tobytes()), hash(bg.tobytes()))
        if self._soft_stamp == stamp:                    # nothing moved or changed since the last frame
            return self._soft_result
        wide = (x0 - m, y0 - m, width + 2 * m, height + 2 * m)
        ground = self.region("walkable", wide) & (self.region("liquid", wide) == 0) & ~self.region("built", wide)       # (paths, bridges and paving keep their own colour)
        light = self.region("light", wide)
        wide_bg, wide_fg = light["bg"].astype(np.int64), light["fg"].astype(np.int64)
        wide_bg[m:m + width, m:m + height] = bg
        wide_fg[m:m + width, m:m + height] = fg
        ground[m:m + width, m:m + height] &= shown
        new_bg, new_fg = blend.soften(wide_bg, wide_fg, ground)
        inside = (slice(m, m + width), slice(m, m + height))
        self._soft_stamp, self._soft_result = stamp, (new_bg[inside], new_fg[inside])
        return self._soft_result

    def _look_down(self, gfx: np.ndarray, mask: np.ndarray, rect: Rect) -> None:
        """Replace the graphics of the cells in `mask` (open tiles: no floor) by what lies below them: the next layer's terrain,
        drawn in its dim "explored" look, and further down where that is open too (up to `LOOK_DOWN` layers)."""
        game_world = getattr(self.engine, "game_world", None)
        if game_world is None:
            return
        for depth in range(1, LOOK_DOWN + 1):
            layer = game_world.world_at(self.z - depth)
            gfx[mask] = layer.terrain_region("dark", rect)[mask]
            mask = mask & layer.terrain_region("open", rect)
            if not mask.any():
                break

    def _render_night(self, canvas: Canvas, rect: Rect, visible: np.ndarray, lit: np.ndarray) -> None:
        """Dim what is seen but not lit by a light source, more the darker it is (nothing by day)."""
        dark = lighting.darkness(self, self.engine.game_world.current_time, self.config)
        if dark < 0.05:
            return
        alpha = np.where(visible & ~lit, int(NIGHT_ALPHA * dark), 0).astype(np.uint8)
        if not alpha.any():
            return
        width, height = alpha.shape
        cells = pygame.Surface((width, height), pygame.SRCALPHA, 32)
        cells.fill(NIGHT_TINT)
        pygame.surfarray.pixels_alpha(cells)[:] = alpha
        canvas.surface.blit(pygame.transform.scale(cells, (width * TILE, height * TILE)), (0, 0))


class GameMap(World):
    """A bounded world made from one fixed landscape at world (0, 0) (tests, the benchmark scenario).

    Besides the World API it exposes the old whole-map arrays as live views: `tiles`, `explored` (into chunk
    (0, 0)), `visible` (into the view window), `blocked`, and `width`/`height`. Accessing `tiles` marks the terrain
    changed, since callers use it to edit tiles.
    """

    def __init__(self, engine: Engine, landscape: np.ndarray, entities: Iterable[Entity] = ()):
        World.__init__(self, engine, FixedLandscape(landscape))
        self.width, self.height = landscape.shape
        self.downstairs_location = (0, 0)
        self._center = (0, 0)
        self.load_chunk((0, 0))
        for entity in entities:
            self.add_entity(entity, entity.x, entity.y)

    def init_loaded(self, engine: Engine, source: ChunkSource, *, floor: int, seed: int, z: int = 0) -> None:
        World.__init__(self, engine, source, floor=floor, seed=seed, z=z)
        self.width, self.height = source.landscape.shape
        self._center = (0, 0)

    @property
    def _chunk(self) -> Chunk:
        return self.chunks[(0, 0)]

    @property
    def tiles(self) -> np.ndarray:
        self._chunk.terrain_version += 1  # callers may write through this view
        return self._chunk.tiles[: self.width, : self.height]

    @property
    def explored(self) -> np.ndarray:
        return self._chunk.explored[: self.width, : self.height]

    @property
    def visible(self) -> np.ndarray:
        window = self.window.ensure()
        wx, wy = window.to_window(0, 0)
        return window.visible[wx: wx + self.width, wy: wy + self.height]

    @property
    def blocked(self) -> np.ndarray:
        return self._chunk.blocked[: self.width, : self.height]

    def update_tiers(self) -> None:
        """A bounded map has a single chunk: always loaded, always active."""


class GameWorld:
    """
    The layers and the clock: holds the game seed, the layer the player is on (`current_z`) and the time.

    Every layer (0 = surface, < 0 caves, > 0 upper floors, see `shafts`) is a `World` of its own, created on first use in
    `layers`. Only the player's layer is loaded and simulated; the others are stored chunk by chunk (`World.suspend`) and
    catch up when the player returns.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        seed: Optional[int] = None,
        current_z: int = 0,
        current_floor: Optional[int] = None,  # old spelling: the depth, 1 = surface
        current_time: int = 0,
        culture: str = "human",
        **_legacy,  # map_width/map_height/max_rooms/room_*: accepted for old callers, unused (worlds are unbounded)
    ):
        self.engine = engine
        self.seed = seed if seed is not None else random.getrandbits(62)  # from `random`: seeding it reproduces a game
        self.current_z = current_z if current_floor is None else 1 - current_floor
        self.current_time = current_time
        self.culture = culture  # naming culture of the planet's catalogue (the player's people)
        self.layers: Dict[int, World] = {}
        self.arrivals: List[tuple] = []  # (due time, unit, z, x, y): followers still on the stairs
        from run import RunState
        self.run = RunState(seed=self.seed)  # mode, reputation, contracts, discoveries, escape progress

    @property
    def planet(self):
        """The planet catalogue (species, materials, names) of this game; None for the old single-species test worlds."""
        source = self.world_at(0).source
        return getattr(source, "planet", None)

    @property
    def current_floor(self) -> int:
        """The depth: 1 on the surface, 2 one cave below it, 0 on the first upper floor."""
        return 1 - self.current_z

    def floor_seed(self, floor: int) -> int:
        from worldgen import mix_seed
        return mix_seed(self.seed, floor)

    @property
    def master_seed(self) -> int:
        """The seed every layer's generation derives from (it is the surface's own seed)."""
        return self.floor_seed(1)

    def make_world(self, z: int) -> World:
        from worldgen import CaveSource, NoiseWorldSource, SkySource
        if z == 0:
            source = NoiseWorldSource(self.master_seed, 1, culture=self.culture)
        elif z < 0:
            source = CaveSource(self.master_seed, z)
        else:
            source = SkySource(self.master_seed, z)
        return World(self.engine, source, floor=source.floor, seed=source.floor_seed, z=z)

    def world_at(self, z: int) -> World:
        """The World of layer `z`, created (empty, nothing loaded) if it was never visited."""
        world = self.layers.get(z)
        if world is None:
            world = self.layers[z] = self.make_world(z)
        return world

    def start(self) -> None:
        """Begin the game on the surface: load the start chunk and put the player on its spawn point."""
        self.current_z = 0
        world = self.world_at(0)
        world.load_chunk((0, 0))  # chunk (0, 0) holds the start and the cave entrance
        player = self.engine.player
        player.place(*world.source.spawn_point, world)
        self.engine.game_map = world
        world.update_tiers()
        self.engine.update_fov()

    def place_on_layer(self, unit: Unit, z: int, x: int, y: int) -> bool:
        """Put `unit` on the free tile nearest (x, y) of layer `z` (loading its chunk, and storing it again if the layer is not
        the current one). False if there is no room within 3 tiles."""
        from chunks import chunk_key
        world = self.world_at(z)
        for radius in range(4):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    tx, ty = x + dx, y + dy
                    key = chunk_key(tx, ty)
                    was_loaded = key in world.chunks
                    world.load_chunk(key)
                    tile = world.tile_at(tx, ty)
                    ok = (tile is not None and bool(tile["walkable"]) and not int(tile["liquid"])
                          and not world.get_entities_at_location(tx, ty, True))
                    if ok:
                        unit.place(tx, ty, world)
                        if not was_loaded and world is not self.engine.game_map:
                            world.unload_chunk(key)
                        return True
                    if not was_loaded and world is not self.engine.game_map:
                        world.unload_chunk(key)
        return False

    def send(self, unit: Unit, z: int, delay: int = 0) -> None:
        """A creature takes stairs to layer `z`: it leaves its layer now and arrives `delay` turns later at the same x/y."""
        x, y = unit.x, unit.y
        unit.game_map.remove_entity(unit)
        if unit.ai is not None:
            unit.ai.path = []
        if delay <= 0:
            self.place_on_layer(unit, z, x, y)
        else:
            self.arrivals.append((self.current_time + delay, unit, z, x, y))

    def release_arrivals(self, everyone: bool = False) -> None:
        """Place the followers whose time has come (all of them with `everyone`: the player moved on, or the game is saved)."""
        due = [a for a in self.arrivals if everyone or a[0] <= self.current_time]
        if not due:
            return
        self.arrivals = [a for a in self.arrivals if a not in due]
        for _, unit, z, x, y in due:
            self.place_on_layer(unit, z, x, y)

    def followers(self, world: World) -> list:
        """Living hostile creatures close enough to the player to follow him down (or up) a staircase."""
        import behavior
        import debug
        player = self.engine.player
        found = []
        if debug.is_god(self.engine):
            return found
        for chunk in list(world.chunks.values()):
            for entity in chunk.actors:
                if entity is player or entity.category is not EntityCategory.UNIT or not allegiance.threatens(entity, player):
                    continue
                gap = max(abs(entity.x - player.x), abs(entity.y - player.y))
                if gap <= behavior.FOLLOW_RANGE:
                    found.append((gap, entity))
        return found

    def change_layer(self, z: int, x: int, y: int) -> World:
        """Move the player to (x, y) of layer `z`; the layer left is stored away."""
        from chunks import chunk_key
        engine, player = self.engine, self.engine.player
        old = engine.game_map
        self.release_arrivals(everyone=True)
        old.remove_entity(player)
        old.suspend()
        old.window.visible[:] = False
        new = self.world_at(z)
        self.current_z = z
        new.load_chunk(chunk_key(x, y))
        player.place(x, y, new)
        engine.game_map = new
        new.update_tiers()
        self.drop_far_layers()
        engine.update_fov()
        return new

    def drop_far_layers(self) -> None:
        """Forget layers that were never changed (nothing stored) so the layer table stays small."""
        for z in [z for z, w in self.layers.items() if z != self.current_z and not w.stored and not w.chunks]:
            del self.layers[z]

    def tile_on_layer(self, z: int, x: int, y: int):
        """A copy of the tile record at (x, y) of layer `z` (loaded or not), or None."""
        from chunks import chunk_key
        tiles = self.world_at(z).terrain_tiles(chunk_key(x, y))
        if tiles is None:
            return None
        return tiles[x % CHUNK_W, y % CHUNK_H].copy()

    def edit_tile(self, z: int, x: int, y: int, tile) -> None:
        """Set the tile at (x, y) of layer `z`, loading its chunk if needed (and storing it again if the layer is not current)."""
        from chunks import chunk_key
        world = self.world_at(z)
        key = chunk_key(x, y)
        was_loaded = key in world.chunks
        world.load_chunk(key)
        world.set_tile(x, y, tile)
        if not was_loaded and world is not self.engine.game_map:
            world.unload_chunk(key)

    def take_stairs(self, direction: int) -> int:
        """Use the staircase under the player: `+1` up, `-1` down. Returns the new z; `Impossible` if there is none that way."""
        import exceptions
        from chunks import chunk_key
        engine, player = self.engine, self.engine.player
        world = engine.game_map
        tile = world.tile_at(player.x, player.y)
        stairs = int(tile["stairs"]) if tile is not None else 0
        if stairs == 0:
            raise exceptions.Impossible("There are no stairs here.")
        if direction and stairs != direction:
            raise exceptions.Impossible("These stairs only go " + ("up." if stairs > 0 else "down."))
        followers = self.followers(world)
        for _, creature in followers:  # they leave before the layer is stored
            world.remove_entity(creature)
            if creature.ai is not None:
                creature.ai.path = []
        self.change_layer(world.z + stairs, player.x, player.y)
        for gap, creature in followers:
            self.arrivals.append((self.current_time + gap, creature, self.current_z, player.x, player.y))
        return self.current_z

    def pass_time(self, unit: Unit, time: int) -> int:
        """Passes game time in minutes after every player turn and runs the tiered simulation. Returns the time."""

        if unit == self.engine.player:
            for _ in range(time):   # needs are paid minute by minute: a 5-minute job costs five minutes of hunger
                self.current_time += 1
                import debug
                if debug.is_god(self.engine):
                    continue   # God Mode: time passes, needs do not
                import simulation
                if not self.current_time % simulation.HUNGER_PERIOD:
                    unit.handle_hunger(-1)
                if not self.current_time % simulation.THIRST_PERIOD:
                    unit.handle_thirst(-1)
                if not self.current_time % simulation.HEAL_PERIOD and unit.poison <= 0:
                    unit.heal(1)
                unit.tick_poison(1)
                if self.planet is not None:  # the old single-species test worlds have no climate
                    import survival
                    survival.tick(self.engine, unit, 1)
                if not unit.is_alive:
                    break
            unit.last_upkeep = self.current_time

            self.release_arrivals()
            from simulation import run_turn
            run_turn(self.engine)
            import endings
            endings.tick(self.engine)
            self.engine.update_fov()

        return self.current_time
