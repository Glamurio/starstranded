"""Urban regions: the streets, blocks and buildings of cities nobody lives in.

A city is laid out tile by tile from world coordinates (the same way terrain is), so a district looks the same whichever chunk draws
it and buildings and roads run across chunk borders without a seam. For a biome with an `UrbanStyle` (see `biomes`):

- the ground is cut into **blocks** by a street grid (`pitch`, street width `road`, the grid shifted per region so two cities
  do not line up); a smooth noise field makes the middle of a district denser;
- each block holds, with the chances of the style, nothing (a plaza, a yard), a **low building** (a ring of wall entities with a door
  and a floor inside; part of the wall has fallen: `ruin`), a **tower** (solid rock-like tiles drawn with the sheet's tall-building sprites)
  or a **factory** (a larger low building with drums and pipes around it);
- streets are asphalt with a lane marking, with wrecked cars and trucks on them, lamp posts at the corners and signposts at crossings;
- `overgrown` lets the biome's trees and bushes grow back on open ground; `huts` replaces the street grid with scattered small stone huts.

Nobody lives here: there are no creatures, only what they left (see DECISIONS.md)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional, Set, Tuple

import numpy as np  # type: ignore

import biomes
from atlas import sprite_id

NOISE_DENSITY = 23
DENSITY_SCALE = 0.02
ASPHALT = (74, 76, 86)
LANE = (190, 180, 120)
CONCRETE = (126, 124, 120)
TOWER_COLOURS = ((112, 116, 124), (126, 118, 108), (100, 108, 118), (132, 128, 120), (96, 100, 96))
TOWER_SPRITES = tuple((c, 8) for c in range(50, 62))
LANE_H, LANE_V = (51, 3), (50, 3)
WRECKS = (("wreck_car", 0.7), ("wreck_truck", 0.3))
COVERED = 0.6
"""Share of an overgrown city's open ground (not street, not building) that keeps its trees at `overgrown` = 1."""


def _hash(seed: int, a: np.ndarray, b: np.ndarray, salt: int) -> np.ndarray:
    """A float in [0, 1) for every pair of integers (a coordinate hash)."""
    with np.errstate(over="ignore"):
        v = a.astype(np.int64).astype(np.uint64) * np.uint64(73856093) ^ b.astype(np.int64).astype(np.uint64) * np.uint64(19349663)
        v = v ^ np.uint64((seed * 2654435761 + salt * 40503) & 0xFFFFFFFF)
        v ^= v >> np.uint64(13)
        v = v * np.uint64(0x5BD1E995)
        v ^= v >> np.uint64(15)
        v = v * np.uint64(0x27D4EB2D)
        v ^= v >> np.uint64(16)
    return (v & np.uint64(0xFFFFFF)).astype(np.float64) / 16777216.0


@dataclass
class Layout:
    road: np.ndarray            # streets
    lane_h: np.ndarray          # the marking on east-west streets
    lane_v: np.ndarray          # ... and on north-south ones
    crossing: np.ndarray        # where two streets meet
    ring: np.ndarray            # the wall tiles of a low building (before the fallen ones are taken out)
    fallen: np.ndarray          # ring tiles that have fallen
    door: np.ndarray            # the doorway
    inside: np.ndarray          # the floor of a low building
    tower: np.ndarray           # solid tower footprint
    factory: np.ndarray         # lots of factories (inside and ring)
    corner: np.ndarray          # sidewalk corner of a block (where a lamp post may stand)
    tone: np.ndarray            # a number 0..1 per tile that is the same over a whole block (colour variety)


def layout(seed: int, style: "biomes.UrbanStyle", x: np.ndarray, y: np.ndarray, region: np.ndarray, density: np.ndarray) -> Layout:
    """The layout of a city for arrays of world coordinates `x`, `y` (same shape), their region number and a density field 0..1."""
    px, py = style.pitch
    ox, oy = region % px, (region // 7) % py
    gx, lx = np.divmod(x - ox, px)
    gy, ly = np.divmod(y - oy, py)
    road = style.road
    road_x, road_y = lx < road, ly < road
    is_road = road_x | road_y
    lot = lambda salt: _hash(seed, gx + 977 * region, gy, salt)
    centre = 0.35 + 1.3 * density
    built = lot(1) < np.clip(style.built * centre, 0.0, 1.0)
    tower = built & (lot(2) < style.towers * (0.2 + 1.6 * density))
    factory = built & ~tower & (lot(3) < style.industrial)
    shrink = 3 if not style.huts else 4
    left = np.floor(lot(4) * shrink).astype(int)
    right = np.floor(lot(5) * shrink).astype(int)
    top = np.floor(lot(6) * shrink).astype(int)
    bottom = np.floor(lot(7) * shrink).astype(int)
    if style.huts:                      # a hut is a small square somewhere in its cell
        w = 5 + np.floor(lot(8) * 3).astype(int)
        x0 = 1 + np.floor(lot(9) * (px - w - 2)).astype(int)
        y0 = 1 + np.floor(lot(10) * (py - w - 2)).astype(int)
        bx0, bx1, by0, by1 = x0, x0 + w - 1, y0, y0 + w - 1
    else:
        left = np.where(tower | factory, 0, left)
        right = np.where(tower | factory, 0, right)
        top = np.where(tower | factory, 0, top)
        bottom = np.where(tower | factory, 0, bottom)
        bx0, bx1 = road + 1 + left, px - 2 - right
        by0, by1 = road + 1 + top, py - 2 - bottom
    rect = built & (lx >= bx0) & (lx <= bx1) & (ly >= by0) & (ly <= by1) & ~is_road
    edge = rect & ((lx == bx0) | (lx == bx1) | (ly == by0) | (ly == by1))
    low = rect & ~tower
    ring = edge & ~tower
    door = ring & (ly == by1) & (lx == (bx0 + bx1) // 2)
    fall = _hash(seed, x, y, 11) < np.clip(style.ruin * (0.4 + 1.2 * lot(12)), 0.0, 0.95)
    fallen = ring & ~door & fall
    inside = low & ~edge
    middle = road // 2
    lane_h = road_y & ~road_x & (ly == middle) & (x % 4 < 2)
    lane_v = road_x & ~road_y & (lx == middle) & (y % 4 < 2)
    crossing = road_x & road_y
    corner = ~is_road & (((lx == road) | (lx == px - 1)) & ((ly == road) | (ly == py - 1)))
    return Layout(road=is_road, lane_h=lane_h, lane_v=lane_v, crossing=crossing, ring=ring, fallen=fallen, door=door, inside=inside,
                  tower=rect & tower, factory=rect & factory, corner=corner, tone=lot(13))


def styles_by_index() -> Dict[int, "biomes.UrbanStyle"]:
    return {biomes.BIOME_INDEX[k]: b.urban for k, b in biomes.BIOMES.items() if b.urban is not None}


def density_field(noise, x0: int, y0: int, w: int, h: int) -> np.ndarray:
    """0 at the edge of a district (and in its slow gaps), 1 in its heart."""
    n = noise.sample(NOISE_DENSITY, DENSITY_SCALE, x0, y0, w, h)
    return np.clip(0.5 + 0.9 * n, 0.0, 1.0)


def _grid(x0: int, y0: int, w: int, h: int) -> Tuple[np.ndarray, np.ndarray]:
    return np.meshgrid(np.arange(x0, x0 + w), np.arange(y0, y0 + h), indexing="ij")


def layouts(noise, env: dict, x0: int, y0: int, w: int, h: int) -> Dict[int, Tuple["biomes.UrbanStyle", Layout, np.ndarray]]:
    """For each urban style present in the rectangle: `(style, layout, mask of the tiles that belong to it)`."""
    found = {}
    biome = env["biome"]
    styles = styles_by_index()
    present = [i for i in styles if (biome == i).any()]
    if not present:
        return found
    xs, ys = _grid(x0, y0, w, h)
    density = density_field(noise, x0, y0, w, h)
    for index in present:
        style = styles[index]
        found[index] = (style, layout(noise.floor_seed, style, xs, ys, env["region"], density), biome == index)
    return found


def paint(noise, area: Tuple[int, int, int, int], landscape: np.ndarray, env: dict, kinds: np.ndarray, tree_map: np.ndarray) -> None:
    """Streets, yards, floors and towers into the terrain tiles of the rectangle `area` (padded; see `worldgen.generate_terrain`)."""
    import tile_types
    x0, y0, w, h = area
    for index, (style, lay, mine) in layouts(noise, env, x0, y0, w, h).items():
        open_ground = mine & (kinds == 1)
        if not open_ground.any():
            continue
        road = open_ground & lay.road
        tower = open_ground & lay.tower & ~lay.road
        floor = open_ground & (lay.inside | lay.ring)
        yard = open_ground & ~road & ~tower & ~floor
        for layer, scale in (("light", 1.0), ("dark", 0.42)):
            fg, bg = landscape[layer]["fg"], landscape[layer]["bg"]
            fg[road] = (np.array(ASPHALT) * scale * 0.8).astype(np.uint8)
            bg[road] = (np.array(ASPHALT) * 0.12).astype(np.uint8) if layer == "light" else (0, 0, 0)
            fg[floor] = (np.array(CONCRETE) * scale * 0.9).astype(np.uint8)
            for m, sprite in ((open_ground & lay.lane_h, LANE_H), (open_ground & lay.lane_v, LANE_V)):
                landscape[layer]["sprite"][m] = sprite_id(*sprite)
                fg[m] = (np.array(LANE) * scale * 0.9).astype(np.uint8)
        landscape[tower] = tile_types.wall.get_array()
        pick = np.floor(lay.tone * len(TOWER_SPRITES)).astype(int) % len(TOWER_SPRITES)
        tint = np.array(TOWER_COLOURS)[np.floor(lay.tone * 997).astype(int) % len(TOWER_COLOURS)]
        sprites = np.array([sprite_id(*c) for c in TOWER_SPRITES])[pick]
        for layer, scale in (("light", 1.0), ("dark", 0.45)):
            landscape[layer]["sprite"][tower] = sprites[tower]
            landscape[layer]["fg"][tower] = (tint[tower] * scale).astype(np.uint8)
            landscape[layer]["bg"][tower] = (tint[tower] * 0.15).astype(np.uint8) if layer == "light" else (0, 0, 0)
        tree_map[road | tower | floor] = False
        grow = noise.scatter(24, x0, y0, w, h) < style.overgrown * COVERED
        tree_map[yard] &= grow[yard] | (style.overgrown > 0.3)
        if style.overgrown <= 0.3:
            tree_map[yard] &= noise.scatter(25, x0, y0, w, h)[yard] < 0.12
    return None


def reserved_tiles(noise, env: dict, x0: int, y0: int) -> Set[Tuple[int, int]]:
    """Chunk tiles (world coordinates) where nothing wild is placed: streets and buildings."""
    from chunks import CHUNK_H, CHUNK_W
    out: Set[Tuple[int, int]] = set()
    for style, lay, mine in layouts(noise, env, x0, y0, CHUNK_W, CHUNK_H).values():
        for m in (lay.road, lay.ring, lay.inside, lay.tower):
            for lx, ly in np.argwhere(m & mine).tolist():
                out.add((x0 + lx, y0 + ly))
    return out


def populate(source, world, chunk, env: dict) -> int:
    """Wall entities of the low buildings, wrecks, lamp posts, signposts and the odd drum of a chunk. Returns how many were placed."""
    import housing
    import scenery
    from chunks import CHUNK_H, CHUNK_W
    found = layouts(source.noise, env, chunk.x0, chunk.y0, CHUNK_W, CHUNK_H)
    if not found:
        return 0
    noise = source.noise
    planet = getattr(source, "planet", None)
    placed = 0
    walk = chunk.tiles["walkable"][:CHUNK_W, :CHUNK_H]
    liquid = chunk.tiles["liquid"][:CHUNK_W, :CHUNK_H] != 0
    draw = noise.scatter(2600, chunk.x0, chunk.y0, CHUNK_W, CHUNK_H)
    pick = noise.scatter(2601, chunk.x0, chunk.y0, CHUNK_W, CHUNK_H)
    for style, lay, mine in found.values():
        material = housing.material_for(planet, (source.floor_seed ^ 0x51ED) & 0xFFFFFFFF, "stone")
        standing = mine & lay.ring & ~lay.fallen & ~lay.door & walk & ~liquid
        tiles = [tuple(t) for t in np.argwhere(standing).tolist()]
        housing.raise_walls(world, chunk, tiles, material)
        placed += len(tiles)
        # rubble where walls have fallen, wrecks in the street, lamp posts at block corners, signposts at crossings, drums by the factories
        specs = (
            (lay.fallen, "rubble", 0.5, 0), (lay.corner, "lamp_post", 0.45, 1), (lay.crossing, "signpost", 0.18, 2),
            (lay.road & ~lay.crossing, "wreck", style.vehicles, 3), (lay.factory & ~lay.ring, "drum", 0.05, 4), (lay.factory & ~lay.ring, "pipe", 0.04, 5),
        )
        for mask, key, chance, salt in specs:
            if chance <= 0:
                continue
            here = np.argwhere(mine & mask & walk & ~liquid & (_hash(source.floor_seed, *_grid(chunk.x0, chunk.y0, CHUNK_W, CHUNK_H), 90 + salt) < chance))
            for lx, ly in here.tolist():
                x, y = chunk.x0 + lx, chunk.y0 + ly
                kind = key
                if key == "wreck":
                    kind = WRECKS[0][0] if pick[lx, ly] < WRECKS[0][1] else WRECKS[1][0]
                if not scenery.tile_is_free(world, x, y):
                    continue
                variant = int(pick[lx, ly] * 1000)
                color = scenery.vary(scenery.BY_KEY[kind].color, (variant % 97) / 96.0, (variant % 89) / 88.0)
                world.add_entity(scenery.Scenery(kind, variant, color), x, y)
                placed += 1
    return placed


MARGIN = 8
"""Tiles round a chunk that count as its surroundings when asking whether a city touches it."""


@lru_cache(maxsize=8192)
def touches(master: int, key: Tuple[int, int]) -> bool:
    """Whether any urban region lies within the chunk or `MARGIN` tiles of it (so farms, hamlets and sites keep out of cities whole, not just at the middle)."""
    import regions
    import shafts
    from chunks import CHUNK_H, CHUNK_W
    x0, y0 = key[0] * CHUNK_W - MARGIN, key[1] * CHUNK_H - MARGIN
    field = regions.field(shafts.terrain_noise(master), x0, y0, CHUNK_W + 2 * MARGIN, CHUNK_H + 2 * MARGIN)
    urban = np.array([biomes.BIOMES[k].urban is not None for k in biomes.BIOME_IDS])
    return bool(urban[field.biome].any())
