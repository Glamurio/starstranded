"""Underground biomes: the caves are not one grey maze but regions with their own look and their own animals.

Like the surface, a cave layer's biome is a pure function of the seed, the layer and the position (`field`), so a chunk draws
the same regions as its neighbours. Each biome (`UBIOMES`) is data: floor and wall colours, the little things growing or lying on
the floor (`cover`), the animals that live there (keys of `planet.CAVE_FAUNA`, with weights), and the soundtrack pool. The `ruins`
biome is the one under a precursor ruin of the surface (an oval of it); every other region comes from two low-frequency noise fields (warm/cold and
dry/wet) matched to the nearest biome in that plane. Selenites and robots are rare visitors everywhere, commoner in the ruins."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Tuple

import numpy as np  # type: ignore

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
    UBIOMES[biome.key] = biome
    UBIOME_IDS.append(biome.key)
    return biome


_biome("barren", "Barren cave", "Bare grey rock and dust; little lives here.", (110, 100, 120), (6, 6, 9), (128, 120, 110),
       cover=((3, 9), (4, 9)), cover_chance=0.03, fauna=(("cave_beetle", 3), ("cave_bat", 2), ("cave_worm", 1)), centre=(0.0, 0.0), reach=1.2)
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
_biome("ruins", "Precursor ruins", "Worked stone, long straight edges and old cold light.", (150, 175, 160), (8, 12, 10), (120, 150, 140),
       cover=(), cover_chance=0.0, fauna=(("cave_beetle", 1),), centre=(9.0, 9.0), reach=1.0)

UBIOME_INDEX: Dict[str, int] = {key: i for i, key in enumerate(UBIOME_IDS)}
RUINS = UBIOME_INDEX["ruins"]

# Chance per spawn that a Selenite / a robot is the creature (instead of a cave animal); the ruins are theirs.
VISITORS = {"default": (0.06, 0.02), "ruins": (0.25, 0.30)}
FIELD_SCALE = 0.009


@lru_cache(maxsize=64)
def _noises(master: int, z: int):
    import tcod.noise
    from seeds import mix_seed
    return [tcod.noise.Noise(dimensions=2, algorithm=tcod.noise.Algorithm.PERLIN, seed=mix_seed(master, z, 77, i) % 2**31) for i in range(2)]


def clear_caches() -> None:
    _noises.cache_clear()


def field(master: int, z: int, key: ChunkKey, margin: int = 0) -> np.ndarray:
    """Biome index of every tile of chunk `key` (plus `margin` tiles around it), shape `(CHUNK_W + 2m, CHUNK_H + 2m)`."""
    import tcod.noise
    from structures import ruin_chunks
    x0, y0 = chunk_origin(key)
    width, height = CHUNK_W + 2 * margin, CHUNK_H + 2 * margin
    grid = dict(shape=(height, width), offset=(y0 - margin, x0 - margin))
    warm, wet = (1.7 * n[tcod.noise.grid(scale=FIELD_SCALE, **grid)] for n in _noises(master, z))
    candidates = [b for b in UBIOMES.values() if b.key != "ruins"]
    distance = np.stack([np.hypot(warm - b.centre[0], wet - b.centre[1]) / b.reach for b in candidates])
    out = np.array([UBIOME_INDEX[b.key] for b in candidates], dtype=np.int8)[np.argmin(distance, axis=0)]
    if key in ruin_chunks(master):                    # an oval of ruins under the surface ruin, its edge roughened by the warm field
        xs = (np.arange(width)[:, None] - margin - CHUNK_W / 2 + 0.5) / (CHUNK_W * 0.46)
        ys = (np.arange(height)[None, :] - margin - CHUNK_H / 2 + 0.5) / (CHUNK_H * 0.46)
        out[xs * xs + ys * ys + 0.25 * warm < 1.0] = RUINS
    return out


def paint(landscape: np.ndarray, biome: np.ndarray, floor: np.ndarray, wall: np.ndarray, rng: np.random.Generator) -> None:
    """Colour the tiles of a chunk by their biome (`floor` / `wall` are masks) and scatter each biome's cover over its floor."""
    for key, i in UBIOME_INDEX.items():
        b = UBIOMES[key]
        here = biome == i
        for layer, dim in (("light", 1.0), ("dark", 0.42)):
            landscape[layer]["fg"][floor & here] = tuple(int(c * dim) for c in b.floor)
            landscape[layer]["bg"][floor & here] = tuple(int(c * dim) for c in b.floor_bg) if layer == "light" else (0, 0, 0)
            landscape[layer]["fg"][wall & here] = tuple(int(c * (dim if layer == "light" else 0.4)) for c in b.wall)
        if b.cover and b.cover_chance:
            covered = floor & here & (rng.random(biome.shape) < b.cover_chance)
            if not covered.any():
                continue
            sprites = np.array([sprite_id(*cell) for cell in b.cover], dtype=np.int32)
            chosen = sprites[(rng.random(biome.shape) * len(sprites)).astype(int)[covered]]
            flip = rng.random(biome.shape)[covered] < 0.5
            for layer, dim in (("light", 1.0), ("dark", 0.42)):
                landscape[layer]["sprite"][covered] = chosen
                landscape[layer]["flip"][covered] = flip
                landscape[layer]["fg"][covered] = tuple(min(255, int(c * dim * 1.25)) if dim == 1.0 else int(c * dim) for c in b.floor)


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
