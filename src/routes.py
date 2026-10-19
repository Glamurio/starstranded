"""Planned routes: trodden paths (and the odd plank bridge) between the places that were built on the surface.

Sites are the chunks that have a building (a roll on the seed alone, so nothing has to be generated to know) and the precursor
ruins. Every site is joined to its nearest other site within `RANGE` chunks by a route: a straight line with one bend, laid down
as `path` tiles over open ground, as `bridge` planks over a short stretch of water that has dry ground on both sides, and
left out over rock and wide water. A route is a pure function of the seed and its two ends, so every chunk it crosses draws
the same line and the pieces meet exactly at the chunk borders.

Not modelled: farms and urban areas (the game has neither), and ending a route at the door of the building (the building's
spot inside its chunk is only decided when that chunk is generated, which a neighbouring chunk must not trigger)."""
from __future__ import annotations

import random
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np  # type: ignore

from chunks import CHUNK_H, CHUNK_W, ChunkKey

RANGE = 4
"""A site is joined to its nearest neighbour if that lies within this many chunks."""
MAX_SPAN = 6
"""Longest stretch of water (tiles) a route bridges."""
PATCH = 24
BUILDING_ROLL = 0.2      # (shafts.BUILDING_CHANCE; kept equal by a test)
JITTER = 8


def _rng(master: int, *values: int) -> random.Random:
    from worldgen import mix_seed
    return random.Random(mix_seed(master, 4747, *values))


def is_site(master: int, key: ChunkKey) -> bool:
    """Whether chunk `key` is a site: a ruin, or a building by the roll of `shafts.structure` (the landing chunk is not)."""
    if key == (0, 0):
        return False
    import structures
    if key in structures.ruin_chunks(master):
        return True
    from shafts import _mix
    return random.Random(_mix(master, key[0], key[1], 7)).random() < BUILDING_ROLL


def site_point(master: int, key: ChunkKey) -> Tuple[int, int]:
    """Where in chunk `key` a route ends: near the middle."""
    rng = _rng(master, key[0], key[1], 1)
    return (key[0] * CHUNK_W + CHUNK_W // 2 + rng.randint(-JITTER, JITTER),
            key[1] * CHUNK_H + CHUNK_H // 2 + rng.randint(-JITTER // 2, JITTER // 2))


@lru_cache(maxsize=512)
def sites_near(master: int, key: ChunkKey, radius: int) -> Tuple[ChunkKey, ...]:
    return tuple((key[0] + dx, key[1] + dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)
                 if is_site(master, (key[0] + dx, key[1] + dy)))


@lru_cache(maxsize=512)
def nearest(master: int, key: ChunkKey) -> Optional[ChunkKey]:
    """The nearest other site within `RANGE` chunks of site `key` (ties by position), or None."""
    best = None
    for other in sites_near(master, key, RANGE):
        if other == key:
            continue
        d = (other[0] - key[0]) ** 2 + (other[1] - key[1]) ** 2
        if best is None or (d, other) < best[0]:
            best = ((d, other), other)
    return None if best is None else best[1]


def edges_near(master: int, key: ChunkKey) -> List[Tuple[ChunkKey, ChunkKey]]:
    """The routes (as ordered site pairs) that may cross chunk `key`: each site within RANGE of it, to its nearest."""
    found = set()
    for site in sites_near(master, key, RANGE):
        other = nearest(master, site)
        if other is not None:
            found.add((min(site, other), max(site, other)))
    return sorted(found)


def line(a: Tuple[int, int], b: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Tiles of the straight line a..b (Bresenham), both ends included."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    out = []
    while True:
        out.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def course(master: int, a: ChunkKey, b: ChunkKey) -> List[Tuple[int, int]]:
    """The tiles of the route between sites a and b: a line with one bend."""
    p, q = site_point(master, a), site_point(master, b)
    rng = _rng(master, a[0], a[1], b[0], b[1])
    mx, my = (p[0] + q[0]) // 2, (p[1] + q[1]) // 2
    length = max(abs(q[0] - p[0]), abs(q[1] - p[1]))
    bend = (mx + rng.randint(-length // 5, length // 5), my + rng.randint(-length // 5, length // 5))
    first, second = line(p, bend), line(bend, q)
    return first + second[1:]


@lru_cache(maxsize=64)
def laid(master: int, a: ChunkKey, b: ChunkKey) -> Dict[Tuple[int, int], bool]:
    """`{(x, y): is_deck}` for the tiles of the route a-b that get a path (False) or a plank (True)."""
    import hydrology
    import worldgen
    from shafts import terrain_noise
    noise = terrain_noise(master)
    tiles = course(master, a, b)
    patches: Dict[Tuple[int, int], Tuple[np.ndarray, np.ndarray]] = {}

    def kind(x: int, y: int) -> Tuple[int, bool]:
        px, py = x // PATCH, y // PATCH
        if (px, py) not in patches:
            args = (noise, px * PATCH, py * PATCH, PATCH, PATCH)
            bad = hydrology.lava_mask(*args) | hydrology.hot_spring_mask(*args) | hydrology.waterfall_mask(*args)
            patches[(px, py)] = (worldgen.base_terrain(*args), bad)
        kinds, bad = patches[(px, py)]
        return int(kinds[x - px * PATCH, y - py * PATCH]), bool(bad[x - px * PATCH, y - py * PATCH])

    marks = [kind(x, y) for x, y in tiles]
    out: Dict[Tuple[int, int], bool] = {}
    i = 0
    while i < len(tiles):
        k, bad = marks[i]
        if k == 1:
            out[tiles[i]] = False
            i += 1
        elif k == 0:
            j = i
            while j < len(tiles) and marks[j][0] == 0:
                j += 1
            span = j - i
            clean = not any(marks[n][1] for n in range(i, j))
            if clean and span <= MAX_SPAN and i > 0 and j < len(tiles) and marks[i - 1][0] == 1 and marks[j][0] == 1:
                for n in range(i, j):
                    out[tiles[n]] = True
            i = j
        else:
            i += 1
    return out


def paint(master: int, key: ChunkKey, tiles: np.ndarray, tree_map: np.ndarray) -> None:
    """Lay the routes crossing chunk `key` into its (copied) tiles and clear the trees they pass: path over ground, planks over a
    short stretch of water. Only ever replaces plain floor, ground cover and water, never rock or a structure."""
    import tile_types
    x0, y0 = key[0] * CHUNK_W, key[1] * CHUNK_H
    for a, b in edges_near(master, key):
        for (x, y), deck in laid(master, a, b).items():
            lx, ly = x - x0, y - y0
            if not (0 <= lx < CHUNK_W and 0 <= ly < CHUNK_H):
                continue
            here = tiles[lx, ly]
            if deck:
                if here["depth"] > 0 and here["liquid"] > 0 or here["liquid"] == 0 and here["walkable"]:
                    tiles[lx, ly] = tile_types.bridge.get_array()
            elif here["walkable"] and here["liquid"] == 0 and not here["stairs"]:
                tiles[lx, ly] = tile_types.path.get_array()
            tree_map[lx, ly] = False
