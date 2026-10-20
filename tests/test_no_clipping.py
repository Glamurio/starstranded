"""Nothing clips into anything: over real generated chunks (random ones, and the ones round a city, farms and points of interest),
no plant stands on rock, wall or water, no two things share a tile, and only a creature may stand on a piece of scenery."""
import collections
import random

import pytest

import setup_game
from components.plant import Plant
from components.unit import Unit
from crafting import Wall
from engine import Engine
from scenery import Scenery
from world import GameWorld, World
from worldgen import NoiseWorldSource

CHUNKS_PER_SEED = 45


def _loaded(seed, keys):
    engine = Engine(player=setup_game.create_player())
    engine.game_world = GameWorld(engine=engine, seed=5)
    world = World(engine, NoiseWorldSource(seed), floor=1, seed=seed)
    engine.game_map = world
    for key in keys:
        world.load_chunk(key)
    return world


def _problems(world, keys):
    found = collections.Counter()
    where = {}

    def note(what, at):
        found[what] += 1
        where.setdefault(what, at)

    for key in keys:
        cells = collections.defaultdict(list)
        for e in world.chunks[key].entities:
            if not getattr(e, "decal", False):
                cells[(e.x, e.y)].append(e)
        for (x, y), things in cells.items():
            tile = world.tile_at(x, y)
            walkable, wet = bool(tile["walkable"]), int(tile["liquid"])
            for e in things:
                name = type(e).__name__
                dry_ground = (e._ground[0] if getattr(e, "_ground", None) else walkable) if isinstance(e, Plant) else walkable
                if not dry_ground and not isinstance(e, Wall):
                    note(f"{name} on rock or wall", (x, y))
                if wet and isinstance(e, (Plant, Scenery)) and not getattr(getattr(e, "species", None), "aquatic", False):
                    note(f"{name} in water", (x, y))
            solid = [e for e in things if not isinstance(e, Scenery)]
            if len(solid) > 1:
                note("shared tile: " + " + ".join(sorted(type(e).__name__ for e in solid)), (x, y))
            if len(solid) != len(things) and any(not isinstance(e, Unit) for e in solid):
                note("scenery under " + " + ".join(sorted(type(e).__name__ for e in solid)), (x, y))
    return found, where


@pytest.mark.parametrize("seed", [3, 7, 12])
def test_random_chunks_have_nothing_clipping(seed):
    rng = random.Random(seed)
    keys = list({(rng.randint(-40, 40), rng.randint(-25, 25)) for _ in range(CHUNKS_PER_SEED)})
    world = _loaded(seed, keys)
    found, where = _problems(world, keys)
    assert not found, {k: (v, where[k]) for k, v in found.items()}


def test_the_chunks_round_a_city_hold_nothing_clipping():
    keys = [(x, y) for x in range(-9, -2) for y in range(-3, 2)]       # the abandoned district of seed 7 and its edges
    world = _loaded(7, keys)
    found, where = _problems(world, keys)
    assert not found, {k: (v, where[k]) for k, v in found.items()}


def test_farms_hamlets_ruins_and_points_of_interest_hold_nothing_clipping():
    import biomes
    import pois
    import regions
    import settlements
    import structures
    import shafts
    seed = 7
    noise = shafts.terrain_noise(seed)
    farms, hamlets, sites = [], [], []
    for cx in range(-30, 30):
        for cy in range(-20, 20):
            key = (cx, cy)
            kind = settlements.kind_of(seed, key)
            if kind == "farm":
                farms.append(key)
            elif kind == "town":
                hamlets.append(key)
            elif pois.roll(seed, key, biomes.BIOMES[regions.biome_at(noise, cx * 70 + 35, cy * 40 + 20)]):
                sites.append(key)
    keys = farms[:6] + hamlets[:6] + sites[:14] + list(structures.ruin_chunks(seed))[:4] + [(0, 0)]
    assert len(keys) > 20
    world = _loaded(seed, keys)
    found, where = _problems(world, keys)
    assert not found, {k: (v, where[k]) for k, v in found.items()}
