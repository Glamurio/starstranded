"""Relief: the large-scale shape of the land (continents, seas, mountain ranges) on top of the old local height noise.

Everything is a pure function of the planet seed and the tile coordinates, so chunks agree and nothing is saved.

- **continent** `c` (very slow noise): below `SEA_LEVEL` the land is under water; the shape of the zero set gives bays, peninsulas,
  gulfs and, where a hilly coast dips under, archipelagos.
- **ranges**: a thin contour line of a second noise is a ridge line; a third noise says where ranges exist at all. Ridge
  profiles are broad at the foot and sharp at the top, so ranges have foothills, a crest, and passes where the ridge noise
  weakens.
- **detail**: the old two-octave height noise, stronger on mountains, makes every slope rough.
- **landing meadow**: around the spawn the continent is forced to gentle land and the ranges are off.

`elevation` is the sum: sea below `SEA_LEVEL`, open ground up to `ROCK_LEVEL`, rock above. The same number is the `elevation`
species habitats ask for, and it cools the air: `LAPSE` degrees of climate temperature per unit above `SNOWLINE`.
"""
from __future__ import annotations

import numpy as np  # type: ignore
import tcod

SPAWN = (35, 20)
SPAWN_LAND, SPAWN_FREE = 60, 150
"""No mountain range within `SPAWN_LAND` tiles of the landing site; ranges are free from `SPAWN_FREE`."""

SEA_LEVEL = -0.30
ROCK_LEVEL = 0.80
SNOWLINE = 0.45
LAPSE = 0.9

CONTINENT_SCALE, RANGE_SCALE, RANGE_MASK_SCALE = 0.0022, 0.0065, 0.0032
RIDGE_HALF_WIDTH = 0.20
"""How far from the ridge's zero contour (in noise units) the foothills reach."""
MOUNTAIN_HEIGHT = 1.35
PLATEAU = 0.55
POND_DISTANCE, POND_RADIUS, POND_DEPTH = (75, 105), 16, 3.2
"""A pond near the landing site, so the first days are not a search for water."""


def smooth(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _shifted(noise, index: int, scale: float, x0, y0, width, height, step: int = 1):
    """Noise `index` read every `step` tiles from (x0, y0) (the coarse grids of `hydrology` use step > 1)."""
    ox, oy = noise.shift
    if step == 1:
        return noise.sample(index, scale, x0 + ox, y0 + oy, width, height)
    return noise.sample(index, scale * step, (x0 + ox) / step, (y0 + oy) / step, width, height)


def find_shift(noise) -> tuple:
    """Where in the noise the world is read from, chosen per seed so that the landing site lies in open land, well inside a
    continent, clear of ranges and in a mild climate (not a desert, not a glacier). (Forcing land at the spawn instead would
    leave a round coast around it.) A handful of probe points around the spawn are enough."""
    import random
    from seeds import mix_seed
    step = 30
    x0, y0 = SPAWN[0] - 90, SPAWN[1] - 60
    best, best_score = (0, 0), -1e9

    def probe(index: int, scale: float, shift) -> np.ndarray:
        origin = ((y0 + shift[1]) / step, (x0 + shift[0]) / step)
        return noise.noises[index][tcod.noise.grid(shape=(5, 7), scale=scale * step, offset=origin)]

    for attempt in range(120):
        rng = random.Random(mix_seed(noise.floor_seed, 7000 + attempt))
        shift = (int(rng.uniform(-30000, 30000)), int(rng.uniform(-30000, 30000)))
        c = probe(6, CONTINENT_SCALE, shift) * 1.7
        mass = smooth(1.0 - np.abs(probe(7, RANGE_SCALE, shift)) / RIDGE_HALF_WIDTH) ** 1.4 * smooth((probe(8, RANGE_MASK_SCALE, shift) - 0.02) / 0.22)
        t, m = np.clip(1.7 * probe(2, 0.006, shift), -1.3, 1.3), np.clip(1.7 * probe(5, 0.007, shift), -1.3, 1.3)
        comfort = min(float(t.min()) + 0.15, 0.55 - float(t.max()), float(m.min()) + 0.15, 0.7 - float(m.max()), 0.0)
        score = float(c.min()) - 1.5 * float(mass.max()) + 2.0 * comfort
        if score > best_score:
            best, best_score = shift, score
        if c.min() > SEA_LEVEL + 0.45 and mass.max() < 0.05 and comfort >= 0.0:
            return shift
    return best


def spawn_freedom(x0: int, y0: int, width: int, height: int, step: int = 1) -> np.ndarray:
    """0 at the landing site, 1 from `SPAWN_FREE` tiles away."""
    xs = x0 + step * np.arange(width)[:, None] - SPAWN[0]
    ys = y0 + step * np.arange(height)[None, :] - SPAWN[1]
    return smooth((np.hypot(xs, ys) - SPAWN_LAND) / (SPAWN_FREE - SPAWN_LAND))


def pond_centre(seed: int) -> tuple:
    """Where the landing site's own pond lies: 75-105 tiles from the spawn, in a direction fixed by the seed."""
    import math
    import random
    from seeds import mix_seed
    rng = random.Random(mix_seed(seed, 2026))
    angle, distance = rng.uniform(0, 2 * math.pi), rng.uniform(POND_DISTANCE[0], POND_DISTANCE[1])
    return SPAWN[0] + distance * math.cos(angle), SPAWN[1] + distance * math.sin(angle) * 0.6


def continent_raw(noise, x0: int, y0: int, width: int, height: int, step: int = 1) -> np.ndarray:
    return _shifted(noise, 6, CONTINENT_SCALE, x0, y0, width, height, step) * 1.7


def continent(noise, x0: int, y0: int, width: int, height: int, step: int = 1) -> np.ndarray:
    raw = continent_raw(noise, x0, y0, width, height, step)
    land = np.where(raw > 0, PLATEAU * np.tanh(np.maximum(raw, 0) / PLATEAU), raw)   # the interior flattens out: rock is for ranges
    px, py = pond_centre(noise.floor_seed)
    xs = x0 + step * np.arange(width)[:, None] - px
    ys = y0 + step * np.arange(height)[None, :] - py
    return land - POND_DEPTH * smooth(1.0 - np.hypot(xs, ys / 0.7) / POND_RADIUS)


def ranges(noise, x0: int, y0: int, width: int, height: int, c: np.ndarray, free: bool = True, step: int = 1) -> np.ndarray:
    """0..1 mountain mass: high on the ridge lines of the range zones, 0 in the sea and at the landing site."""
    ridge = _shifted(noise, 7, RANGE_SCALE, x0, y0, width, height, step)
    zone = smooth((_shifted(noise, 8, RANGE_MASK_SCALE, x0, y0, width, height, step) - 0.02) / 0.22)
    profile = smooth(1.0 - np.abs(ridge) / RIDGE_HALF_WIDTH) ** 1.4
    land = smooth((c - SEA_LEVEL + 0.05) / 0.35)
    return profile * zone * land * (spawn_freedom(x0, y0, width, height, step) if free else 1.0)


def elevation(noise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    c = continent(noise, x0, y0, width, height)
    mass = ranges(noise, x0, y0, width, height, c)
    detail = noise.heights(x0, y0, width, height)          # the old local noise, about -0.35 .. 0.35
    return c + MOUNTAIN_HEIGHT * mass + 0.9 * detail * (1.0 + 1.2 * mass)


def basin_height(noise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    """The height that decides where water stands: continent and ranges plus only the slow part of the local noise, so shores are
    smooth lines and not a spray of single wet tiles."""
    c = continent(noise, x0, y0, width, height)
    return c + MOUNTAIN_HEIGHT * ranges(noise, x0, y0, width, height, c) + 0.22 * noise.sample(0, 0.05, x0, y0, width, height)


def smooth_elevation(noise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    """Elevation without the rough detail (the climate, and so the landmarks, read this)."""
    c = continent(noise, x0, y0, width, height)
    return c + MOUNTAIN_HEIGHT * ranges(noise, x0, y0, width, height, c)


def drainage(noise, x0: int, y0: int, width: int, height: int, step: int = 1) -> np.ndarray:
    """What rivers flow over: the smooth height, read every `step` tiles. It has no local detail (that would give a pit every
    twenty tiles), so its only basins are the real ones: the sea, the pond and inland dips."""
    c = continent(noise, x0, y0, width, height, step)
    return c + MOUNTAIN_HEIGHT * ranges(noise, x0, y0, width, height, c, True, step)
