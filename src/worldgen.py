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
import hashlib
import random
import struct
from typing import Iterator, List, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import tcod

import tile_types
from chunks import CHUNK_H, CHUNK_W, Chunk, ChunkKey, chunk_origin
from species import PlantCategory, PlantSpecies, make_plant_species

if TYPE_CHECKING:
    from world import World

MARGIN = 2
"""Padding (tiles) around a chunk for neighbour-dependent generation steps: dilation (1) + variations (1)."""

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
            for i in range(4)
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
        self.spawn_point: Optional[Tuple[int, int]] = None
        self.stairs: Optional[Tuple[int, int]] = None

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

    def generate(self, world: World, key: ChunkKey) -> Chunk:
        x0, y0 = chunk_origin(key)
        with seeded_rng(self.chunk_seed(key)):
            tiles, tree_map = generate_terrain(self.noise, x0, y0, CHUNK_W, CHUNK_H)
        chunk = Chunk(key, tiles)
        chunk.pending_trees = tree_map  # consumed by populate()
        if key == (0, 0):
            self._place_start_and_stairs(world, chunk, tree_map)
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

    def _place_start_and_stairs(self, world: World, chunk: Chunk, tree_map: np.ndarray) -> None:
        """Start = the walkable tile (no tree) closest to the chunk centre; stairs = a walkable tile 8-20 tiles away."""
        free = chunk.tiles["walkable"] & ~tree_map
        if not free.any():  # a solid chunk: open its centre so there is somewhere to stand
            chunk.tiles[CHUNK_W // 2, CHUNK_H // 2] = tile_types.floor.get_array()
            free = chunk.tiles["walkable"] & ~tree_map
        xs, ys = np.nonzero(free)
        d = np.maximum(np.abs(xs - CHUNK_W // 2), np.abs(ys - CHUNK_H // 2))
        i = int(np.lexsort((ys, xs, d))[0])
        sx, sy = int(xs[i]), int(ys[i])
        self.spawn_point = (chunk.x0 + sx, chunk.y0 + sy)
        ring = np.maximum(np.abs(xs - sx), np.abs(ys - sy))
        candidates = np.nonzero((ring >= 8) & (ring <= 20))[0]
        if candidates.size == 0:
            candidates = np.nonzero(ring >= 1)[0]
        if candidates.size:
            with seeded_rng(mix_seed(self.chunk_seed(chunk.key), 2)):
                j = int(candidates[random.randrange(candidates.size)])
            tx, ty = int(xs[j]), int(ys[j])
            chunk.tiles[tx, ty] = tile_types.down_stairs.get_array()
            self.stairs = (chunk.x0 + tx, chunk.y0 + ty)
            world.downstairs_location = self.stairs


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

    def generate(self, world: World, key: ChunkKey) -> Chunk:
        tiles = np.full((CHUNK_W, CHUNK_H), fill_value=tile_types.floor.get_array(), dtype=tile_types.tile_dt, order="F")
        return Chunk(key, tiles)

    def populate(self, world: World, chunk: Chunk) -> None:
        pass
