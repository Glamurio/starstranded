"""Underground biomes: the caves are not one grey maze but regions with their own look and their own animals.

Like the surface, a cave layer's biome is a pure function of the seed, the layer and the position (`field`), so a chunk draws
the same regions as its neighbours. Each biome (`UBIOMES`) is data: floor and wall colours, the little things growing or lying on
the floor (`cover`), the animals that live there (keys of `planet.CAVE_FAUNA`, with weights), and the soundtrack pool. The `ruins`
biome is the one under a precursor ruin of the surface (an oval of it); every other region is a region of the surface above (`regions`: large, with blended borders), which has the underground biome of its surface biome with a chance (`SURFACE_INFLUENCE`:
likely in the first layer, less with depth, so the deep caves drift away from the country over them) and otherwise a biome of its own, drawn from the region's number. Selenites and robots are rare visitors everywhere, commoner in the ruins."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Tuple

import numpy as np  # type: ignore

import spriteconfig
from atlas import sprite_id
from chunks import CHUNK_H, CHUNK_W, ChunkKey, chunk_origin

RGB = Tuple[int, int, int]
Cell = Tuple[int, int]


@dataclass(frozen=True)
class UBiome:
    key: str
    name: str
    description: str
    floor: RGB                         # colour of the floor sprite
    floor_bg: RGB                      # ... and of what lies behind it
    wall: RGB                          # colour of the walls
    cover: Tuple[Cell, ...] = ()       # sprites scattered over the floor
    cover_chance: float = 0.0
    fauna: Tuple[Tuple[str, float], ...] = ()      # (`planet.CAVE_FAUNA` key, weight)
    centre: Tuple[float, float] = (0.0, 0.0)       # where it sits in the (warm, wet) plane of the noise fields
    reach: float = 1.0                 # how far it extends: larger = more of the cave (distance to its centre is divided by this)
    music: str = ""


UBIOMES: Dict[str, UBiome] = {}
UBIOME_IDS = []


def _biome(*args, **kwargs) -> UBiome:
    biome = UBiome(*args, **kwargs)
    object.__setattr__(biome, "cover", tuple(spriteconfig.get(f"cave.{biome.key}.cover.{i}", cell) for i, cell in enumerate(biome.cover)))
    UBIOMES[biome.key] = biome
    UBIOME_IDS.append(biome.key)
    return biome


_biome("barren", "Barren cave", "Bare grey rock and dust; little lives here.", (110, 100, 120), (6, 6, 9), (128, 120, 110),
       cover=((3, 9), (4, 9)), cover_chance=0.03, fauna=(("cave_beetle", 3), ("cave_bat", 2), ("cave_worm", 1)), centre=(0.0, 0.0), reach=1.0)
_biome("volcanic", "Volcanic cave", "Black rock stained red, warm air and the smell of sulphur.", (150, 70, 50), (22, 6, 4), (74, 52, 50),
       cover=((3, 9),), cover_chance=0.04, fauna=(("cave_crab", 2), ("cave_bat", 2), ("cave_worm", 2)), centre=(0.55, -0.35))
_biome("ice", "Ice cave", "Pale blue ice on every wall, and cold that stings.", (150, 190, 225), (6, 10, 18), (170, 205, 235),
       cover=(), cover_chance=0.0, fauna=(("cave_bat", 3), ("cave_crab", 1), ("cave_moth", 1)), centre=(-0.55, -0.35))
_biome("crystal", "Crystal cave", "Violet crystal grows from the rock and throws back every light.", (160, 130, 215), (10, 6, 20), (130, 110, 190),
       cover=((16, 9), (0, 10)), cover_chance=0.08, fauna=(("cave_crab", 3), ("cave_moth", 2), ("cave_beetle", 1)), centre=(0.0, -0.6))
_biome("fungal", "Fungal cave", "Damp, soft ground under pale mushrooms; spores hang in the air.", (170, 110, 175), (14, 6, 16), (96, 84, 108),
       cover=((2, 10), (3, 10), (105, 0)), cover_chance=0.14, fauna=(("cave_slug", 3), ("cave_moth", 3), ("cave_beetle", 2)), centre=(-0.35, 0.5))
_biome("wet", "Flooded cave", "Dripping rock and standing water; the floor is slick.", (70, 150, 160), (4, 12, 16), (84, 108, 118),
       cover=((4, 9), (5, 9)), cover_chance=0.07, fauna=(("cave_slug", 3), ("cave_worm", 2), ("cave_crab", 1)), centre=(0.35, 0.5))
_biome("salt", "Salt cave", "Crusted white rock where old brine dried to crystals.", (225, 225, 215), (14, 14, 14), (190, 185, 170),
       cover=((14, 6), (5, 26)), cover_chance=0.05, fauna=(("cave_crab", 3), ("cave_beetle", 2), ("cave_moth", 1)), centre=(0.75, -0.7), reach=0.9)
_biome("rootbound", "Rootbound cave", "Pale roots push through the ceiling and knot across the floor.", (120, 95, 65), (10, 7, 4), (100, 80, 60),
       cover=((23, 9), (24, 9), (4, 10)), cover_chance=0.09, fauna=(("cave_beetle", 3), ("cave_slug", 2), ("cave_worm", 1)), centre=(-0.75, 0.1), reach=0.9)
_biome("mycelial", "Mycelial cave", "White threads cover every surface; the floor gives like a mattress.", (210, 200, 225), (12, 10, 16), (150, 140, 165),
       cover=((2, 10), (3, 10), (105, 0)), cover_chance=0.16, fauna=(("cave_moth", 3), ("cave_slug", 3), ("cave_beetle", 1)), centre=(-0.5, 0.85), reach=0.9)
_biome("bone_vault", "Bone vault", "Bones of things that crawled in to die lie in drifts.", (200, 190, 170), (10, 9, 8), (140, 130, 115),
       cover=((5, 27), (7, 26)), cover_chance=0.07, fauna=(("cave_bat", 3), ("cave_worm", 2), ("cave_crab", 1)), centre=(0.2, 0.25), reach=0.8)
_biome("warren", "Warren", "Fleshy tunnels that are warm to the touch and faintly pulse.", (180, 90, 100), (18, 6, 8), (130, 60, 75),
       cover=((23, 8), (24, 8)), cover_chance=0.1, fauna=(("cave_worm", 3), ("cave_slug", 2), ("cave_bat", 1)), centre=(0.7, 0.85), reach=0.9)
_biome("infrastructure", "Service tunnels", "Square-cut tunnels, pipes and old cable runs under a dead city.", (140, 150, 160), (8, 10, 12), (95, 105, 115),
       cover=((57, 3), (76, 7)), cover_chance=0.03, fauna=(("cave_beetle", 2), ("cave_bat", 2), ("cave_moth", 1)), centre=(-0.85, -0.85), reach=0.9)
_biome("ruins", "Precursor ruins", "Worked stone, long straight edges and old cold light.", (150, 175, 160), (8, 12, 10), (120, 150, 140),
       cover=(), cover_chance=0.0, fauna=(("cave_beetle", 1),), centre=(9.0, 9.0), reach=1.0)

UBIOME_INDEX: Dict[str, int] = {key: i for i, key in enumerate(UBIOME_IDS)}
RUINS = UBIOME_INDEX["ruins"]

# Chance per spawn that a Selenite / a robot is the creature (instead of a cave animal); the ruins are theirs.
VISITORS = {"default": (0.06, 0.02), "ruins": (0.25, 0.30), "infrastructure": (0.04, 0.12)}
SURFACE_INFLUENCE = {-1: 0.85, -2: 0.6, -3: 0.35}
"""The chance that a cave region follows the surface above it (layers deeper than these: `DEEP_INFLUENCE`); otherwise it takes a biome of its own."""
DEEP_INFLUENCE = 0.12
OWN_WEIGHT = {"barren": 0.5}
"""How often each biome is the one a cave region takes of its own (1 unless listed): bare caves are kept to a minority."""


@lru_cache(maxsize=1)
def _surface_to_under() -> np.ndarray:
    """For each surface biome index the underground biome index that lies below it."""
    import biomes
    return np.array([UBIOME_INDEX[biomes.BIOMES[k].under_key] for k in biomes.BIOME_IDS], dtype=np.int8)


@lru_cache(maxsize=256)
def _surface_above(master: int, key: ChunkKey, margin: int):
    """The surface regions (`regions.Field`) over every tile of a chunk and its margin: the caves use the same regions as the country above."""
    import regions
    import shafts
    x0, y0 = chunk_origin(key)
    return regions.field(shafts.terrain_noise(master), x0 - margin, y0 - margin, CHUNK_W + 2 * margin, CHUNK_H + 2 * margin)


def _of_region(master: int, z: int, region: int, surface_biome: int) -> int:
    """The underground biome of one region of layer z: the one under its surface biome (more likely near the surface), else one of its own."""
    import random
    from seeds import mix_seed
    rng = random.Random(mix_seed(master, z, region, 7201))
    if rng.random() < SURFACE_INFLUENCE.get(z, DEEP_INFLUENCE):
        return int(_surface_to_under()[surface_biome])
    keys = [k for k in UBIOME_IDS if k != "ruins"]
    return UBIOME_INDEX[rng.choices(keys, weights=[OWN_WEIGHT.get(k, 1.0) for k in keys])[0]]


def clear_caches() -> None:
    _surface_above.cache_clear()


def blended(master: int, z: int, key: ChunkKey, margin: int = 0):
    """`(biome, other, edge)` of every tile of chunk `key` (plus `margin`): the cave biome of the tile's region, that of the neighbouring
    region and the neighbour's share (0 deep inside a region .. 0.5 on its border), so caves change gradually like the country does."""
    from structures import ruin_chunks
    above = _surface_above(master, key, margin)
    biome = np.zeros(above.biome.shape, dtype=np.int8)
    other = np.zeros(above.biome.shape, dtype=np.int8)
    for region in np.unique(np.concatenate([above.region.ravel(), above.other_region.ravel()])):
        for ids, out in ((above.region, biome), (above.other_region, other)):
            here = ids == region
            if here.any():
                surface = (above.biome if out is biome else above.other)[here][0]
                out[here] = _of_region(master, z, int(region), int(surface))
    edge = np.where(biome == other, 0.0, above.edge)
    width, height = biome.shape
    if key in ruin_chunks(master):                    # an oval of ruins under the surface ruin
        xs = (np.arange(width)[:, None] - margin - CHUNK_W / 2 + 0.5) / (CHUNK_W * 0.46)
        ys = (np.arange(height)[None, :] - margin - CHUNK_H / 2 + 0.5) / (CHUNK_H * 0.46)
        oval = xs * xs + ys * ys < 1.0
        biome[oval], edge[oval] = RUINS, 0.0
    return biome, other, edge


def field(master: int, z: int, key: ChunkKey, margin: int = 0) -> np.ndarray:
    """Biome index of every tile of chunk `key` (plus `margin` tiles around it), shape `(CHUNK_W + 2m, CHUNK_H + 2m)`."""
    return blended(master, z, key, margin)[0]


def paint(landscape: np.ndarray, biome: np.ndarray, floor: np.ndarray, wall: np.ndarray, rng: np.random.Generator,
          other: np.ndarray = None, edge: np.ndarray = None) -> None:
    """Colour the tiles of a chunk by their biome (`floor` / `wall` are masks) and scatter each biome's cover over its floor. Where a region
    meets another (`other`, `edge` its share) the colours run into each other and the cover comes from either."""
    if other is None:
        other, edge = biome, np.zeros(biome.shape)
    share = edge[..., None]
    for layer, dim in (("light", 1.0), ("dark", 0.42)):
        wall_dim = dim if layer == "light" else 0.4
        for part, dims, mask in (("floor", dim, floor), ("floor_bg", dim, floor), ("wall", wall_dim, wall)):
            if part == "floor_bg" and layer != "light":
                landscape[layer]["bg"][floor] = (0, 0, 0)
                continue
            colours = np.array([getattr(UBIOMES[k], part) for k in UBIOME_IDS], dtype=float) * dims
            mixed = colours[biome] * (1.0 - share) + colours[other] * share
            target = "bg" if part == "floor_bg" else "fg"
            landscape[layer][target][mask] = mixed[mask].astype(np.uint8)
    pick = np.where(rng.random(biome.shape) < edge, other, biome)          # the biome whose cover a tile may carry
    for key, i in UBIOME_INDEX.items():
        b = UBIOMES[key]
        if not (b.cover and b.cover_chance):
            continue
        covered = floor & (pick == i) & (rng.random(biome.shape) < b.cover_chance)
        if not covered.any():
            continue
        sprites = np.array([sprite_id(*cell) for cell in b.cover], dtype=np.int32)
        chosen = sprites[(rng.random(biome.shape) * len(sprites)).astype(int)[covered]]
        flip = rng.random(biome.shape)[covered] < 0.5
        tint = b.floor
        for layer, dim in (("light", 1.0), ("dark", 0.42)):
            landscape[layer]["sprite"][covered] = chosen
            landscape[layer]["flip"][covered] = flip
            landscape[layer]["fg"][covered] = tuple(min(255, int(c * dim * 1.25)) if dim == 1.0 else int(c * dim) for c in tint)


def biome_at(master: int, z: int, x: int, y: int) -> str:
    """The key of the underground biome at world tile (x, y) of layer z."""
    from chunks import chunk_key
    key = chunk_key(x, y)
    return UBIOME_IDS[int(field(master, z, key)[x - key[0] * CHUNK_W, y - key[1] * CHUNK_H])]


def populate(world, chunk, floor: int, master: int, z: int, planet) -> None:
    """Place the creatures of a cave chunk (call inside `worldgen.seeded_rng`): the animals of each tile's biome, with now and then a
    Selenite or a robot. The count follows `procgen.max_monsters_by_floor`."""
    import random
    import components.unit as units
    from components.unit import Unit
    from procgen import get_max_value_for_floor, max_monsters_by_floor
    biome = field(master, z, chunk.key)
    for _ in range(random.randint(0, get_max_value_for_floor(max_monsters_by_floor, floor))):
        lx, ly = random.randrange(CHUNK_W), random.randrange(CHUNK_H)
        x, y = chunk.x0 + lx, chunk.y0 + ly
        if not world.is_walkable(x, y) or world.is_blocked(x, y) or world.tile_at(x, y)["liquid"]:
            continue
        key = UBIOME_IDS[int(biome[lx, ly])]
        selenite, robot = VISITORS.get(key, VISITORS["default"])
        roll = random.random()
        if roll < selenite:
            world.add_entity(units.Selenite(), x, y)
        elif roll < selenite + robot:
            world.add_entity(units.Robot(), x, y)
        else:
            species, weights = planet.cave_fauna(key) if planet is not None else ([], [])
            if species:
                world.add_entity(Unit(random.choices(species, weights=weights)[0]), x, y)
