"""A planet creature in a cave chunk still shares the planet's species object after unloading and after a save."""
import numpy as np

import savegame
from test_review_fixes import new_game


def creature_in_cave(engine):
    game_world = engine.game_world
    unit = next(u for u in engine.game_map.units if getattr(u.kind, "key", "").startswith("planet:fauna:"))
    tiles = game_world.world_at(-1).terrain_tiles((0, 0))
    xs, ys = np.nonzero(tiles["walkable"])
    game_world.place_on_layer(unit, -1, int(xs[0]), int(ys[0]))
    return unit, game_world.world_at(-1)


def planet_creatures(world):
    return [u for u in world.units if getattr(u.kind, "key", "").startswith("planet:fauna:")]


def test_species_identity_survives_unloading_a_cave_chunk():
    engine = new_game()
    unit, cave = creature_in_cave(engine)
    for key in list(cave.chunks):
        if cave is not engine.game_map:
            cave.unload_chunk(key)
    for key in list(cave.stored):
        cave.load_chunk(key)
    creatures = planet_creatures(cave)
    assert creatures
    fauna = engine.game_world.planet.fauna
    assert all(any(c.kind is species for species in fauna) for c in creatures)


def test_species_identity_survives_save_and_load(tmp_path):
    engine = new_game()
    creature_in_cave(engine)
    cave = engine.game_world.world_at(-1)
    for key in list(cave.chunks):
        cave.unload_chunk(key)
    directory = str(tmp_path / "save")
    savegame.save_game(engine, directory)
    loaded = savegame.load_game(directory)
    cave2 = loaded.game_world.world_at(-1)
    for key in list(cave2.stored):
        cave2.load_chunk(key)
    creatures = planet_creatures(cave2)
    assert creatures
    fauna = loaded.game_world.planet.fauna
    assert all(any(c.kind is species for species in fauna) for c in creatures)
