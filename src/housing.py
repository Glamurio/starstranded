"""Walls of houses and buildings as wall entities of the construction system (`crafting.Wall`): a material, hit points, taken down by
attacking or salvaging them, instead of rock tiles that only a pickaxe could mine. The tiles under them are floor."""
from __future__ import annotations

import random
from typing import Iterable, List, Tuple

from items import DEFAULT_WOOD


def ring(x: int, y: int, w: int, h: int, openings: Iterable[Tuple[int, int]] = ()) -> List[Tuple[int, int]]:
    """The wall tiles round a rectangle (chunk-local), without the tiles in `openings` (doors)."""
    skip = set(openings)
    edge = [(i, j) for i in range(x, x + w) for j in (y, y + h - 1)] + [(i, j) for i in (x, x + w - 1) for j in range(y + 1, y + h - 1)]
    return [t for t in edge if t not in skip]


def material_for(planet, seed: int, kind: str):
    """The material a building is made of: a wood of the planet's trees (`kind` "wood") or one of its stones ("stone"); chosen from
    `seed`, so a place always looks the same. Plain wood when there is no planet (tests)."""
    if planet is None:
        return DEFAULT_WOOD
    rng = random.Random(seed)
    if kind == "wood":
        woods = [s.material for s in planet.flora if s.material is not None]
        if woods:
            return rng.choice(woods)
    stones = [planet.material(i) for _, ids in planet.stone_ids for i in ids]
    return rng.choice(stones) if stones else DEFAULT_WOOD


def raise_walls(world, chunk, tiles: Iterable[Tuple[int, int]], material) -> None:
    """Stand a wall of `material` on each chunk-local tile."""
    from crafting import Wall
    for lx, ly in tiles:
        for entity in list(world.get_entities_at_location(chunk.x0 + lx, chunk.y0 + ly)):
            if not getattr(entity, "decal", False):
                world.remove_entity(entity)        # (a creature or plant that spawned on the line of the wall is cleared away)
        world.add_entity(Wall({"wall": material}, 1.0, {}), chunk.x0 + lx, chunk.y0 + ly)


def raise_building(world, chunk, master: int, z: int) -> None:
    """The walls of the chunk's building on layer `z` (0 the ground floor, up to its top floor), but not at its door or stairs."""
    import shafts
    building = shafts.structure(master, chunk.key).building
    if building is None or z > building.floors:
        return
    skip = [building.door] if z == 0 else []
    ring_tiles = [t for t in ring(building.x, building.y, building.w, building.h, skip)
                  if not (int(world.tile_at(chunk.x0 + t[0], chunk.y0 + t[1])["stairs"]))]
    planet = getattr(getattr(world.engine, "game_world", None), "planet", None)
    material = material_for(planet, hash((master, chunk.key[0], chunk.key[1], 3)) & 0xFFFFFFFF, "stone")
    raise_walls(world, chunk, ring_tiles, material)
