"""What the player knows of the surface, one record per chunk (the data behind the world map on M).

Rules: the map only ever shows what the player has seen. A chunk gets a record the first time any of its tiles is
explored, and the record is rebuilt from the explored tiles alone whenever more of the chunk has been explored, so it
never reveals terrain that was not seen and it never asks the world generator for anything. The records live in
`run.flags["map"]` (saved with the run, absent in older saves)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np  # type: ignore

from chunks import CHUNK_H, CHUNK_W, ChunkKey

FLAG = "map"
BLOCK = 10
"""Tiles per side of a map block: a chunk is drawn as a grid of blocks, each one picture (a tree, water, rock, grass ...)."""
BLOCKS_X, BLOCKS_Y = CHUNK_W // BLOCK, CHUNK_H // BLOCK
TREE_BLOCK, SHRUB_BLOCK = 4, 6
"""Plants in a block (of 100 tiles) that make it a wood or a thicket."""


@dataclass(frozen=True)
class Known:
    """What is known of one chunk: how many of its tiles were seen, their average colour, how much of what was seen is
    water and rock, and the biome it lies in (`""` for none)."""
    seen: int
    color: Tuple[int, int, int]
    water: float
    rock: float
    biome: str = ""
    blocks: tuple = ()
    """`BLOCKS_X * BLOCKS_Y` entries, row by row: `(sprite, colour, background)` of what the block shows, or None for a block
    not yet seen (empty in saves from before the picture map)."""

    @property
    def share(self) -> float:
        """The part of the chunk that has been explored."""
        return self.seen / (CHUNK_W * CHUNK_H)


def records(run) -> Dict[ChunkKey, Known]:
    """The chunk records of a run (created empty on first use)."""
    return run.flags.setdefault(FLAG, {})


def summarise(chunk, master_seed: Optional[int] = None) -> Optional[Known]:
    """A record from the explored tiles of a loaded chunk (None when none are explored). `master_seed` also names the
    biome; without it (tests of a fixed landscape) there is none."""
    explored = chunk.explored
    seen = int(explored.sum())
    if not seen:
        return None
    tiles = chunk.tiles
    water = explored & (tiles["depth"] > 0)
    rock = explored & ~water & ~tiles["walkable"] & ~tiles["open"]
    colors = tiles["light"]["fg"][explored].astype(float)
    color = tuple(int(c) for c in colors.mean(axis=0))
    return Known(seen, color, float(water.sum()) / seen, float(rock.sum()) / seen, _biome(chunk, master_seed), _blocks(chunk))


def _common(values) -> int:
    """The most frequent of a list of ints."""
    found, counts = np.unique(np.asarray(values), return_counts=True)
    return int(found[counts.argmax()])


def _mean_colour(colours) -> Tuple[int, int, int]:
    return tuple(int(c) for c in np.asarray(colours, dtype=float).reshape(-1, 3).mean(axis=0))


def _plants_by_block(chunk) -> Dict[Tuple[int, int], Dict[str, list]]:
    """Seen plants of the chunk, sorted into its blocks as `{"tree": [(sprite, colour)], "shrub": [...]}`."""
    from entity import EntityCategory
    from species import PlantCategory
    out: Dict[Tuple[int, int], Dict[str, list]] = {}
    for plant in chunk.by_category[EntityCategory.PLANT]:
        lx, ly = plant.x - chunk.x0, plant.y - chunk.y0
        if not chunk.explored[lx, ly]:
            continue
        kind = getattr(plant, "kind", None)
        word = "tree" if getattr(kind, "category", None) is PlantCategory.TREE else "shrub"
        entry = out.setdefault((lx // BLOCK, ly // BLOCK), {"tree": [], "shrub": []})
        entry[word].append((int(plant.sprite_id), tuple(int(c) for c in plant.color)))
    return out


def _blocks(chunk) -> tuple:
    """One picture per block of the explored part of a chunk, chosen from what was seen there: water, a wood (its commonest
    tree), a settlement, rock, a thicket, or else the ground."""
    plants = _plants_by_block(chunk)
    tiles = chunk.tiles
    out = []
    for by in range(BLOCKS_Y):
        for bx in range(BLOCKS_X):
            sx, sy = slice(bx * BLOCK, (bx + 1) * BLOCK), slice(by * BLOCK, (by + 1) * BLOCK)
            seen = chunk.explored[sx, sy]
            n = int(seen.sum())
            if not n:
                out.append(None)
                continue
            light = tiles["light"][sx, sy][seen]
            bg = _mean_colour(light["bg"])
            water = tiles["depth"][sx, sy][seen] > 0
            built = tiles["built"][sx, sy][seen]
            rock = ~water & ~tiles["walkable"][sx, sy][seen] & ~tiles["open"][sx, sy][seen]
            found = plants.get((bx, by), {"tree": [], "shrub": []})

            def pick(mask):
                sprites = light["sprite"][mask]
                sprite = _common(sprites)
                return sprite, _mean_colour(light["fg"][mask][sprites == sprite])

            if water.sum() * 2 >= n:
                sprite, fg = pick(water)
            elif len(found["tree"]) >= TREE_BLOCK:
                (sprite, fg) = max(set(found["tree"]), key=found["tree"].count)
            elif built.sum() * 3 >= n:
                sprite, fg = pick(built)
            elif rock.sum() * 2 >= n:
                sprite, fg = pick(rock)
            elif len(found["shrub"]) >= SHRUB_BLOCK:
                (sprite, fg) = max(set(found["shrub"]), key=found["shrub"].count)
            else:
                ground = ~water
                sprite, fg = pick(ground if ground.any() else water)
            out.append((int(sprite), fg, bg))
    return tuple(out)


def _biome(chunk, master_seed: Optional[int]) -> str:
    """The biome that most of the explored tiles of a chunk belong to ("" when unknown)."""
    if master_seed is None:
        return ""
    import biomes
    import shafts
    try:
        env = shafts.environment(master_seed, chunk.key)
    except Exception:       # a fixed test landscape has no climate behind it
        return ""
    found = env["biome"][chunk.explored]
    if not found.size:
        return ""
    return biomes.BIOME_IDS[int(np.bincount(found).argmax())]


def record(engine) -> None:
    """Update the records of the chunks in view (surface only). Called whenever the field of view is recomputed."""
    world = engine.game_map
    game_world = getattr(engine, "game_world", None)
    if game_world is None or world.z != 0:
        return
    known = records(game_world.run)
    for chunk in world.chunks_in_rect(world.window.rect):
        old = known.get(chunk.key)
        if old is not None and old.seen >= int(chunk.explored.sum()):
            continue
        found = summarise(chunk, getattr(game_world, "master_seed", None))
        if found is not None:
            known[chunk.key] = found


def visible_chunks(engine) -> set:
    """Keys of the loaded chunks of this layer with something in view right now."""
    world = engine.game_map
    window = world.window
    ox, oy = window.origin
    out = set()
    for chunk in world.chunks_in_rect(window.rect):
        sx = slice(chunk.x0 - ox, chunk.x0 - ox + CHUNK_W)
        sy = slice(chunk.y0 - oy, chunk.y0 - oy + CHUNK_H)
        if window.visible[sx, sy].any():
            out.add(chunk.key)
    return out


def bounds(known: Dict[ChunkKey, Known], extra=()) -> Tuple[int, int, int, int]:
    """`(kx0, ky0, kx1, ky1)`: the smallest chunk rectangle holding every known chunk and the `extra` keys (inclusive)."""
    keys = list(known) + list(extra)
    xs, ys = [k[0] for k in keys], [k[1] for k in keys]
    return min(xs), min(ys), max(xs), max(ys)


def fit_cell(columns: int, rows: int, width_px: int, height_px: int, lowest: int = 4, highest: int = 32) -> int:
    """The largest square cell (pixels, between `lowest` and `highest`) with which a `columns` x `rows` chunk rectangle fits
    in `width_px` x `height_px`; `lowest` when even that does not fit (the map then scrolls)."""
    best = min(width_px // max(columns, 1), height_px // max(rows, 1))
    return max(lowest, min(highest, best))


def fit_block(columns: int, rows: int, width_px: int, height_px: int, lowest: int = 3, highest: int = 24) -> int:
    """The largest block size (pixels, `lowest`..`highest`) with which `columns` x `rows` chunks fit in the area."""
    return fit_cell(columns * BLOCKS_X, rows * BLOCKS_Y, width_px, height_px, lowest, highest)
