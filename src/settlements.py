"""Farms and towns: chunks of the surface that people have built up.

A settlement is a chunk with neither a building nor a cave (the roll of `shafts.structure` is 0.6 or more) that wins a second
roll of its own. Like everything about the world it is a pure function of `(master_seed, chunk_key)`, so a chunk knows what it
holds without generating its neighbours, and `routes` can join the settlements to the other sites.

- a **farm**: a fenced field (tilled rows alternating with crops, a gate in the south fence) and a small farmhouse next to it;
- a **town**: a paved street across the chunk with a row of small houses on each side, their doors on the street.

A settlement is only built where the ground is dry and free of chasms: it tries a few spots and, failing that, the chunk stays
wild. It never touches the landing chunk."""
from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np  # type: ignore

import tile_types
from chunks import CHUNK_H, CHUNK_W, ChunkKey

CHANCE = 0.16
"""Of the chunks that have no structure, the share that is a settlement."""
FARM_SHARE = 0.65
"""Of the settlements, the share that are farms (the rest are towns)."""
MARGIN = 3
MEDKIT_CHANCE = 0.3


@dataclass(frozen=True)
class House:
    x: int
    y: int
    w: int
    h: int
    door: Tuple[int, int]       # chunk-local tile of the door in the wall


@dataclass(frozen=True)
class Layout:
    kind: str                       # "farm" or "town"
    houses: Tuple[House, ...]
    fence: Tuple[int, int, int, int] = (0, 0, 0, 0)     # farm: x, y, w, h of the fenced field (0 for a town)
    gate: Tuple[int, int] = (0, 0)
    streets: Tuple[Tuple[int, int, int, int], ...] = ()  # town: paved rectangles x, y, w, h


def _mix(*values: int) -> int:
    from shafts import _mix as mix
    return mix(*values)


def kind_of(master: int, key: ChunkKey) -> Optional[str]:
    """`"farm"`, `"town"` or None for chunk `key` (by the seed alone: whether the ground suits it is decided in `layout`)."""
    if key == (0, 0):
        return None
    import shafts
    if random.Random(_mix(master, key[0], key[1], 7)).random() < (
            shafts.BUILDING_CHANCE + shafts.SHAFT_CHANCE + shafts.MOUNTAIN_CAVE_BONUS):
        return None
    rng = random.Random(_mix(master, key[0], key[1], 8))
    if rng.random() >= CHANCE:
        return None
    return "farm" if rng.random() < FARM_SHARE else "town"


ROCK_LIMIT = 0.08
"""Share of rock a plot may have (a few boulders are cleared; a mountainside is not built on)."""


def _dry(ground, x: int, y: int, w: int, h: int) -> bool:
    """Whether the plot is free of water and chasms and not mostly rock. `ground` is `(wet_or_open, rock)` masks."""
    wet, rock = ground
    area = (slice(max(x - 1, 0), x + w + 1), slice(max(y - 1, 0), y + h + 2))
    return not wet[area].any() and rock[area].mean() <= ROCK_LIMIT


@lru_cache(maxsize=96)
def layout(master: int, key: ChunkKey) -> Optional[Layout]:
    """Where the settlement of chunk `key` stands (chunk-local tiles), or None when it has none or the ground does not allow."""
    kind = kind_of(master, key)
    if kind is None:
        return None
    import shafts
    raw = shafts.raw_surface(master, key)[0]
    blocked = ((raw["liquid"] != 0) | raw["open"], ~raw["walkable"] & ~raw["transparent"] & (raw["liquid"] == 0))
    rng = random.Random(_mix(master, key[0], key[1], 9))
    for _ in range(10):
        found = _farm(rng, blocked) if kind == "farm" else _town(rng, blocked)
        if found is not None:
            return found
    return None


def _farm(rng: random.Random, blocked) -> Optional[Layout]:
    fw, fh = rng.randint(22, 30), rng.randint(13, 18)
    hw, hh = rng.randint(7, 9), rng.randint(5, 6)
    total_w = hw + 3 + fw
    x0 = rng.randint(MARGIN, CHUNK_W - MARGIN - total_w)
    y0 = rng.randint(MARGIN, CHUNK_H - MARGIN - max(fh, hh) - 1)
    house_left = rng.random() < 0.5
    hx = x0 if house_left else x0 + fw + 3
    fx = x0 + hw + 3 if house_left else x0
    hy = y0 + max(fh, hh) - hh
    if not (_dry(blocked, fx, y0, fw, fh) and _dry(blocked, hx, hy, hw, hh)):
        return None
    door = (hx + hw // 2, hy + hh - 1)
    gate = (fx + fw // 2, y0 + fh - 1)
    return Layout("farm", (House(hx, hy, hw, hh, door),), fence=(fx, y0, fw, fh), gate=gate)


def _town(rng: random.Random, blocked) -> Optional[Layout]:
    street_y = rng.randint(CHUNK_H // 2 - 3, CHUNK_H // 2 + 3)
    x = MARGIN + rng.randint(0, 4)
    houses: List[House] = []
    while True:
        w, h = rng.randint(6, 9), rng.randint(5, 7)
        if x + w > CHUNK_W - MARGIN:
            break
        for side in (-1, 1):
            if rng.random() < 0.8:          # (some plots stay empty)
                if side < 0:
                    y = street_y - 2 - h + 1       # above the street, door in the south wall
                    door = (x + w // 2, y + h - 1)
                else:
                    y = street_y + 2               # below the street, door in the north wall
                    door = (x + w // 2, y)
                houses.append(House(x, y, w, h, door))
        x += w + rng.randint(2, 3)
    if len(houses) < 3:
        return None
    first, last = min(h.x for h in houses), max(h.x + h.w for h in houses)
    street = (first - 2, street_y, last - first + 4, 2)
    bounds_ok = all(0 <= h.y and h.y + h.h < CHUNK_H for h in houses)
    if not bounds_ok or not _dry(blocked, street[0], street[1], street[2], 2):
        return None
    if not all(_dry(blocked, h.x, h.y, h.w, h.h) for h in houses):
        return None
    return Layout("town", tuple(houses), streets=(street,))


def paint(master: int, key: ChunkKey, tiles: np.ndarray, tree_map: np.ndarray) -> None:
    """Draw the chunk's settlement into its (copied) tiles and clear the trees under it."""
    found = layout(master, key)
    if found is None:
        return
    for house in found.houses:
        _house(tiles, tree_map, house)
    if found.kind == "farm":
        _field(tiles, tree_map, found)
    for x, y, w, h in found.streets:
        tiles[x:x + w, y:y + h] = tile_types.street.get_array()
        tree_map[x:x + w, y:y + h] = False
    for house in found.houses:         # a street tile in front of every door (and the farm's path to its gate)
        dx, dy = house.door
        step = 1 if dy >= house.y + house.h - 1 else -1
        tiles[dx, dy + step] = (tile_types.street if found.kind == "town" else tile_types.path).get_array()


def built(master: int, key: ChunkKey) -> frozenset:
    """Chunk-local tiles that people have built on (houses and a margin round them, the field, the streets): nothing wild is
    scattered there."""
    found = layout(master, key)
    if found is None:
        return frozenset()
    tiles = set()
    rects = [(h.x - 1, h.y - 1, h.w + 2, h.h + 3) for h in found.houses] + list(found.streets)
    if found.kind == "farm":
        rects.append(found.fence)
    for x, y, w, h in rects:
        tiles.update((i, j) for i in range(max(0, x), min(CHUNK_W, x + w)) for j in range(max(0, y), min(CHUNK_H, y + h)))
    return frozenset(tiles)


def populate(world, chunk, master: int) -> None:
    """The people and supplies of a settlement: rations (and now and then a medkit) on the floors of its houses, and settlers
    about the street (a town) or the farmyard. Uses the chunk's seeded `random`."""
    import types
    import components.unit as units
    from components.consumable import Ration
    import structures
    found = layout(master, chunk.key)
    if found is None:
        return
    nobody = types.SimpleNamespace(inventory=None)
    for house in found.houses:
        floor = [(x, y) for x in range(house.x + 1, house.x + house.w - 1) for y in range(house.y + 1, house.y + house.h - 1)]
        for _ in range(random.randint(1, 2)):
            x, y = floor.pop(random.randrange(len(floor)))
            world.add_entity(Ration(), chunk.x0 + x, chunk.y0 + y)
        if random.random() < MEDKIT_CHANCE:
            x, y = random.choice(floor)
            world.add_entity(structures.salvage_piece("medkit", nobody), chunk.x0 + x, chunk.y0 + y)
    if found.kind == "town":
        spots = [(x + random.randrange(w), y + random.randrange(h)) for x, y, w, h in found.streets for _ in range(8)]
        count = random.randint(2, 4)
    else:
        fx, fy, fw, fh = found.fence
        spots = [(fx + 1 + random.randrange(fw - 2), fy + 1 + random.randrange(fh - 2)) for _ in range(8)]
        count = random.randint(1, 2)
    for lx, ly in spots:
        if count <= 0:
            break
        x, y = chunk.x0 + lx, chunk.y0 + ly
        if world.is_walkable(x, y) and not world.is_blocked(x, y) and not world.get_entities_at_location(x, y):
            world.add_entity(units.Settler(), x, y)
            count -= 1


def _house(tiles: np.ndarray, tree_map: np.ndarray, house: House) -> None:
    x, y, w, h = house.x, house.y, house.w, house.h
    tiles[x:x + w, y:y + h] = tile_types.wall.get_array()
    tiles[x + 1:x + w - 1, y + 1:y + h - 1] = tile_types.floor.get_array()
    tiles[house.door] = tile_types.floor.get_array()
    tree_map[x - 1:x + w + 1, y - 1:y + h + 2] = False


def _field(tiles: np.ndarray, tree_map: np.ndarray, found: Layout) -> None:
    x, y, w, h = found.fence
    tree_map[x:x + w, y:y + h] = False
    tiles[x:x + w, y:y + h] = tile_types.farmland.get_array()
    for row in range(y + 2, y + h - 1, 2):                 # every other row, clear of the fence, carries crops
        tiles[x + 1:x + w - 1, row] = tile_types.crops.get_array()
    for fx, fy in [(i, j) for i in range(x, x + w) for j in (y, y + h - 1)] + [(i, j) for i in (x, x + w - 1) for j in range(y, y + h)]:
        tiles[fx, fy] = tile_types.fence.get_array()
    gx, gy = found.gate
    tiles[gx, gy] = tile_types.path.get_array()            # the gate
    tiles[gx, gy - 1] = tile_types.farmland.get_array()    # (and the row inside it stays open)
