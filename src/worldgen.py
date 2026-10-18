"""Deterministic generation of chunks from `(floor_seed, cx, cy)`.

Terrain noise is sampled in world coordinates, so it is seamless across chunk borders. The steps that look at
neighbouring tiles (lake dilation, edge variations of water and walls) run on a region padded by `MARGIN` tiles on
every side and only the 70x40 interior is kept, so a tile on a border sees the same neighbours whichever chunk is
generated. Everything random inside a chunk runs under `seeded_rng(chunk_seed)`, which also covers incidental
`random` use in entity constructors (shades, names, mirroring): generating a chunk twice gives the same terrain and
the same entities (only uids differ).
"""
from __future__ import annotations

import colorsys
import contextlib
import hashlib
import random
import struct
from typing import Iterator, List, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import tcod

import shafts
import tile_types
from chunks import CHUNK_H, CHUNK_W, Chunk, ChunkKey, chunk_origin
from species import PlantCategory, PlantSpecies, make_plant_species

if TYPE_CHECKING:
    from world import World

MARGIN = 4
"""Padding (tiles) around a chunk for neighbour-dependent generation steps: dilation (1) + variations (1) + the two
erosions that give the liquid depths (2)."""

LIQUID_HUES = 24
DEPTH_BRIGHTNESS = (1.0, 0.78, 0.58)  # shallow, deep, very deep: the same hue, darker
IMPURE_BELOW, TOXIC_BELOW = 0.15, 0.40  # liquid noise thresholds: below the first is impure, below the second toxic, else acidic

HEIGHT_LIMITS = (-1.1, -0.3, 0.3, 1.1)  # water | floor | wall (values outside stay wall, as before)


def mix_seed(*values: int) -> int:
    """A stable 63-bit seed from ints (negative ones fine), identical across processes and platforms."""
    digest = hashlib.blake2b(struct.pack(f"<{len(values)}q", *values), digest_size=8).digest()
    return int.from_bytes(digest, "little") >> 1


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


class TerrainNoise:
    """The floor's four noise generators (two for height, two for vegetation, as the single-map generator had)."""

    def __init__(self, floor_seed: int):
        self.noises = [
            tcod.noise.Noise(dimensions=2, algorithm=tcod.noise.Algorithm.PERLIN, seed=mix_seed(floor_seed, i) % 2**31)
            for i in range(6)
        ]

    def sample(self, index: int, scale: float, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Noise `index` on the world rectangle (x0, y0, width, height) as a [x, y] array."""
        samples = self.noises[index][tcod.noise.grid(shape=(height, width), scale=scale, offset=(y0, x0))]
        assert samples.shape == (width, height), (
            f"tcod.noise.grid axis order changed: got {samples.shape}, expected {(width, height)}"
        )
        return samples

    def heights(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        return (self.sample(0, 0.05, x0, y0, width, height) + self.sample(1, 0.25, x0, y0, width, height)) / 2

    def liquid_kind_field(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Slowly varying noise that decides what a lake is made of (a lake is mostly one kind)."""
        return self.sample(4, 0.006, x0, y0, width, height)

    def liquid_hue_field(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        """Slowly varying noise for the colour of a lake: unrelated to its kind on purpose."""
        return self.sample(5, 0.004, x0, y0, width, height)

    def vegetation(self, x0: int, y0: int, width: int, height: int) -> np.ndarray:
        # (The single-map generator also sampled noise 2 at scale 0.05 but overwrote it; the result is noise 3 only.)
        return self.sample(3, 0.1, x0, y0, width, height)


def base_terrain(noise: TerrainNoise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    """The deterministic part of the terrain (no RNG): 0 water, 1 floor, 2 wall, lakes grown by one tile.

    Correct for every tile of the rectangle except its outermost ring (dilation needs the neighbour).
    """
    from procgen import dilate
    heights = noise.heights(x0, y0, width, height)
    kinds = np.full((width, height), 2, dtype=np.int8, order="F")
    for kind, (low, high) in enumerate(zip(HEIGHT_LIMITS[:-1], HEIGHT_LIMITS[1:])):
        kinds[(heights > low) & (heights <= high)] = kind
    kinds[dilate(kinds == 0)] = 0
    return kinds


def _shape_liquid(noise: TerrainNoise, landscape: np.ndarray, liquid: np.ndarray, x0: int, y0: int, width: int, height: int) -> None:
    """Give the lake tiles (`liquid` mask) their depth (1 on the shore, +1 per tile inwards, at most 3: deeper liquid is
    always ringed by shallower), kind and hue. Shallow liquid can be waded, deeper liquid cannot."""
    from procgen import neighbour_masks
    depth = liquid.astype(np.int8)
    inner = liquid
    for _ in range(2):
        left, right, up, down = neighbour_masks(inner)
        inner = inner & left & right & up & down
        depth += inner
    kind_value = noise.liquid_kind_field(x0, y0, width, height)
    kind = np.where(kind_value < IMPURE_BELOW, 1, np.where(kind_value < TOXIC_BELOW, 2, 3)).astype(np.int8)
    hue_index = np.clip(((noise.liquid_hue_field(x0, y0, width, height) + 1) / 2 * LIQUID_HUES).astype(np.int32), 0, LIQUID_HUES - 1)
    palette = np.array([colorsys.hsv_to_rgb(i / LIQUID_HUES, 0.7, 0.85) for i in range(LIQUID_HUES)]) * 255
    brightness = np.array((0, *DEPTH_BRIGHTNESS))[depth]
    light = (palette[hue_index] * brightness[..., None]).astype(np.uint8)
    landscape["liquid"][liquid] = kind[liquid]
    landscape["depth"][liquid] = depth[liquid]
    landscape["walkable"][liquid] = depth[liquid] == 1
    landscape["light"]["fg"][liquid] = light[liquid]
    landscape["dark"]["fg"][liquid] = (light[liquid] * 0.5).astype(np.uint8)


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
    _shape_liquid(noise, landscape, kinds == 0, x0 - m, y0 - m, pw, ph)

    # Vegetation: roots wherever the vegetation noise beats a random threshold (not in lakes), as before.
    random_map = np.random.rand(pw, ph)
    tree_map = (noise.vegetation(x0 - m, y0 - m, pw, ph) > random_map + 0.1) & (kinds != 0)
    landscape[tree_map] = tile_types.roots.get_array()
    interior = (slice(m, m + width), slice(m, m + height))
    return np.asfortranarray(landscape[interior]), np.asfortranarray(tree_map[interior])


class NoiseWorldSource:
    """Chunk source of a generated floor (see module docstring). Also owns the floor's procedural species and
    the start position and staircase, which live in chunk (0, 0)."""

    bounds = None

    def __init__(self, floor_seed: int, floor: int = 1, species: Optional[Tuple[PlantSpecies, PlantSpecies]] = None):
        self.floor_seed = floor_seed
        self.floor = floor
        self.noise = TerrainNoise(floor_seed)
        if species is None:
            with seeded_rng(mix_seed(floor_seed, 1000)):
                species = (make_plant_species(PlantCategory.TREE), make_plant_species(PlantCategory.SHRUB))
        self.tree_species, self.shrub_species = species

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
        now = world.engine.game_world.current_time if getattr(world.engine, "game_world", None) else 0
        before = set(chunk.entities)
        with seeded_rng(mix_seed(self.chunk_seed(chunk.key), 1)):
            for lx, ly in np.argwhere(tree_map).tolist():
                if random.random() > 0.2:
                    plant = components.plant.Tree(self.tree_species)
                else:
                    plant = components.plant.Shrub(self.shrub_species)
                plant.growth = random.randrange(int(plant.avg_cycle) + 1)  # staggered, so the forest does not fruit in unison
                world.add_entity(plant, chunk.x0 + lx, chunk.y0 + ly)
            reserved = {self.spawn_point} if chunk.key == (0, 0) else set()
            place_entities(world, self.floor, area=(chunk.x0, chunk.y0, CHUNK_W, CHUNK_H), reserved=reserved)
        for entity in chunk.entities:
            if entity not in before:
                entity.last_upkeep = now


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
        from procgen import cave_enemy_chances, place_entities
        now = world.engine.game_world.current_time if getattr(world.engine, "game_world", None) else 0
        before = set(chunk.entities)
        with seeded_rng(mix_seed(self.floor_seed, chunk.key[0], chunk.key[1], 1)):
            place_entities(world, self.floor, area=(chunk.x0, chunk.y0, CHUNK_W, CHUNK_H), enemies=cave_enemy_chances)
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
