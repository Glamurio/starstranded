"""Points of interest: small, localized things a region holds (`_place_sites` in `worldgen` calls `place`).

A region (a biome) is the big picture; a point of interest is a place inside it: a ruined cabin, a ring of standing stones, a field of
wrecks. Each kind is a function that builds one on free ground near the middle of a chunk, from the chunk's own seeded `random`, so the
world is the same however it is loaded. What a chunk holds follows its biome (`Biome.pois` gives the weight of each kind there; a kind a
biome does not list has its default weight, and a city lists its own kinds only); what a point of interest is made of follows it too
(timber from the planet's own trees, stone from the biome's rock) and so does the scenery it is dressed with. Nothing here is inhabited.

Adding a kind: write a builder `(Site) -> bool`, register it in `POIS` with a default weight and (optionally) the biomes that favour it
in their `pois`. Prefab layouts can be added as ASCII (`PREFABS`) and stamped with `stamp`."""
from __future__ import annotations

import random
import types
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import biomes
from chunks import CHUNK_H, CHUNK_W
from seeds import mix_seed

CHANCE = 0.4
"""Share of chunks that hold a point of interest (the landing chunk, ruin chunks and settlements never do)."""
SECOND = 0.25
"""Of those, the share that hold a second one."""


@dataclass
class Site:
    world: object
    chunk: object
    rng: random.Random
    planet: object
    biome: "biomes.Biome"
    seed: int

    @property
    def stone(self):
        """A rock of this biome (the planet's own stones, as the region favours them); plain wood when there is no planet (tests)."""
        import housing
        if self.planet is None:
            return housing.material_for(None, 0, "stone")
        import resources
        return resources.surface_stone(self.planet, self.seed, self.chunk.x0, self.chunk.y0, 4403, self.biome.key)

    @property
    def wood(self):
        import housing
        return housing.material_for(self.planet, self.rng.getrandbits(32), "wood")


@dataclass(frozen=True)
class Poi:
    key: str
    name: str
    weight: float
    build: Callable[[Site], bool]


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────────
def _free(site: Site, x: int, y: int) -> bool:
    import structures
    return structures._free(site.world, x, y)


def _rect(site: Site, w: int, h: int, margin: int = 1, tries: int = 30) -> Optional[Tuple[int, int]]:
    """The top-left world tile of a free `w` by `h` plot (plus a margin all round) near the middle of the chunk."""
    for _ in range(tries):
        x = site.chunk.x0 + site.rng.randint(8, CHUNK_W - w - 8)
        y = site.chunk.y0 + site.rng.randint(6, CHUNK_H - h - 6)
        if all(_free(site, i, j) for i in range(x - margin, x + w + margin) for j in range(y - margin, y + h + margin)):
            return x, y
    return None


def _scatter(site: Site, key: str, x: int, y: int, spread: int, count: int, dense: bool = False) -> int:
    """`count` scenery pieces of kind `key` on free tiles within `spread` of (x, y)."""
    import scenery
    placed = 0
    for _ in range(count * 4):
        if placed >= count:
            break
        i, j = x + site.rng.randint(-spread, spread), y + site.rng.randint(-spread, spread)
        if not scenery.tile_is_free(site.world, i, j):
            continue
        variant = site.rng.randrange(1000)
        color = scenery.vary(scenery.BY_KEY[key].color, (variant % 97) / 96.0, (variant % 89) / 88.0)
        site.world.add_entity(scenery.Scenery(key, variant, color), i, j)
        placed += 1
    return placed


def _walls(site: Site, tiles, material) -> None:
    from crafting import Wall
    for x, y in tiles:
        for entity in list(site.world.get_entities_at_location(x, y)):
            if not getattr(entity, "decal", False):
                site.world.remove_entity(entity)
        site.world.add_entity(Wall({"wall": material}, 1.0, {}), x, y)


def _ring(x: int, y: int, w: int, h: int, door: Tuple[int, int]) -> List[Tuple[int, int]]:
    edge = [(i, j) for i in range(x, x + w) for j in (y, y + h - 1)] + [(i, j) for i in (x, x + w - 1) for j in range(y + 1, y + h - 1)]
    return [t for t in edge if t != door]


def _drop(site: Site, kind: str, x: int, y: int) -> None:
    import structures
    site.world.add_entity(structures.salvage_piece(kind, types.SimpleNamespace(inventory=None)), x, y)


def _stand_walls(site: Site, x: int, y: int, w: int, h: int, material, fallen: float) -> Tuple[int, int]:
    """A walled building with a door in its south wall, part of the wall fallen (scenery rubble); returns the door tile."""
    door = (x + w // 2, y + h - 1)
    tiles = [t for t in _ring(x, y, w, h, door) if site.rng.random() >= fallen]
    gone = [t for t in _ring(x, y, w, h, door) if t not in tiles]
    _walls(site, tiles, material)
    for gx, gy in gone:
        _scatter(site, "rubble", gx, gy, 0, 1)
    return door


# ── the kinds ───────────────────────────────────────────────────────────────────────────────────────────
def standing_stones(site: Site) -> bool:
    """A ring of pillars round a cold hearth."""
    at = _rect(site, 11, 9)
    if at is None:
        return False
    cx, cy = at[0] + 5, at[1] + 4
    material = site.stone
    ring = [(cx + dx, cy + dy) for dx, dy in ((-4, 0), (4, 0), (0, -3), (0, 3), (-3, -2), (3, -2), (-3, 2), (3, 2))]
    _walls(site, [t for t in ring if site.rng.random() < 0.85], material)
    _scatter(site, "ash_pile", cx, cy, 0, 1)
    _scatter(site, "monolith", cx, cy, 6, 2)
    return True


def bone_pile(site: Site) -> bool:
    """Bones and skulls heaped where something died, or was brought to."""
    at = _rect(site, 7, 5, 0)
    if at is None:
        return False
    cx, cy = at[0] + 3, at[1] + 2
    _scatter(site, "bones", cx, cy, 3, site.rng.randint(8, 14))
    _scatter(site, "skull", cx, cy, 3, site.rng.randint(2, 4))
    return True


def graveyard(site: Site) -> bool:
    """Rows of gravestones inside a broken fence."""
    from crafting import Fence
    w, h = 10, 7
    at = _rect(site, w, h)
    if at is None:
        return False
    import scenery
    x, y = at
    for i in range(x, x + w):
        for j in (y, y + h - 1):
            if site.rng.random() < 0.7:
                site.world.add_entity(Fence(), i, j)
    for j in range(y + 1, y + h - 1):
        for i in (x, x + w - 1):
            if site.rng.random() < 0.7:
                site.world.add_entity(Fence(), i, j)
    for i in range(x + 2, x + w - 2, 2):
        for j in range(y + 2, y + h - 2, 2):
            if site.rng.random() < 0.8 and scenery.tile_is_free(site.world, i, j):
                variant = site.rng.randrange(1000)
                site.world.add_entity(scenery.Scenery("gravestone", variant, scenery.vary(scenery.BY_KEY["gravestone"].color, (variant % 97) / 96.0, 0.5)), i, j)
    return True


def wreck_field(site: Site) -> bool:
    """A scatter of wrecked vehicles and drums, with a few usable parts still in them."""
    at = _rect(site, 14, 9, 0)
    if at is None:
        return False
    cx, cy = at[0] + 7, at[1] + 4
    _scatter(site, "wreck_car", cx, cy, 6, site.rng.randint(2, 4))
    _scatter(site, "wreck_truck", cx, cy, 6, site.rng.randint(1, 3))
    _scatter(site, "drum", cx, cy, 6, site.rng.randint(2, 5))
    _scatter(site, "rubble", cx, cy, 6, site.rng.randint(3, 6))
    for kind in site.rng.sample(["hull_plate", "circuit", "lens", "wire"], 2):
        for _ in range(12):
            x, y = cx + site.rng.randint(-5, 5), cy + site.rng.randint(-4, 4)
            if _free(site, x, y):
                _drop(site, kind, x, y)
                break
    return True


def ruined_cabin(site: Site) -> bool:
    """A one-room timber cabin with half its wall down, a ration on the floor and a stump outside."""
    w, h = site.rng.randint(6, 8), site.rng.randint(5, 6)
    at = _rect(site, w, h)
    if at is None:
        return False
    x, y = at
    _stand_walls(site, x, y, w, h, site.wood, 0.4)
    floor = [(i, j) for i in range(x + 1, x + w - 1) for j in range(y + 1, y + h - 1) if _free(site, i, j)]
    if floor:
        _drop(site, "ration", *site.rng.choice(floor))
    _scatter(site, "stump", x + w // 2, y + h + 1, 4, 2)
    return True


def research_outpost(site: Site) -> bool:
    """A stone laboratory block with two rooms, left-behind equipment and a lamp post."""
    w, h = 11, 7
    at = _rect(site, w, h, 2)
    if at is None:
        return False
    x, y = at
    material = site.stone
    _stand_walls(site, x, y, w, h, material, 0.2)
    _walls(site, [(x + w // 2, j) for j in range(y + 1, y + h - 1) if j != y + 2], material)         # a dividing wall with a gap
    floor = [(i, j) for i in range(x + 1, x + w - 1) for j in range(y + 1, y + h - 1) if _free(site, i, j)]
    site.rng.shuffle(floor)
    for kind in ("circuit", "lens", "medkit", "ration"):
        if floor:
            _drop(site, kind, *floor.pop())
    _scatter(site, "lamp_post", x - 1, y + h, 1, 1)
    _scatter(site, "drum", x + w + 1, y + h // 2, 2, 2)
    _scatter(site, "pipe", x + w // 2, y + h + 1, 3, 1)
    return True


def abandoned_farm(site: Site) -> bool:
    """A small fenced plot gone wild: a gap in the fence and the old crop still growing in rows."""
    from crafting import Fence
    import components.plant
    w, h = 12, 7
    at = _rect(site, w, h)
    if at is None or site.planet is None:
        return False
    x, y = at
    import worldgen
    bare = worldgen.cover_sprites()          # (no crop stands on a tuft of ground cover)
    gate = x + w // 2
    for i in range(x, x + w):
        for j in (y, y + h - 1):
            if (i != gate or j != y + h - 1) and site.rng.random() < 0.75:
                site.world.add_entity(Fence(), i, j)
    for j in range(y + 1, y + h - 1):
        for i in (x, x + w - 1):
            if site.rng.random() < 0.75:
                site.world.add_entity(Fence(), i, j)
    for j in range(y + 2, y + h - 2, 2):
        for i in range(x + 2, x + w - 2):
            if site.rng.random() < 0.7 and _free(site, i, j) and int(site.world.tile_at(i, j)["light"]["sprite"]) not in bare:
                plant = components.plant.Shrub(site.planet.crop)
                plant.growth = site.rng.randrange(int(plant.avg_cycle) + 1)
                site.world.add_entity(plant, i, j)
    return True


POIS: Dict[str, Poi] = {p.key: p for p in (
    Poi("standing_stones", "Standing stones", 0.6, standing_stones),
    Poi("bone_pile", "Bone pile", 1.0, bone_pile),
    Poi("graveyard", "Graveyard", 0.3, graveyard),
    Poi("wreck_field", "Wreck field", 0.5, wreck_field),
    Poi("ruined_cabin", "Ruined cabin", 1.0, ruined_cabin),
    Poi("research_outpost", "Research outpost", 0.3, research_outpost),
    Poi("abandoned_farm", "Abandoned farm plot", 0.5, abandoned_farm),
)}


def weights(biome: "biomes.Biome") -> Dict[str, float]:
    """The weight of each kind in a biome: the biome's own number, else the kind's default (a city lists its own kinds only)."""
    return {k: biome.pois.get(k, 0.0 if biome.urban is not None else p.weight) for k, p in POIS.items()}


def roll(master: int, key: Tuple[int, int], biome: "biomes.Biome") -> List[str]:
    """The kinds of point of interest chunk `key` holds (pure in the seed and the biome at its middle)."""
    rng = random.Random(mix_seed(master, key[0], key[1], 4401))
    if rng.random() >= CHANCE:
        return []
    table = weights(biome)
    keys = [k for k in POIS if table[k] > 0]
    if not keys:
        return []
    picks = [rng.choices(keys, weights=[table[k] for k in keys])[0]]
    if rng.random() < SECOND:
        picks.append(rng.choices(keys, weights=[table[k] for k in keys])[0])
    return picks


def place(source, world, chunk, env: dict) -> List[str]:
    """Build the chunk's points of interest; returns the kinds that were placed. (Call inside `worldgen.seeded_rng`.)"""
    import settlements
    import urban
    if chunk.key == (0, 0) or urban.touches(source.floor_seed, chunk.key) or settlements.layout(source.floor_seed, chunk.key) is not None:
        return []
    import shafts
    import structures
    if chunk.key in structures.ruin_chunks(source.floor_seed) or shafts.structure(source.floor_seed, chunk.key).building is not None:
        return []
    biome = biomes.BIOMES[biomes.BIOME_IDS[int(env["biome"][CHUNK_W // 2, CHUNK_H // 2])]]
    built = []
    planet = getattr(source, "planet", None)
    for number, kind in enumerate(roll(source.floor_seed, chunk.key, biome)):
        rng = random.Random(mix_seed(source.floor_seed, chunk.key[0], chunk.key[1], 4402, number))
        if POIS[kind].build(Site(world, chunk, rng, planet, biome, source.floor_seed)):
            built.append(kind)
    return built
