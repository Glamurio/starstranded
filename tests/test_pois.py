"""Points of interest: biome-weighted, deterministic, built from the region's own stuff, and never inhabited."""
import random

import pytest

import biomes
import pois

SEED = 11


def _world(seed=SEED):
    import setup_game
    from engine import Engine
    from worldgen import NoiseWorldSource
    from world import GameWorld, World
    engine = Engine(player=setup_game.create_player())
    engine.game_world = GameWorld(engine=engine, seed=5)
    source = NoiseWorldSource(seed)
    world = World(engine, source, floor=1, seed=seed)
    engine.game_map = world
    return source, world


def test_every_biome_poi_key_is_a_known_kind():
    for biome in biomes.BIOMES.values():
        assert set(biome.pois) <= set(pois.POIS), biome.key


def test_roll_is_pure_in_seed_chunk_and_biome():
    biome = biomes.BIOMES["plains"] if "plains" in biomes.BIOMES else next(iter(biomes.BIOMES.values()))
    a = [pois.roll(SEED, (x, y), biome) for x in range(-6, 6) for y in range(-6, 6)]
    b = [pois.roll(SEED, (x, y), biome) for x in range(-6, 6) for y in range(-6, 6)]
    assert a == b
    assert any(a) and not all(a)
    assert pois.roll(SEED + 1, (0, 1), biome) is not None


def test_a_biome_favours_its_own_kinds_and_a_city_has_no_wilderness_ones():
    for key, biome in biomes.BIOMES.items():
        table = pois.weights(biome)
        for kind, weight in biome.pois.items():
            assert table[kind] == weight
        if biome.urban is not None:
            assert all(w == 0 for k, w in table.items() if k not in biome.pois), key


@pytest.mark.parametrize("kind", sorted(pois.POIS))
def test_each_kind_builds_something_and_nobody_lives_there(kind):
    from components.unit import Unit
    from chunks import CHUNK_H, CHUNK_W
    source, world = _world()
    built, chunk, before = False, None, 0
    for key in [(4, 4), (4, 5), (5, 5), (3, 5), (6, 4), (2, 6), (7, 7), (-4, 5), (5, -4), (-6, -3)]:        # (regions are big; some chunks are all water or forest)
        chunk = world.load_chunk(key)
        for entity in list(chunk.entities):
            if not getattr(entity, "decal", False):
                world.remove_entity(entity)
        before = len(chunk.entities)
        for number in range(8):
            site = pois.Site(world, chunk, random.Random(number), source.planet, biomes.BIOMES[next(iter(biomes.BIOMES))], SEED)
            built = pois.POIS[kind].build(site) or built
        if built:
            break
    assert built
    assert len(chunk.entities) > before
    assert not [e for e in chunk.entities if isinstance(e, Unit) and e is not world.engine.player and getattr(e, "ai", None) is None and "settler" in str(getattr(e, "name", "")).lower()]


def test_place_skips_the_landing_chunk_and_is_repeatable():
    source, world = _world()
    env = __import__("shafts").environment(SEED, (0, 0))
    assert pois.place(source, world, world.load_chunk((0, 0)), env) == []
    built = {}
    for x in range(-8, 8):
        for y in range(-8, 8):
            if (x, y) == (0, 0):
                continue
            env = __import__("shafts").environment(SEED, (x, y))
            key = biomes.BIOME_IDS[int(env["biome"][35, 20])]
            built[(x, y)] = pois.roll(SEED, (x, y), biomes.BIOMES[key])
    assert any(v for v in built.values())
    assert built == {k: pois.roll(SEED, k, biomes.BIOMES[biomes.BIOME_IDS[int(__import__("shafts").environment(SEED, k)["biome"][35, 20])]]) for k in built}
