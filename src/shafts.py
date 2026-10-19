"""The vertical structure of the world: which chunks have stairs, caves and buildings, and the terrain of every layer.

Layers are keyed by `z`: 0 is the surface, `z < 0` caves under it, `z > 0` the upper floors of buildings. Everything here
is a pure function of `(master_seed, z, chunk_key)` (results are cached, never stored), so any layer can be generated on its
own, in any order, and a layer that was dropped from memory is regenerated identically.

A `Link(x, y, z)` is one staircase between layer `z` (where it goes *up*) and layer `z + 1` (where it goes *down*) at the same
(x, y). `structure(master, key)` lists the links of a chunk; `layer_links(...)` picks the ones a layer needs. A chunk holds at
most one structure:

- a **cave shaft** from the surface down 1-3 layers: the entrance is a walkable surface tile; below it the staircases of one
  shaft are `STAIR_SPACING` tiles apart, so a layer can have both a way up and a way down; the caves around them are carved
  open (a 3x3 room and a corridor to the chunk centre) so a staircase is never walled in;
- a **building** of 1-3 floors above the ground: a walled rectangle with a door, a staircase inside per floor; the upper floors
  are walled rooms surrounded by open air (`tile_types.open_air`: you look down through it).

The chunk (0, 0) always has a cave entrance 8-20 tiles from the spawn point, and never a building.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np  # type: ignore
import tcod

import tile_types
from chunks import CHUNK_H, CHUNK_W, ChunkKey, chunk_origin

STAIR_SPACING = 4
EDGE = 6
"""Structures keep this many tiles away from the chunk border (a shaft and its carved rooms stay inside the chunk)."""

BUILDING_CHANCE = 0.2
SHAFT_CHANCE = 0.3
CAVE_THRESHOLD = -0.05
"""Cave noise above this is open floor (about half of the area)."""

_CACHE = 24


@dataclass(frozen=True)
class Link:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class Building:
    x: int
    y: int
    w: int
    h: int
    floors: int  # floors above the ground floor

    @property
    def door(self) -> Tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h - 1


@dataclass(frozen=True)
class Structure:
    links: Tuple[Link, ...] = ()
    building: Optional[Building] = None


def _mix(*values: int) -> int:
    from worldgen import mix_seed
    return mix_seed(*values)


# ── the surface ──────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=_CACHE)
def terrain_noise(master: int):
    from worldgen import TerrainNoise
    return TerrainNoise(master)


@lru_cache(maxsize=_CACHE)
def raw_surface(master: int, key: ChunkKey) -> Tuple[np.ndarray, np.ndarray]:
    """The natural surface terrain of a chunk: `(tiles, tree_map)` (read-only; no structures yet)."""
    from worldgen import generate_terrain, seeded_rng
    x0, y0 = chunk_origin(key)
    with seeded_rng(_mix(master, key[0], key[1])):
        tiles, tree_map = generate_terrain(terrain_noise(master), x0, y0, CHUNK_W, CHUNK_H)
    tiles.setflags(write=False)
    tree_map.setflags(write=False)
    return tiles, tree_map


@lru_cache(maxsize=_CACHE * 2)
def environment(master: int, key: ChunkKey) -> dict:
    """Environment arrays (temperature, moisture, elevation, fertility, light, water, biome) of a surface chunk (read-only)."""
    from worldgen import chunk_environment
    x0, y0 = chunk_origin(key)
    env = chunk_environment(terrain_noise(master), x0, y0)
    for array in env.values():
        array.setflags(write=False)
    return env


@lru_cache(maxsize=_CACHE)
def start_point(master: int) -> Tuple[Tuple[int, int], bool]:
    """The spawn point (the free tile closest to the centre of chunk (0, 0)) and whether the centre had to be carved open."""
    tiles, tree_map = raw_surface(master, (0, 0))
    free = tiles["walkable"] & ~tree_map & (tiles["liquid"] == 0)
    carved = not free.any()
    if carved:
        free = np.zeros_like(free)
        free[CHUNK_W // 2, CHUNK_H // 2] = True
    xs, ys = np.nonzero(free)
    d = np.maximum(np.abs(xs - CHUNK_W // 2), np.abs(ys - CHUNK_H // 2))
    i = int(np.lexsort((ys, xs, d))[0])
    return (int(xs[i]), int(ys[i])), carved


MOUNTAIN_CAVE_BONUS = 0.10
"""Extra chance (on top of SHAFT_CHANCE) that a chunk of mountain country has a cave."""
MOUNTAIN_ROCK = 0.12
"""Share of a chunk that is rock for it to count as mountain country."""


def _rock_edge(master: int, key: ChunkKey) -> Optional[np.ndarray]:
    """Walkable ground next to the rock face, for a mountain chunk (rock covers `MOUNTAIN_ROCK` of it); else None."""
    from procgen import dilate
    tiles, _ = raw_surface(master, key)
    rock = ~tiles["walkable"] & (tiles["liquid"] == 0) & ~tiles["transparent"]
    if rock.mean() < MOUNTAIN_ROCK:
        return None
    return dilate(rock) & ~rock


def _open_floor(master: int, key: ChunkKey) -> np.ndarray:
    """Surface tiles of a chunk that are walkable and free of trees (after the spawn carve)."""
    tiles, tree_map = raw_surface(master, key)
    free = tiles["walkable"] & ~tree_map & (tiles["liquid"] == 0) & ~tile_types.is_laid(tiles)
    if key == (0, 0):
        (sx, sy), carved = start_point(master)
        if carved:
            free = free.copy()
            free[sx, sy] = True
    return free


@lru_cache(maxsize=_CACHE * 4)
def structure(master: int, key: ChunkKey) -> Structure:
    """What the chunk has above and below its surface (see the module docstring)."""
    rng = random.Random(_mix(master, key[0], key[1], 7))
    roll = rng.random()
    if key != (0, 0) and roll < BUILDING_CHANCE:
        raw = raw_surface(master, key)[0]
        liquid = (raw["liquid"] != 0) | raw["open"]     # no building in a lake or over a chasm
        for _ in range(8):  # a site without liquid (no building in a lake)
            w, h = rng.randint(9, 15), rng.randint(7, 11)
            building = Building(
                x=rng.randint(4, CHUNK_W - 4 - w), y=rng.randint(4, CHUNK_H - 5 - h), w=w, h=h, floors=rng.randint(1, 3)
            )
            if not liquid[building.x - 1:building.x + w + 1, building.y - 1:building.y + h + 2].any():
                x0, y0 = chunk_origin(key)
                links = tuple(Link(x0 + building.x + 2 + 2 * i, y0 + building.y + 2, i) for i in range(building.floors))
                return Structure(links, building)
        return Structure()
    rocky = None
    if key != (0, 0) and roll >= BUILDING_CHANCE + SHAFT_CHANCE:
        if roll >= BUILDING_CHANCE + SHAFT_CHANCE + MOUNTAIN_CAVE_BONUS:
            return Structure()
        rocky = _rock_edge(master, key)          # a second chance, but only in mountain country
        if rocky is None:
            return Structure()
    free = _open_floor(master, key)
    window = np.zeros_like(free)
    depth = rng.randint(1, 3) if key != (0, 0) else 2
    window[EDGE:CHUNK_W - EDGE - STAIR_SPACING * (depth - 1), EDGE:CHUNK_H - EDGE] = True
    candidates = free & window
    if key != (0, 0):
        rocky = rocky if rocky is not None else _rock_edge(master, key)
        if rocky is not None and (candidates & rocky).any():
            candidates = candidates & rocky      # mountain caves open at the foot of the rock face
    if key == (0, 0):
        (sx, sy), _ = start_point(master)
        xs, ys = np.nonzero(candidates)
        ring = np.maximum(np.abs(xs - sx), np.abs(ys - sy))
        near = np.nonzero((ring >= 8) & (ring <= 20))[0]
        pool = near if near.size else np.nonzero(ring >= 1)[0]
        points = [(int(xs[i]), int(ys[i])) for i in pool]
    else:
        points = [(int(x), int(y)) for x, y in zip(*np.nonzero(candidates))]
    if not points:
        return Structure()
    px, py = points[rng.randrange(len(points))]
    x0, y0 = chunk_origin(key)
    return Structure(tuple(Link(x0 + px + STAIR_SPACING * i, y0 + py, -1 - i) for i in range(depth)))


def layer_stairs(links, z: int):
    """`(ups, downs)`: the staircases (x, y) that layer `z` has going up and going down."""
    ups = [(link.x, link.y) for link in links if link.z == z]
    downs = [(link.x, link.y) for link in links if link.z == z - 1]
    return ups, downs


def entrance_of(master: int) -> Optional[Tuple[int, int]]:
    """The cave entrance of the start chunk (the staircase down on the surface), or None."""
    links = structure(master, (0, 0)).links
    return (links[0].x, links[0].y) if links else None


# ── terrain of the layers ────────────────────────────────────────────────────────────
def surface_layer(master: int, key: ChunkKey) -> Tuple[np.ndarray, np.ndarray]:
    """Final surface tiles and tree map of a chunk (copies): natural terrain plus its building or cave entrance."""
    raw_tiles, raw_trees = raw_surface(master, key)
    tiles, tree_map = raw_tiles.copy(), raw_trees.copy()
    if key == (0, 0):
        (sx, sy), carved = start_point(master)
        if carved:
            tiles[sx, sy] = tile_types.floor.get_array()
    import routes
    routes.paint(master, key, tiles, tree_map)            # paths between the sites (before the buildings, which cover them)
    found = structure(master, key)
    x0, y0 = chunk_origin(key)
    if found.building is not None:
        _build(tiles, found.building, 0, x0, y0)
        b = found.building
        tree_map[b.x:b.x + b.w, b.y:b.y + b.h + 1] = False
    ups, downs = layer_stairs(found.links, 0)
    for x, y in ups:
        tiles[x - x0, y - y0] = tile_types.up_stairs.get_array()
    for x, y in downs:
        tiles[x - x0, y - y0] = tile_types.down_stairs.get_array()
        tree_map[x - x0, y - y0] = False
    return tiles, tree_map


def _build(tiles: np.ndarray, b: Building, z: int, x0: int, y0: int) -> None:
    """Draw the building's walls and floor for layer `z` (0 = ground floor) into a chunk's tiles (chunk-local coordinates)."""
    bx, by = b.x, b.y
    tiles[bx:bx + b.w, by:by + b.h] = tile_types.wall.get_array()
    inner = tile_types.floor if z == 0 else tile_types.built_floor
    tiles[bx + 1:bx + b.w - 1, by + 1:by + b.h - 1] = inner.get_array()
    if z == 0:
        dx, dy = b.door
        tiles[dx, dy] = tile_types.floor.get_array()
        tiles[dx, dy + 1] = tile_types.floor.get_array()


@lru_cache(maxsize=_CACHE * 2)
def sky_layer(master: int, z: int, key: ChunkKey) -> np.ndarray:
    """Tiles of an upper layer (z > 0): open air, with the room of a building where it has this floor (read-only)."""
    tiles = np.full((CHUNK_W, CHUNK_H), fill_value=tile_types.open_air.get_array(), dtype=tile_types.tile_dt, order="F")
    found = structure(master, key)
    x0, y0 = chunk_origin(key)
    if found.building is not None and z <= found.building.floors:
        _build(tiles, found.building, z, x0, y0)
        ups, downs = layer_stairs(found.links, z)
        for x, y in ups:
            tiles[x - x0, y - y0] = tile_types.up_stairs.get_array()
        for x, y in downs:
            tiles[x - x0, y - y0] = tile_types.down_stairs.get_array()
    tiles.setflags(write=False)
    return tiles


@lru_cache(maxsize=_CACHE)
def cave_noise(master: int, z: int):
    from worldgen import mix_seed
    return [tcod.noise.Noise(dimensions=2, algorithm=tcod.noise.Algorithm.PERLIN, seed=mix_seed(master, z, 99, i) % 2**31)
            for i in range(2)]


def _carve(kinds: np.ndarray, points, x0: int, y0: int, margin: int) -> None:
    """Open a 3x3 room at each stair and an L-shaped corridor to the chunk centre (coordinates of the padded kinds array)."""
    cx, cy = CHUNK_W // 2 + margin, CHUNK_H // 2 + margin
    kinds[cx - 1:cx + 2, cy - 1:cy + 2] = 1
    for x, y in points:
        lx, ly = x - x0 + margin, y - y0 + margin
        kinds[lx - 1:lx + 2, ly - 1:ly + 2] = 1
        kinds[min(lx, cx):max(lx, cx) + 1, ly] = 1
        kinds[cx, min(ly, cy):max(ly, cy) + 1] = 1


@lru_cache(maxsize=_CACHE * 2)
def cave_layer(master: int, z: int, key: ChunkKey) -> np.ndarray:
    """Tiles of a cave layer (z < 0) (read-only): noise caves, with the stairs of this chunk's shaft carved in."""
    from procgen import replace_variations
    m = 2
    x0, y0 = chunk_origin(key)
    pw, ph = CHUNK_W + 2 * m, CHUNK_H + 2 * m
    big, small = cave_noise(master, z)
    grid = dict(shape=(ph, pw), offset=(y0 - m, x0 - m))
    values = 0.7 * big[tcod.noise.grid(scale=0.07, **grid)] + 0.3 * small[tcod.noise.grid(scale=0.2, **grid)]
    kinds = (values > CAVE_THRESHOLD).astype(np.int8)
    found = structure(master, key)
    ups, downs = layer_stairs(found.links, z)
    _carve(kinds, ups + downs, x0, y0, m)
    landscape = np.full((pw, ph), fill_value=tile_types.wall.get_array(), dtype=tile_types.tile_dt, order="F")
    landscape[kinds == 1] = tile_types.cave_floor.get_array()
    from worldgen import seeded_rng
    with seeded_rng(_mix(master, z, key[0], key[1], 5)):  # the random 'center' wall variations
        landscape = replace_variations(tile_types.wall, landscape, pw, ph)
    tiles = np.asfortranarray(landscape[m:m + CHUNK_W, m:m + CHUNK_H])
    for x, y in ups:
        tiles[x - x0, y - y0] = tile_types.up_stairs.get_array()
    for x, y in downs:
        tiles[x - x0, y - y0] = tile_types.down_stairs.get_array()
    tiles.setflags(write=False)
    return tiles


def clear_caches() -> None:
    for function in (terrain_noise, raw_surface, environment, start_point, structure, sky_layer, cave_noise, cave_layer):
        function.cache_clear()
