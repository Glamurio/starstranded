"""Houses and buildings are walled with wall entities of the construction system, and settlements sit near the middle of their chunk."""
import numpy as np

import settlements
import shafts
from chunks import CHUNK_H, CHUNK_W
from crafting import Wall
from test_settlements import SEED, KEYS, _load, found


def test_a_town_house_is_walled_with_wall_entities_not_rock_tiles():
    key, world, chunk = _load("town")
    lay = settlements.layout(SEED, key)
    walls = {(e.x - chunk.x0, e.y - chunk.y0): e for e in chunk.entities if isinstance(e, Wall)}
    for house in lay.houses:
        for tile in settlements._wall_tiles(house):
            assert tile in walls and not world.is_walkable(chunk.x0 + tile[0], chunk.y0 + tile[1])
        assert world.is_walkable(chunk.x0 + house.door[0], chunk.y0 + house.door[1])
    assert all(e.max_hp > 0 and e.material is not None for e in walls.values())
    first = walls[settlements._wall_tiles(lay.houses[0])[0]]
    first.handle_health(-first.max_hp)                                   # a wall can be broken down like a built one
    assert world.is_walkable(first.x, first.y)


def test_settlements_sit_near_the_middle_of_their_chunk():
    for kind in ("farm", "town"):
        for key, lay in found(kind)[:10]:
            xs = [h.x for h in lay.houses] + [h.x + h.w for h in lay.houses]
            ys = [h.y for h in lay.houses] + [h.y + h.h for h in lay.houses]
            if kind == "farm":
                fx, fy, fw, fh = lay.fence
                xs += [fx, fx + fw]
                ys += [fy, fy + fh]
            assert abs((min(xs) + max(xs)) / 2 - CHUNK_W / 2) <= 5, (kind, key)
            assert abs((min(ys) + max(ys)) / 2 - CHUNK_H / 2) <= 5, (kind, key)


def test_buildings_sit_near_the_middle_of_their_chunk():
    seen = 0
    for kx in range(-6, 7):
        for ky in range(-6, 7):
            b = shafts.structure(SEED, (kx, ky)).building
            if b is not None:
                seen += 1
                assert abs(b.x + b.w / 2 - CHUNK_W / 2) <= 5 and abs(b.y + b.h / 2 - CHUNK_H / 2) <= 5
    assert seen


def test_no_tree_grows_on_solid_rock():
    for key in [(i, j) for i in range(-3, 4) for j in range(-3, 4)]:
        tiles, trees = shafts.raw_surface(SEED, key)
        assert not (trees & ~tiles["walkable"]).any()


def test_a_building_has_wall_entities_on_every_floor_and_a_free_door():
    import setup_game
    from engine import Engine
    from worldgen import NoiseWorldSource, SkySource
    from world import GameWorld, World
    key = next(k for k in KEYS if k != (0, 0) and shafts.structure(SEED, k).building is not None)
    b = shafts.structure(SEED, key).building
    engine = Engine(player=setup_game.create_player())
    engine.game_world = GameWorld(engine=engine, seed=5)
    ground = World(engine, NoiseWorldSource(SEED), floor=1, seed=SEED)
    engine.game_map = ground
    chunk = ground.load_chunk(key)
    x0, y0 = chunk.x0, chunk.y0
    assert isinstance(next(e for e in ground.get_entities_at_location(x0 + b.x, y0 + b.y) if isinstance(e, Wall)), Wall)
    assert ground.is_walkable(x0 + b.door[0], y0 + b.door[1])
    sky = World(engine, SkySource(SEED, 1), floor=1, seed=SEED, z=1)
    upper = sky.load_chunk(key)
    assert any(isinstance(e, Wall) and (e.x, e.y) == (x0 + b.x, y0 + b.y) for e in upper.entities)
