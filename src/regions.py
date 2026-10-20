"""Regions: where each biome lies, decided at world scale.

The old climate table decided a biome tile by tile from a smooth temperature and moisture, so any biome that did not follow
the climate bands (a fungal forest, a crystal field) had to be a separate overlay, and anything noise-driven came out as small
patches. Here the world is cut into **regions** instead:

1. every cell of a coarse grid (`CELL` tiles, about two chunks wide each way...) owns one jittered *site*, a pure function of
   the seed and the cell's coordinates;
2. the site's biome is drawn from the biomes whose climate (temperature, moisture, smooth elevation) suits the climate *at the
   site*, weighted by each biome's `rarity`; near the landing site only mild biomes are allowed;
3. a tile belongs to the region of the nearest site after its position has been bent by two slow noise fields (`WARP`), so
   regions are organic blobs of 100-200 tiles, not squares;
4. the second-nearest site gives the neighbouring region and how far the tile is from the border: the ground colours blend over
   `BORDER` tiles and the plants of both regions mix there. The tile's identity stays that of its own region.

Everything is a pure function of (seed, x, y): two chunks that share a border agree on it, and the order in which chunks are
loaded cannot change a thing. Sites and their biomes are cached per seed.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np  # type: ignore

import biomes
import relief
from ecology import membership
from seeds import mix_seed

CELL = 150
"""Edge of a region cell, in tiles: regions are about this wide (a chunk is 70 by 40)."""
JITTER = 0.7
"""A site lies in the middle `JITTER` of its cell, so regions are never tiny slivers."""
WARP, WARP_SCALE = 55.0, 0.011
"""How far (tiles) the noise bends a tile's position before the nearest site is found, and the noise frequency: borders wander."""
BORDER = 14.0
"""Tiles over which the ground blends across a border and the two regions' plants mix."""
SPAWN_SAFE = 300.0
"""Within this many tiles of the landing site only the mild biomes (`mild`) may be a region's biome."""
NOISE_WARP_X, NOISE_WARP_Y = 16, 17
"""`TerrainNoise` generators used here."""


@dataclass(frozen=True)
class Site:
    x: float
    y: float
    biome: int          # index into `biomes.BIOME_IDS`
    key: int            # a number that names the region (stable, unique per cell)


_SITES: Dict[Tuple[int, int, int], Site] = {}


def mild(biome: "biomes.Biome") -> bool:
    """Whether a biome is a fair place to start in: temperate, and not one of the hostile families."""
    return -8 < biome.ambient < 34 and biome.family not in ("volcanic", "decay", "alien", "urban", "fungal", "crystal")


def _choose(noise, cx: int, cy: int, px: float, py: float) -> int:
    seed = noise.floor_seed
    rng = random.Random(mix_seed(seed, cx, cy, 7101))
    t = float(noise.temperature(int(px), int(py), 1, 1)[0, 0])
    m = float(noise.moisture(int(px), int(py), 1, 1)[0, 0])
    e = float(relief.smooth_elevation(noise, int(px), int(py), 1, 1)[0, 0])
    near_spawn = np.hypot(px - relief.SPAWN[0], py - relief.SPAWN[1]) < SPAWN_SAFE
    keys = [k for k in biomes.REGION_BIOMES if not near_spawn or mild(biomes.BIOMES[k])]
    weights = []
    for key in keys:
        b = biomes.BIOMES[key]
        weights.append(float(membership(t, b.temperature) * membership(m, b.moisture) * membership(e, b.elevation)) * b.rarity)
    if sum(weights) <= 0:           # a climate no biome claims: the nearest one in the (temperature, moisture) plane
        def gap(key: str) -> float:
            b = biomes.BIOMES[key]
            return max(0.0, b.temperature[0] - t, t - b.temperature[1]) + max(0.0, b.moisture[0] - m, m - b.moisture[1])
        return biomes.BIOME_INDEX[min(keys, key=gap)]
    return biomes.BIOME_INDEX[rng.choices(keys, weights=weights)[0]]


def site(noise, cx: int, cy: int) -> Site:
    """The site of region cell (cx, cy)."""
    k = (noise.floor_seed, cx, cy)
    found = _SITES.get(k)
    if found is None:
        rng = random.Random(mix_seed(noise.floor_seed, cx, cy, 7100))
        px = (cx + (1.0 - JITTER) / 2.0 + JITTER * rng.random()) * CELL
        py = (cy + (1.0 - JITTER) / 2.0 + JITTER * rng.random()) * CELL
        found = _SITES[k] = Site(px, py, _choose(noise, cx, cy, px, py), (cx * 73856093 ^ cy * 19349663) & 0x7FFFFFFF)
    return found


def clear_caches() -> None:
    _SITES.clear()


@dataclass
class Field:
    biome: np.ndarray       # (w, h) int16, the biome of the tile's region
    other: np.ndarray       # (w, h) int16, the biome of the neighbouring region
    edge: np.ndarray        # (w, h) float, 0 deep inside a region .. 0.5 on a border: the neighbour's share
    region: np.ndarray      # (w, h) int64, the number of the tile's region (see `Site.key`)


def smooth(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def field(noise, x0: int, y0: int, width: int, height: int) -> Field:
    """The regions of a world rectangle."""
    wx = np.arange(x0, x0 + width, dtype=float)[:, None] + WARP * noise.sample(NOISE_WARP_X, WARP_SCALE, x0, y0, width, height)
    wy = np.arange(y0, y0 + height, dtype=float)[None, :] + WARP * noise.sample(NOISE_WARP_Y, WARP_SCALE, x0, y0, width, height)
    cx0, cx1 = int(np.floor((wx.min()) / CELL)) - 1, int(np.floor((wx.max()) / CELL)) + 1
    cy0, cy1 = int(np.floor((wy.min()) / CELL)) - 1, int(np.floor((wy.max()) / CELL)) + 1
    sites = [site(noise, cx, cy) for cx in range(cx0, cx1 + 1) for cy in range(cy0, cy1 + 1)]
    distance = np.stack([(wx - s.x) ** 2 + (wy - s.y) ** 2 for s in sites])          # squared, (n, w, h)
    first = np.argmin(distance, axis=0)
    d1 = np.take_along_axis(distance, first[None], axis=0)[0]
    masked = distance.copy()
    np.put_along_axis(masked, first[None], np.inf, axis=0)
    second = np.argmin(masked, axis=0)
    d2 = np.take_along_axis(masked, second[None], axis=0)[0]
    px = np.array([s.x for s in sites])
    py = np.array([s.y for s in sites])
    pair = np.hypot(px[first] - px[second], py[first] - py[second])
    border = (d2 - d1) / (2.0 * np.maximum(pair, 1.0))              # distance to the bisector of the two sites
    index = np.array([s.biome for s in sites], dtype=np.int16)
    key = np.array([s.key for s in sites], dtype=np.int64)
    biome, other = index[first], index[second]
    edge = 0.5 * (1.0 - smooth(border / BORDER))
    edge = np.where(biome == other, 0.0, edge)
    return Field(biome, other, edge, key[first])


def biome_at(noise, x: int, y: int) -> str:
    """The key of the region biome at one tile (no wetland or shore overlay)."""
    return biomes.BIOME_IDS[int(field(noise, x, y, 1, 1).biome[0, 0])]
