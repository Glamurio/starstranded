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


@dataclass(frozen=True)
class Known:
    """What is known of one chunk: how many of its tiles were seen, their average colour, how much of what was seen is
    water and rock, and the biome it lies in (`""` for none)."""
    seen: int
    color: Tuple[int, int, int]
    water: float
    rock: float
    biome: str = ""

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
    return Known(seen, color, float(water.sum()) / seen, float(rock.sum()) / seen, _biome(chunk, master_seed))


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
