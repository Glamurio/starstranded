"""Deterministic generation of chunks from `(floor_seed, cx, cy)`.

Terrain noise is sampled in world coordinates, so it is seamless across chunk borders. The steps that look at
neighbouring tiles (lake dilation, edge variations of water and walls) run on a region padded by `MARGIN` tiles on
every side and only the 70x40 interior is kept, so a tile on a border sees the same neighbours whichever chunk is
generated. Everything random inside a chunk runs under `seeded_rng(chunk_seed)`, which also covers incidental
`random` use in entity constructors (shades, names, mirroring): generating a chunk twice gives the same terrain and
the same entities (only uids differ).
"""
from __future__ import annotations

import contextlib
import random
from typing import Dict, Iterator, List, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import tcod

import hydrology
import landmarks
import relief
import shafts
from seeds import mix_seed  # noqa: F401  (re-exported: worldgen.mix_seed is the long-standing import path)
import tile_types
from atlas import sprite_id
from chunks import CHUNK_H, CHUNK_W, Chunk, ChunkKey, chunk_origin
from entity import EntityCategory
from species import PlantCategory, PlantSpecies, make_plant_species

if TYPE_CHECKING:
    from world import World

MARGIN = 8
"""Padding (tiles) around a chunk for neighbour-dependent generation steps: dilation (1) + variations (1) + the two
erosions that give the liquid depths (2), and the wetland damp that reaches `WET_REACH` (6) tiles from water."""

SHALLOW_COLOR = (92, 150, 186)
DEEP_COLOR = (58, 104, 148)
"""The classic blue, kept as the fallback and for hand-built maps; generated lakes take their colour from `liquid_palette`."""
HUE_STOPS = ((0.00, 205.0), (0.30, 218.0), (0.45, 182.0), (0.58, 152.0), (0.68, 110.0), (0.76, 62.0), (0.84, 292.0), (0.92, 322.0), (1.00, 345.0))
"""Lake hue (degrees) along the slowly varying lake-colour noise (0..1): mostly sea blues and teals, then greens, lime, gold, and the
violets and rose of an alien chemistry. Interpolated, so neighbouring lakes shade into each other."""
PLATEAU_EDGE = 0.25
KIND_HUE, KIND_PULL = {2: 285.0, 3: 78.0}, 0.3
"""What a lake is made of tints it a little (toxic towards violet, acid towards yellow-green): a faint tell, never a label, since
the colour field is independent of the kind field and plenty of clean-looking lakes are poisonous."""
LIQUID_SATURATION, SHALLOW_VALUE, DEEP_VALUE = 0.68, 0.80, 0.54
"""Liquid has exactly two colours, the same everywhere: shallow (depth 1) and deep (depth 2 and 3). They are close in
brightness on purpose: a stark light/dark edge clashes with the land."""
FOAM_COLOR = (225, 240, 250)
LAVA_COLOR = (235, 90, 20)
HOT_COLOR = (120, 185, 175)
BASE_THRESHOLD = -0.02
WOODLAND_REACH = 0.8   # how far the large-scale woodland noise moves the planting threshold
IMPURE_BELOW, TOXIC_BELOW = 0.15, 0.40  # liquid noise thresholds: below the first is impure, below the second toxic, else acidic

OUTCROP_ABOVE = 0.28

# Terrain kinds come from `relief.elevation`: water below `relief.SEA_LEVEL`, open ground up to `relief.ROCK_LEVEL`, rock above.


@contextlib.contextmanager
def seeded_rng(seed: int) -> Iterator[None]:
    """Run a block with the global `random` and `numpy.random` seeded from `seed`, restoring their state after."""
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    random.seed(seed)
    np.random.seed(seed % 2**32)
    try:
        yield
    finally:
        random.setstate(python_state)
        np.random.set_state(numpy_state)


_SHIFTS: Dict[int, Tuple[int, int]] = {}
"""Per seed, where the relief is read from (found once, see `relief.find_shift`)."""


class TerrainNoise:
    """The floor's four noise generators (two for height, two for vegetation, as the single-map generator had)."""

    def __init__(self, floor_seed: int):
        self.floor_seed = floor_seed
        self.noises = [
            tcod.noise.Noise(dimensions=2, algorithm=tcod.noise.Algorithm.PERLIN, seed=mix_seed(floor_seed, i) % 2**31)
            for i in range(landmarks.NOISE_BASE + len(landmarks.LANDMARK_IDS))   # 0-15 terrain and climate, then one per landmark
        ]
        self.shift = _SHIFTS.get(floor_seed)
        if self.shift is None:
            self.shift = (0, 0)
            self.shift = _SHIFTS[floor_seed] = relief.find_shift(self)

    def scatter(self, salt: int, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """A pseudo-random number in [0, 1) for every tile of a world rectangle, a pure function of (seed, salt, x, y): the same
        tile gets the same number however the rectangle is cut, so chunk borders show no seam (unlike the global RNG)."""
        mask = 2 ** 64 - 1
        with np.errstate(over="ignore"):
            xs = np.arange(x0, x0 + width, dtype=np.int64).astype(np.uint64)[:, None]
            ys = np.arange(y0, y0 + height, dtype=np.int64).astype(np.uint64)[None, :]
            key = np.uint64((self.floor_seed * 0x165667B19E3779F9 + salt * 0x27D4EB2F165667C5) & mask)
            h = xs * np.uint64(0x9E3779B97F4A7C15) ^ ys * np.uint64(0xC2B2AE3D27D4EB4F) ^ key
            h ^= h >> np.uint64(33)
            h *= np.uint64(0xFF51AFD7ED558CCD)
            h ^= h >> np.uint64(33)
            h *= np.uint64(0xC4CEB9FE1A85EC53)
            h ^= h >> np.uint64(33)
        return (h >> np.uint64(11)).astype(np.float64) / float(2 ** 53)

    def sample(self, index: int, scale: float, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Noise `index` on the world rectangle (x0, y0, width, height) as a [x, y] array."""
        samples = self.noises[index][tcod.noise.grid(shape=(height, width), scale=scale, offset=(y0, x0))]
        assert samples.shape == (width, height), (
            f"tcod.noise.grid axis order changed: got {samples.shape}, expected {(width, height)}"
        )
        return samples

    def heights(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        return (self.sample(0, 0.05, x0, y0, width, height) + self.sample(1, 0.25, x0, y0, width, height)) / 2

    def liquid_hue_field(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Slowly varying noise for the colour of a lake (noise 12: unused by anything else), unrelated to its kind on purpose."""
        return self.sample(12, 0.0012, x0, y0, width, height)

    def liquid_kind_field(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Slowly varying noise that decides what a lake is made of (a lake is mostly one kind)."""
        return self.sample(4, 0.006, x0, y0, width, height)

    def temperature(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Climate temperature, about -1 (frozen) .. 1 (scorching), varying over a few hundred tiles."""
        return np.clip(1.7 * self.sample(2, 0.006, x0 + self.shift[0], y0 + self.shift[1], width, height), -1.3, 1.3)

    def moisture(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Climate moisture, about -1 (arid) .. 1 (soaked)."""
        return np.clip(1.7 * self.sample(5, 0.007, x0 + self.shift[0], y0 + self.shift[1], width, height), -1.3, 1.3)

    def woodland(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Large-scale stands, about -0.7 (a clearing) .. 0.7 (deep wood): the same noise as `vegetation`, read ~100 tiles wide
        and offset, so a biome is a patchwork of open ground, copses and forest instead of one even sprinkle."""
        return self.sample(3, 0.012, x0 + 7919, y0 - 4421, width, height)

    def vegetation(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        # (The single-map generator also sampled noise 2 at scale 0.05 but overwrote it; the result is noise 3 only.)
        return self.sample(3, 0.1, x0, y0, width, height)


def base_terrain(noise: TerrainNoise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    """The deterministic part of the terrain (no RNG): 0 water, 1 floor, 2 wall, lakes grown by one tile.

    Correct for every tile of the rectangle except its outermost ring (dilation needs the neighbour).
    """
    from procgen import dilate
    height_map = relief.elevation(noise, x0, y0, width, height)
    # (rock is the mountains plus the odd outcrop of the local noise, so there is stone to mine on any plain)
    rock = (height_map > relief.ROCK_LEVEL) | (noise.heights(x0, y0, width, height) > OUTCROP_ABOVE)
    wet = relief.basin_height(noise, x0, y0, width, height) < relief.SEA_LEVEL
    kinds = np.where(wet, 0, np.where(rock, 2, 1)).astype(np.int8)
    kinds = np.asfortranarray(kinds)
    kinds[dilate(kinds == 0)] = 0
    kinds[hydrology.water_mask(noise, x0, y0, width, height)] = 0      # rivers, springs, estuaries and lakes at river ends
    kinds[hydrology.hot_spring_mask(noise, x0, y0, width, height)] = 0
    kinds[hydrology.lava_mask(noise, x0, y0, width, height)] = 0
    return kinds


WET_REACH, WET_BOOST = 6, 0.6
"""How far (tiles) the damp of water reaches over low ground, and how much moisture it adds at the shore."""
WATER_PROXIMITY = (1.0, 1.0, 0.7, 0.4)
"""Water availability by distance (tiles) from liquid: 0 = in it, 1, 2, 3; beyond that 0."""


def environment_for(noise: TerrainNoise, x0: int, y0: int, width: int, height: int, kinds: np.ndarray) -> dict:
    """Environment arrays (see `ecology`) for a world rectangle whose base terrain kinds (0 water) are `kinds`:
    temperature, moisture, elevation, fertility, light, water, the biome index and the landmark (index, strength; see
    `landmarks`). All pure functions of the seed."""
    from procgen import dilate
    import biomes
    elevation = relief.elevation(noise, x0, y0, width, height)
    # Wetlands: low ground near water (river banks, lake shores, estuaries) is soaked, so the swamp and bog overlay of the
    # biome table takes it. The damp fades out over `WET_REACH` tiles.
    distance = shore_distance(kinds == 0, WET_REACH)
    damp = np.clip(1.0 - (distance - 1) / WET_REACH, 0.0, 1.0) * (distance > 0) * relief.smooth((0.3 - elevation) / 0.3)
    moisture = noise.moisture(x0, y0, width, height) + WET_BOOST * damp
    shore = np.clip(1.0 - (distance - 1) / (WET_REACH - 1), 0.0, 1.0) * (distance > 0)   # 1 at the water's edge, 0 six tiles inland
    # (the air cools with the smooth height only: rough detail would make temperature, and so the biome, jump from tile to tile)
    cooling = relief.LAPSE * np.maximum(relief.smooth_elevation(noise, x0, y0, width, height) - relief.SNOWLINE, 0.0)
    temperature = noise.temperature(x0, y0, width, height) - cooling
    biome = biomes.classify(temperature, moisture, elevation)
    water = np.zeros((width, height), dtype=float)
    reach = kinds == 0
    water[reach] = WATER_PROXIMITY[0]
    for distance in range(1, len(WATER_PROXIMITY)):
        reach = dilate(reach)
        water[reach & (water == 0)] = WATER_PROXIMITY[distance]
    fertility = np.clip(np.array([biomes.BIOMES[k].vegetation for k in biomes.BIOME_IDS])[biome] / 1.6, 0.0, 1.0)
    env = dict(temperature=temperature, moisture=moisture, elevation=elevation, fertility=fertility,
               light=np.ones((width, height)), water=water, biome=biome, land=kinds != 0, shore=shore)
    env["landmark"], env["landmark_strength"] = landmarks.field(noise, x0, y0, width, height, env)
    return env


def chunk_environment(noise: TerrainNoise, x0: int, y0: int, width: int = CHUNK_W, height: int = CHUNK_H) -> dict:
    """The environment arrays of one chunk (interior only), computed the same way `generate_terrain` sees them."""
    m = MARGIN
    kinds = base_terrain(noise, x0 - m, y0 - m, width + 2 * m, height + 2 * m)
    env = environment_for(noise, x0 - m, y0 - m, width + 2 * m, height + 2 * m, kinds)
    interior = (slice(m, m + width), slice(m, m + height))
    return {k: np.ascontiguousarray(v[interior]) for k, v in env.items()}


def liquid_palette(noise: TerrainNoise, kind: np.ndarray, x0: int, y0: int, width: int, height: int) -> Tuple[np.ndarray, np.ndarray]:
    """`(shallow, deep)` RGB (float, shape (width, height, 3)) for every tile of the rectangle: a pure function of the lake-colour
    noise and the liquid kind, so a lake keeps its colour across chunk borders and neighbouring lakes differ."""
    import colorsys
    field = noise.liquid_hue_field(x0, y0, width, height)
    u = np.clip(0.5 + field / 1.1, 0.0, 1.0)
    stops = np.array(HUE_STOPS)
    # plateaus: most of a body of water keeps one colour and the change to the next is a short band, so an ocean is not a rainbow
    cells = u * (len(stops) - 1)
    base = np.floor(cells)
    blend = np.clip((cells - base - 0.5) / PLATEAU_EDGE + 0.5, 0.0, 1.0)
    hue = stops[np.minimum(base.astype(int), len(stops) - 1), 1] * (1 - blend) + stops[np.minimum(base.astype(int) + 1, len(stops) - 1), 1] * blend
    for number, target in KIND_HUE.items():
        pull = np.where(kind == number, KIND_PULL, 0.0)
        delta = (target - hue + 180.0) % 360.0 - 180.0         # the short way round the colour wheel
        hue = (hue + delta * pull) % 360.0
    out = []
    for value in (SHALLOW_VALUE, DEEP_VALUE):
        # (vectorised hsv->rgb)
        h = (hue / 60.0) % 6.0
        s, v = LIQUID_SATURATION, value
        c = v * s
        x = c * (1 - np.abs(h % 2 - 1))
        m = v - c
        z = np.zeros_like(h)
        sector = h.astype(int)
        r = np.choose(sector, (c, x, z, z, x, c))
        g = np.choose(sector, (x, c, c, x, z, z))
        b = np.choose(sector, (z, z, x, c, c, x))
        out.append(np.stack([r + m, g + m, b + m], axis=-1) * 255.0)
    return out[0], out[1]


def _shape_liquid(noise: TerrainNoise, landscape: np.ndarray, liquid: np.ndarray, x0: int, y0: int, width: int, height: int):
    """Give the lake tiles (`liquid` mask) their depth (1 on the shore, +1 per tile inwards, at most 3: deeper liquid is
    always ringed by shallower), kind and colour (shallow or deep, see `liquid_palette`). Shallow liquid can be waded, deeper liquid
    cannot. Returns the palette `(shallow, deep)` for the whole rectangle (the shores borrow it)."""
    from procgen import neighbour_masks
    depth = liquid.astype(np.int8)
    inner = liquid
    for _ in range(2):
        left, right, up, down = neighbour_masks(inner)
        inner = inner & left & right & up & down
        depth += inner
    kind_value = noise.liquid_kind_field(x0, y0, width, height)
    kind = np.where(kind_value < IMPURE_BELOW, 1, np.where(kind_value < TOXIC_BELOW, 2, 3)).astype(np.int8)
    shallow, deep = liquid_palette(noise, kind, x0, y0, width, height)
    light = np.where((depth >= 2)[..., None], deep, shallow).astype(np.uint8)
    landscape["liquid"][liquid] = kind[liquid]
    landscape["depth"][liquid] = depth[liquid]
    landscape["walkable"][liquid] = depth[liquid] == 1
    landscape["light"]["fg"][liquid] = light[liquid]
    landscape["dark"]["fg"][liquid] = (light[liquid] * 0.5).astype(np.uint8)
    return shallow, deep


# ── ground cover and shores ─────────────────────────────────────────────────────────────────────────────
_TUFTS = ((3, 9), (4, 9), (5, 9), (1, 9), (7, 9), (8, 9), (9, 9), (19, 9), (20, 9))
_FERNS = ((10, 9), (11, 9), (12, 9))
_LEAVES = ((17, 9), (18, 9))
_DRY = ((3, 9), (4, 9), (5, 9))
GROUND_COVER: Dict[str, Tuple[Tuple[int, int], ...]] = {
    "glacial": _DRY, "tundra": _DRY + ((1, 9),), "taiga": _TUFTS + _FERNS, "steppe": _DRY + ((7, 9), (8, 9)),
    "temperate_forest": _TUFTS + _FERNS + _LEAVES, "grassland": _TUFTS, "shrubland": _DRY + ((7, 9), (8, 9)),
    "savanna": _DRY + ((7, 9), (8, 9)), "jungle": _TUFTS + _FERNS + _LEAVES + _LEAVES, "badlands": _DRY, "desert": _DRY,
    "swamp": _TUFTS + _FERNS + _LEAVES, "bog": _TUFTS + _FERNS,
}
"""The little plants drawn on open ground, by biome: tufts of grass, ferns, leaves, toadstools (sprites of the sheet).
They are part of the terrain graphics, not objects: free to draw, nothing to save, nothing to pick up."""
COVER_BASE, COVER_PER_VEGETATION, COVER_MAX = 0.06, 0.30, 0.5
"""Share of open ground that carries cover: `COVER_BASE + COVER_PER_VEGETATION * biome.vegetation` (at most `COVER_MAX`)."""

SHORE_WET = (0.40, 0.22, 0.09)
"""How far the damp of a shore reaches into the land: the share of the water colour mixed into the ground 1, 2 and 3 tiles
from the water."""


def shore_distance(water: np.ndarray, reach: int = 3) -> np.ndarray:
    """Tiles from the nearest water for every tile: 0 in the water, 1..`reach` on land, `reach` + 1 further away."""
    from procgen import dilate
    distance = np.full(water.shape, reach + 1, dtype=np.int8)
    distance[water] = 0
    seen = water.copy()
    for step in range(1, reach + 1):
        grown = dilate(seen)
        distance[grown & ~seen] = step
        seen = grown
    return distance


def _mix(a: np.ndarray, b: np.ndarray, share) -> np.ndarray:
    return (a.astype(float) * (1.0 - share) + b.astype(float) * share)


def _blend_shores(noise: TerrainNoise, area, landscape: np.ndarray, water: np.ndarray, ground: np.ndarray, open_ground: np.ndarray,
                  shallow: np.ndarray, deep: np.ndarray) -> None:
    """Soften the edge between water and land into a gradient: the ground gets damper and bluer towards the water, shallow
    water takes some of the ground's colour, and the step from shallow to deep water is split in two. Every tile gets a few
    shades of variation so the bands do not read as stripes."""
    distance = shore_distance(water)
    jitter = np.floor(noise.scatter(1, *area) * 9 - 4)[..., None]   # -4..4 shades, the same for a tile whichever chunk makes it
    for step, share in enumerate(SHORE_WET, start=1):
        band = open_ground & (distance == step)
        if not band.any():
            continue
        for layer, scale in (("light", 0.8), ("dark", 0.4)):
            damp = shallow[band] * scale * 0.85 + ground[band].astype(float) * scale * 0.15
            colour = _mix(landscape[layer]["fg"][band], damp, share) + jitter[band]
            landscape[layer]["fg"][band] = np.clip(colour, 0, 255).astype(np.uint8)
        damp_bg = shallow[band] * 0.10
        landscape["light"]["bg"][band] = np.clip(_mix(landscape["light"]["bg"][band], damp_bg, share), 0, 255).astype(np.uint8)
    depth = landscape["depth"]
    for level, base, other, share in ((1, shallow, ground * 0.8, 0.22), (2, deep, shallow, 0.45)):
        band = water & (depth == level)
        if not band.any():
            continue
        colour = _mix(base[band], other[band], share) + jitter[band]
        landscape["light"]["fg"][band] = np.clip(colour, 0, 255).astype(np.uint8)
        landscape["dark"]["fg"][band] = np.clip(colour * 0.5, 0, 255).astype(np.uint8)


def _cover_ground(noise: TerrainNoise, area, landscape: np.ndarray, env: dict, open_ground: np.ndarray, vegetation: np.ndarray) -> None:
    """Scatter little plants over open ground (see `GROUND_COVER`): a sprite, tinted from the ground under it."""
    import biomes
    chance = np.clip(COVER_BASE + COVER_PER_VEGETATION * vegetation, 0.0, COVER_MAX)
    covered = open_ground & (noise.scatter(2, *area) < chance)
    pick, turn, tone = noise.scatter(3, *area), noise.scatter(4, *area), noise.scatter(5, *area)
    # A landmark's own cover takes over where the landmark is strong (the edge mixes both, tile by tile).
    own = (env["landmark"] > 0) & (noise.scatter(6, *area) < env["landmark_strength"])
    groups = [(covered & ~own & (env["biome"] == index), GROUND_COVER[key]) for index, key in enumerate(biomes.BIOME_IDS)]
    groups += [(covered & own & (env["landmark"] == number), landmarks.LANDMARKS[key].cover)
               for key, number in landmarks.LANDMARK_INDEX.items()]
    for mask, cells in groups:
        count = int(mask.sum())
        if not count:
            continue
        sprites = np.array([sprite_id(*cell) for cell in cells], dtype=np.int32)
        chosen = sprites[(pick[mask] * len(sprites)).astype(int)]
        flip = turn[mask] < 0.5
        for layer, brighten in (("light", (1.0, 1.55)), ("dark", (1.0, 1.4))):
            shade = (brighten[0] + tone[mask] * (brighten[1] - brighten[0]))[:, None]
            landscape[layer]["sprite"][mask] = chosen
            landscape[layer]["flip"][mask] = flip
            landscape[layer]["fg"][mask] = np.clip(landscape[layer]["fg"][mask].astype(float) * shade, 0, 255).astype(np.uint8)


SNOW_FROM, SNOW_SPAN = 1.0, 0.45
"""Rock above this elevation (reached only by the high crests) turns white over the next `SNOW_SPAN`."""
SNOW_COLOR, ASH_COLOR = (228, 236, 246), (70, 52, 50)
STONE_COLOR, STONE_FROM_GROUND = (128, 120, 110), 0.22
"""Bare rock is grey-brown stone with this share of the colour of the ground around it."""


def _tint_rock(landscape: np.ndarray, env: dict, rock: np.ndarray, ground: np.ndarray) -> None:
    """Mountain colour by height: bare grey-brown at the foot, snow and ice on the crests, dark ash and lava rock in
    volcanic country (where it is too hot for snow). Only the colours change; the tiles stay ordinary walls."""
    volcanic = (env["landmark"] == landmarks.LANDMARK_INDEX["volcanic_mountains"]) * env["landmark_strength"]
    snow = relief.smooth((env["elevation"] - SNOW_FROM) / SNOW_SPAN) * (1.0 - np.clip(volcanic * 1.5, 0.0, 1.0))
    ash = np.clip(volcanic * 1.2, 0.0, 0.85)
    for layer, scale in (("light", 1.0), ("dark", 0.5)):
        fg = np.array(STONE_COLOR, dtype=float) * scale * (1.0 - STONE_FROM_GROUND) + ground.astype(float) * scale * STONE_FROM_GROUND
        fg = fg * (1.0 - ash[..., None]) + np.array(ASH_COLOR, dtype=float) * scale * ash[..., None]
        fg = fg * (1.0 - snow[..., None]) + np.array(SNOW_COLOR, dtype=float) * scale * snow[..., None]
        landscape[layer]["fg"][..., :3][rock] = np.clip(fg[rock], 0, 255).astype(np.uint8)


CHASM_SCALE, CHASM_WIDTH, CHASM_FROM = 0.05, 0.03, 0.95
"""Chasms: thin winding rifts (where a noise crosses zero) cut into the high rock above `CHASM_FROM`."""


def _cut_chasms(noise: TerrainNoise, landscape: np.ndarray, env: dict, rock: np.ndarray, x0: int, y0: int, width: int, height: int) -> None:
    """Turn rifts in the high mountain rock into open air (no floor: you look down into the cave layer; nothing walks there)."""
    rift = np.abs(noise.sample(9, CHASM_SCALE, x0, y0, width, height)) < CHASM_WIDTH
    chasm = rock & rift & (env["elevation"] > CHASM_FROM)
    landscape[chasm] = tile_types.open_air.get_array()


def generate_terrain(noise: TerrainNoise, x0: int, y0: int, width: int, height: int) -> Tuple[np.ndarray, np.ndarray]:
    """Tiles and tree map for a world rectangle, generated on a padded region. Uses the global RNGs (wrap it in
    `seeded_rng`). Returns `(tiles, tree_map)` for the unpadded rectangle."""
    from procgen import replace_variations
    m = MARGIN
    pw, ph = width + 2 * m, height + 2 * m
    kinds = base_terrain(noise, x0 - m, y0 - m, pw, ph)
    landscape = np.full((pw, ph), fill_value=tile_types.wall.get_array(), dtype=tile_types.tile_dt, order="F")
    landscape[kinds == 0] = tile_types.water.get_array()
    landscape[kinds == 1] = tile_types.floor.get_array()
    landscape = replace_variations(tile_types.water, landscape, pw, ph)
    landscape = replace_variations(tile_types.wall, landscape, pw, ph)
    shallow_colors, deep_colors = _shape_liquid(noise, landscape, kinds == 0, x0 - m, y0 - m, pw, ph)
    hot = hydrology.hot_spring_mask(noise, x0 - m, y0 - m, pw, ph) & (kinds == 0)
    landscape["liquid"][hot] = 4      # liquids.LiquidKind.HOT
    fall = hydrology.waterfall_mask(noise, x0 - m, y0 - m, pw, ph) & (kinds == 0) & ~hot
    landscape["depth"][fall], landscape["walkable"][fall] = 3, False        # a waterfall is deep, foaming water
    lava = hydrology.lava_mask(noise, x0 - m, y0 - m, pw, ph) & (kinds == 0)
    landscape["liquid"][lava], landscape["depth"][lava], landscape["walkable"][lava] = 5, 3, False   # LiquidKind.LAVA: a lake, never waded

    # Climate: the biome tints the open ground and decides how thickly it is vegetated.
    import biomes
    env = environment_for(noise, x0 - m, y0 - m, pw, ph, kinds)
    ground = landmarks.blend_ground(biomes.ground_colors(env["biome"]), env["landmark"], env["landmark_strength"])
    open_ground = kinds == 1
    _tint_rock(landscape, env, kinds == 2, ground)
    _cut_chasms(noise, landscape, env, kinds == 2, x0 - m, y0 - m, pw, ph)
    landscape["light"]["fg"][open_ground] = (ground[open_ground] * 0.8).astype(np.uint8)
    landscape["light"]["bg"][open_ground] = (ground[open_ground] * 0.10).astype(np.uint8)
    landscape["dark"]["fg"][open_ground] = (ground[open_ground] * 0.4).astype(np.uint8)
    density = landmarks.blend_density(np.array([biomes.BIOMES[k].vegetation for k in biomes.BIOME_IDS])[env["biome"]],
                                      env["landmark"], env["landmark_strength"])

    # Vegetation: wherever the vegetation noise beats a random threshold (not in lakes); the threshold follows
    # the biome (barren desert ... dense jungle).
    random_map = noise.scatter(7, x0 - m, y0 - m, pw, ph)   # a coordinate hash, so chunk borders show no seam
    # (The biome sets the base; the woodland noise raises it into stands and clearings. The earlier `0.1 + (1 - density) * 0.45`
    # left grass, steppe and scrub at under 1% cover, against the 4.7% everywhere of the original generator.)
    stands = noise.woodland(x0 - m, y0 - m, pw, ph)
    threshold = BASE_THRESHOLD + (1.0 - density) * 0.4 - stands * WOODLAND_REACH
    tree_map = (noise.vegetation(x0 - m, y0 - m, pw, ph) > random_map + threshold) & (kinds != 0)
    # (the ground under vegetation stays ordinary biome ground: plants are drawn on top of it)
    area = (x0 - m, y0 - m, pw, ph)
    _blend_shores(noise, area, landscape, kinds == 0, ground, open_ground, shallow_colors, deep_colors)
    for layer, scale in (("light", 1.0), ("dark", 0.5)):     # hot springs are a paler, greener blue; lava glows orange
        landscape[layer]["fg"][hot] = (np.array(HOT_COLOR, dtype=float) * scale).astype(np.uint8)
        landscape[layer]["fg"][fall & ~lava] = (np.array(FOAM_COLOR, dtype=float) * scale).astype(np.uint8)
        landscape[layer]["fg"][lava] = (np.array(LAVA_COLOR, dtype=float) * scale).astype(np.uint8)
    # (ground cover never goes under a tree: a tree and a tuft of grass would share a tile)
    _cover_ground(noise, area, landscape, env, open_ground & ~tree_map, density)
    deck, banks = hydrology.bridge_tiles(noise, x0 - m, y0 - m, pw, ph)
    deck, banks = deck & (kinds == 0) & ~hot & ~fall & ~lava, banks & (kinds == 1) & ~landscape["open"]
    tile_types.lay_bridge(landscape, deck, (kinds == 1) & ~deck)     # the odd natural bridge over a narrow river
    landscape[banks] = tile_types.path.get_array()
    tree_map &= ~landscape["open"] & ~deck & ~banks        # nothing grows over a chasm, a bridge or its path
    interior = (slice(m, m + width), slice(m, m + height))
    return np.asfortranarray(landscape[interior]), np.asfortranarray(tree_map[interior])


class NoiseWorldSource:
    """Chunk source of a generated floor (see module docstring). Also owns the floor's procedural species and
    the start position and staircase, which live in chunk (0, 0)."""

    bounds = None

    def __init__(self, floor_seed: int, floor: int = 1, species: Optional[Tuple[PlantSpecies, PlantSpecies]] = None,
                 planet=None, culture: str = "human"):
        """`planet` (a `planet.Planet`) supplies the ecosystem; by default one is generated from the seed for `culture`.
        Passing `species` (a tree and a shrub) selects the old single-species mode, kept for tests of the generator."""
        self.floor_seed = floor_seed
        self.floor = floor
        self.noise = TerrainNoise(floor_seed)
        self.legacy = species is not None
        if species is not None:
            self.tree_species, self.shrub_species = species
            self.planet = None
        else:
            from planet import generate_planet
            self.planet = planet or generate_planet(floor_seed, culture)
            self.tree_species = self.shrub_species = None

    @property
    def spawn_point(self) -> Tuple[int, int]:
        """Where the player starts: a free tile near the middle of chunk (0, 0)."""
        return shafts.start_point(self.floor_seed)[0]

    @property
    def stairs(self) -> Optional[Tuple[int, int]]:
        """The cave entrance of the start chunk (a staircase down), if it has one."""
        return shafts.entrance_of(self.floor_seed)

    def __getstate__(self):  # tcod noise objects are rebuilt from the seed
        state = self.__dict__.copy()
        del state["noise"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.noise = TerrainNoise(self.floor_seed)

    def definitions(self) -> List:
        """Procedural definitions shared by this floor's entities (saved once, referenced from chunk files)."""
        if self.planet is not None:
            return self.planet.definitions()
        found = [self.tree_species, self.shrub_species]
        found += [s.fruit for s in (self.tree_species, self.shrub_species) if s.fruit is not None]
        return found

    def chunk_seed(self, key: ChunkKey) -> int:
        return mix_seed(self.floor_seed, key[0], key[1])

    # ── ChunkSource protocol ───────────────────────────────────────────────────────
    def can_load(self, key: ChunkKey) -> bool:
        return True

    def mask(self, key: ChunkKey):
        return True

    def terrain(self, key: ChunkKey) -> np.ndarray:
        """The chunk's tiles as generated (a copy; pure, nothing is loaded): used to look down onto this layer."""
        return shafts.surface_layer(self.floor_seed, key)[0]

    def generate(self, world: World, key: ChunkKey) -> Chunk:
        tiles, tree_map = shafts.surface_layer(self.floor_seed, key)
        chunk = Chunk(key, tiles)
        chunk.pending_trees = tree_map  # consumed by populate()
        if key == (0, 0):
            world.downstairs_location = self.stairs
        return chunk

    def populate(self, world: World, chunk: Chunk) -> None:
        import components.plant
        from procgen import place_entities
        tree_map = chunk.__dict__.pop("pending_trees")
        import structures
        now = world.engine.game_world.current_time if getattr(world.engine, "game_world", None) else 0
        before = set(chunk.entities)
        with seeded_rng(mix_seed(self.chunk_seed(chunk.key), 1)):
            reserved = {self.spawn_point} if chunk.key == (0, 0) else set()
            if not self.legacy:
                import settlements
                reserved |= {(chunk.x0 + lx, chunk.y0 + ly) for lx, ly in settlements.built(self.floor_seed, chunk.key)}   # nothing wild on built ground
            if self.legacy:
                for lx, ly in np.argwhere(tree_map).tolist():
                    if random.random() > 0.2:
                        plant = components.plant.Tree(self.tree_species)
                    else:
                        plant = components.plant.Shrub(self.shrub_species)
                    plant.growth = random.randrange(int(plant.avg_cycle) + 1)  # staggered, so the forest does not fruit in unison
                    world.add_entity(plant, chunk.x0 + lx, chunk.y0 + ly)
                place_entities(world, self.floor, area=(chunk.x0, chunk.y0, CHUNK_W, CHUNK_H), reserved=reserved)
            else:
                env = shafts.environment(self.floor_seed, chunk.key)
                self._grow_flora(world, chunk, tree_map, env)
                self._scatter_stones(world, chunk, env, reserved)
                import scenery
                scenery.populate(self, world, chunk, env, reserved, ruin_chunk=chunk.key in structures.ruin_chunks(self.floor_seed))
                self._spawn_fauna(world, chunk, env, reserved)
                self._place_sites(world, chunk)
                settlements.populate(world, chunk, self.floor_seed, self.planet)
                self._scatter_flowers(world, chunk, env, reserved)
                self._scatter_lily_pads(world, chunk)
        for entity in chunk.entities:
            if entity not in before:
                entity.last_upkeep = now


def _grow_flora(self, world: "World", chunk: Chunk, tree_map: np.ndarray, env: dict) -> None:
    """Plant each root tile with a species whose habitat suits the tile (weighted by suitability and rarity)."""
    import components.plant
    pool, weights = self.planet.species_weights(env)
    if not pool:
        return
    for lx, ly in np.argwhere(tree_map).tolist():
        column = weights[:, lx, ly]
        if column.sum() <= 0:
            continue
        species = random.choices(pool, weights=column.tolist())[0]
        plant = components.plant.Tree(species) if species.category is PlantCategory.TREE else components.plant.Shrub(species)
        plant.growth = random.randrange(int(plant.avg_cycle) + 1)  # staggered, so the forest does not fruit in unison
        world.add_entity(plant, chunk.x0 + lx, chunk.y0 + ly)


FLOWERS_PER_CHUNK = (25, 60)
"""Flowers placed on a chunk's open ground (min, max attempts; each needs a free tile a flower species can live on)."""
FLOWER_UNDER_TREE = 0.12
"""Chance that a flower attempt picks the foot of a tree instead of open ground."""
LILY_PADS_PER_100_WATER_TILES = 1.2
"""Lily pads on the water of a chunk: very sparse."""


def _scatter_flowers(self, world: "World", chunk: Chunk, env: dict, reserved) -> None:
    """Flowers on free open ground, each a species whose habitat suits the tile."""
    import components.plant
    pool, weights = self.planet.species_weights(env, PlantCategory.FLOWER)   # one pass over the whole chunk
    if not pool:
        return
    trees = [(e.x, e.y) for e in chunk.entities if e.category is EntityCategory.PLANT and e.blocks_movement]
    for _ in range(random.randint(*FLOWERS_PER_CHUNK)):
        if trees and random.random() < FLOWER_UNDER_TREE:
            # (a flower may grow at the foot of a tree: the one pairing of foliage that may share a tile)
            x, y = random.choice(trees)
            there = world.get_entities_at_location(x, y)
            if len(there) == 1 and (x, y) not in reserved:
                lx, ly = x - chunk.x0, y - chunk.y0
                column = weights[:, lx, ly]
                if column.sum() > 0:
                    plant = components.plant.Flower(random.choices(pool, weights=column.tolist())[0])
                    plant.growth = random.randrange(int(plant.avg_cycle) + 1)
                    world.add_entity(plant, x, y)
            continue
        lx, ly = random.randrange(CHUNK_W), random.randrange(CHUNK_H)
        x, y = chunk.x0 + lx, chunk.y0 + ly
        if (x, y) in reserved or not world.is_walkable(x, y) or world.is_blocked(x, y) or world.tile_at(x, y)["liquid"]:
            continue
        if world.get_entities_at_location(x, y):
            continue
        column = weights[:, lx, ly]
        if column.sum() <= 0:
            continue
        plant = components.plant.Flower(random.choices(pool, weights=column.tolist())[0])
        plant.growth = random.randrange(int(plant.avg_cycle) + 1)
        world.add_entity(plant, x, y)


def _scatter_lily_pads(self, world: "World", chunk: Chunk) -> None:
    """A few lily pads floating on the shallow and middling water."""
    import decals
    liquid = chunk.tiles["liquid"] > 0
    count = int(liquid.sum() * LILY_PADS_PER_100_WATER_TILES / 100 + random.random())
    spots = np.argwhere(liquid & (chunk.tiles["depth"] <= 2))
    for _ in range(min(count, len(spots))):
        lx, ly = spots[random.randrange(len(spots))].tolist()
        x, y = chunk.x0 + lx, chunk.y0 + ly
        if world.get_entities_at_location(x, y):
            continue
        pad = decals.LilyPad(tuple(max(0, min(255, c + random.randint(-18, 18))) for c in (70, 150, 70)))
        pad.variant = random.randrange(8)
        world.add_entity(pad, x, y)


FAUNA_PER_CHUNK = 9
SELENITE_EXILE_CHANCE = 0.04
ROBOT_CHANCE = 0.02
"""Chance per animal spawn that a (hostile) machine stands there instead."""
"""Chance per animal spawn that an exiled Selenite stands there instead (the old demo enemy, kept as a rare hostile)."""


def _spawn_fauna(self, world: "World", chunk: Chunk, env: dict, reserved) -> None:
    """Place up to `FAUNA_PER_CHUNK` animals at random tiles, each a species that can live at that tile."""
    import components.unit as units
    from components.unit import Unit
    import wildlife
    pool, _ = self.planet.fauna_weights({k: v[0:1, 0:1] for k, v in env.items()})
    placed = 0
    for _ in range(random.randint(0, FAUNA_PER_CHUNK)):
        lx, ly = random.randrange(CHUNK_W), random.randrange(CHUNK_H)
        x, y = chunk.x0 + lx, chunk.y0 + ly
        if (x, y) in reserved or not world.is_walkable(x, y) or world.is_blocked(x, y) or world.tile_at(x, y)["liquid"]:
            continue
        if random.random() < SELENITE_EXILE_CHANCE:
            world.add_entity(units.Selenite(), x, y)
            continue
        if random.random() < ROBOT_CHANCE:
            world.add_entity(units.Robot(), x, y)
            continue
        point = {k: v[lx:lx + 1, ly:ly + 1] for k, v in env.items()}
        _, weights = self.planet.fauna_weights(point)
        column = weights[:, 0, 0]
        if column.sum() <= 0:
            continue
        world.add_entity(Unit(random.choices(pool, weights=column.tolist())[0]), x, y)
        placed += 1
    if self.floor == 1:
        wildlife.note(world, chunk, placed)


STONES_PER_CHUNK = (3, 7)
"""Loose stones lying about on the surface of a chunk (min, max): the first tools are made of them."""


def _scatter_stones(self, world: "World", chunk: Chunk, env: dict, reserved) -> None:
    """Lay a few loose stones (of the kinds this biome has, plus flint) on free ground."""
    import biomes
    import resources
    import species as defs
    from items import Stuff
    for _ in range(random.randint(*STONES_PER_CHUNK)):
        lx, ly = random.randrange(CHUNK_W), random.randrange(CHUNK_H)
        x, y = chunk.x0 + lx, chunk.y0 + ly
        if (x, y) in reserved or not world.is_walkable(x, y) or world.is_blocked(x, y) or world.tile_at(x, y)["liquid"]:
            continue
        if any(e.category is EntityCategory.PLANT for e in world.get_entities_at_location(x, y)):
            continue                                  # (a loose stone under a bush could not be seen)
        biome = biomes.BIOME_IDS[int(env["biome"][lx, ly])]
        stone_landmark = landmarks.key_of(int(env["landmark"][lx, ly])) if env["landmark_strength"][lx, ly] > 0.3 else ""
        material = resources.surface_stone(self.planet, self.floor_seed, x, y, random.getrandbits(16), biome, stone_landmark)
        world.add_entity(Stuff(defs.PIECE_STONE, material), x, y)


def _place_sites(self, world: "World", chunk: Chunk) -> None:
    """The crash site around the spawn (chunk (0, 0)) and the precursor ruins and gate in their chunks (surface only)."""
    import structures
    game_world = getattr(world.engine, "game_world", None)
    run = getattr(game_world, "run", None)
    if self.floor != 1:
        return
    if chunk.key == (0, 0):
        placed = structures.place_crash_site(world, self.spawn_point, self.floor_seed)
        if run is not None:
            run.wreck, run.pod = placed.get("ship"), placed.get("pod")
    site = structures.ruin_chunks(self.floor_seed).get(chunk.key)
    if site is not None:
        at = structures.place_ruin(world, chunk, self.floor_seed, site)
        if run is not None:
            run.flags.setdefault("sites", {})[site] = at


NoiseWorldSource._place_sites = _place_sites
NoiseWorldSource._scatter_stones = _scatter_stones
NoiseWorldSource._grow_flora = _grow_flora
NoiseWorldSource._scatter_flowers = _scatter_flowers
NoiseWorldSource._scatter_lily_pads = _scatter_lily_pads
NoiseWorldSource._spawn_fauna = _spawn_fauna


class FlatWorldSource:
    """An unbounded world of open floor and nothing else: a clean stage for tests and benchmarks (walking across
    borders, NEAR-ring populations). Same protocol as `NoiseWorldSource`."""

    bounds = None

    def __init__(self, floor_seed: int = 0, floor: int = 1, spawn_point: Tuple[int, int] = (35, 20)):
        self.floor_seed = floor_seed
        self.floor = floor
        self.spawn_point = spawn_point
        self.stairs: Optional[Tuple[int, int]] = None

    def definitions(self) -> List:
        return []

    def can_load(self, key: ChunkKey) -> bool:
        return True

    def mask(self, key: ChunkKey):
        return True

    def terrain(self, key: ChunkKey) -> np.ndarray:
        return np.full((CHUNK_W, CHUNK_H), fill_value=tile_types.floor.get_array(), dtype=tile_types.tile_dt, order="F")

    def generate(self, world: World, key: ChunkKey) -> Chunk:
        return Chunk(key, self.terrain(key))

    def populate(self, world: World, chunk: Chunk) -> None:
        pass


class CaveSource:
    """A cave layer (z < 0): noise caves, Selenites rather than rabbits, no sky. Stairs come from `shafts`."""

    bounds = None

    def __init__(self, master_seed: int, z: int):
        self.master_seed = master_seed
        self.z = z
        self.floor = 1 - z
        self.floor_seed = mix_seed(master_seed, z)
        self.spawn_point = None
        self.stairs = None

    def definitions(self) -> List:
        return []

    def can_load(self, key: ChunkKey) -> bool:
        return True

    def mask(self, key: ChunkKey):
        return True

    def terrain(self, key: ChunkKey) -> np.ndarray:
        return shafts.cave_layer(self.master_seed, self.z, key)

    def generate(self, world: World, key: ChunkKey) -> Chunk:
        return Chunk(key, self.terrain(key).copy())

    def populate(self, world: World, chunk: Chunk) -> None:
        import underground
        game_world = getattr(world.engine, "game_world", None)
        now = game_world.current_time if game_world else 0
        before = set(chunk.entities)
        with seeded_rng(mix_seed(self.floor_seed, chunk.key[0], chunk.key[1], 1)):
            underground.populate(world, chunk, self.floor, self.master_seed, self.z, getattr(game_world, "planet", None))
        for entity in chunk.entities:
            if entity not in before:
                entity.last_upkeep = now


class SkySource:
    """An upper layer (z > 0): open air, with the upper floors of the buildings below it."""

    bounds = None

    def __init__(self, master_seed: int, z: int):
        self.master_seed = master_seed
        self.z = z
        self.floor = max(1, 1 - z)
        self.floor_seed = mix_seed(master_seed, z)
        self.spawn_point = None
        self.stairs = None

    def definitions(self) -> List:
        return []

    def can_load(self, key: ChunkKey) -> bool:
        return True

    def mask(self, key: ChunkKey):
        return True

    def terrain(self, key: ChunkKey) -> np.ndarray:
        return shafts.sky_layer(self.master_seed, self.z, key)

    def generate(self, world: World, key: ChunkKey) -> Chunk:
        return Chunk(key, self.terrain(key).copy())

    def populate(self, world: World, chunk: Chunk) -> None:
        pass
