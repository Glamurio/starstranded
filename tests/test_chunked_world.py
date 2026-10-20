"""Phase 5 acceptance: the chunked world.

Walking across chunk borders in all four directions, seamless terrain at borders, entities keeping their identity
and state when they cross, save/load in the middle of the world, far chunks unloading and coming back with catch-up,
and identical regeneration of chunks from their seed.
"""
import dataclasses

import numpy as np
import pytest

import actions
import tile_types
from chunks import CHUNK_H, CHUNK_W, chebyshev, chunk_key, keys_around
from components.consumable import Meat
from animals import Animal
from config import GameConfig
from view import VIEW_H, VIEW_W
from index_helpers import assert_index_consistent
from simulation import steps_between
from worldgen import FlatWorldSource, NoiseWorldSource, generate_terrain, seeded_rng


def flat_engine(**config):
    """A player at (35, 20) on an endless open floor (no terrain or spawns to get in the way)."""
    import setup_game
    from engine import Engine
    from world import GameWorld, World
    engine = Engine(player=setup_game.create_player(), config=GameConfig(**config))
    engine.game_world = GameWorld(engine=engine, seed=1)
    world = World(engine, FlatWorldSource(), floor=1, seed=0)
    engine.game_map = world
    world.load_chunk((0, 0))
    engine.player.place(35, 20, world)
    world.update_tiers()
    engine.update_fov()
    return engine


def step(engine, dx, dy):
    p = engine.player
    actions.MovementAction(p, p.x + dx, p.y + dy, [(p.x + dx, p.y + dy)]).perform()


def assert_tiers(engine):
    world, config = engine.game_map, engine.config
    center = chunk_key(engine.player.x, engine.player.y)
    assert world.center_key() == center
    assert set(keys_around(center, config.load_radius)) <= set(world.chunks)
    assert all(chebyshev(key, center) <= config.unload_radius for key in world.chunks)
    assert not set(world.chunks) & set(world.stored)


def boxed_rabbit(world, x, y):
    """A rabbit walled in on its tile, so its AI cannot move it (upkeep still runs)."""
    rabbit = Animal()
    rabbit.place(x, y, world)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                world.set_tile(x + dx, y + dy, tile_types.wall.get_array())
    return rabbit


# ── walking ────────────────────────────────────────────────────────────────────────
def test_walking_across_borders_in_all_four_directions_loads_and_unloads_chunks():
    e = flat_engine()
    world, player = e.game_map, e.player
    visited = {chunk_key(player.x, player.y)}
    for (dx, dy), steps in [((1, 0), 3 * CHUNK_W), ((0, 1), 2 * CHUNK_H), ((-1, 0), 5 * CHUNK_W), ((0, -1), 4 * CHUNK_H)]:
        for _ in range(steps):
            before = (player.x, player.y)
            step(e, dx, dy)
            assert (player.x, player.y) == (before[0] + dx, before[1] + dy)
            assert player.parent is world and world.chunk_of(player) is world.chunks[chunk_key(player.x, player.y)]
            visited.add(chunk_key(player.x, player.y))
            assert_tiers(e)
        assert_index_consistent(world)
    assert {(3, 0), (3, 2), (-2, 2), (-2, -2)} <= visited
    assert world.unloads > 0 and world.stored  # far chunks were serialised away
    # one turn per step, plus the extra turns humans lose to walking in the dark (night aversion)
    assert e.game_world.current_time >= 3 * CHUNK_W + 2 * CHUNK_H + 5 * CHUNK_W + 4 * CHUNK_H


def test_camera_follows_and_mouse_maps_to_world_tiles():
    import input_handlers as ih
    from events import MouseMotion, Point
    e = flat_engine()
    for _ in range(100):
        step(e, 1, 0)
    camera = e.camera
    # the camera shows one whole page (a viewport-sized, grid-aligned screenful) and stays put while you walk inside it
    assert camera.x0 % VIEW_W == 0 and camera.y0 % VIEW_H == 0 and camera.contains(e.player.x, e.player.y)
    handler = ih.MainGameEventHandler(e)
    handler.handle_events(MouseMotion(Point(10, 5)))
    assert tuple(e.mouse_location) == camera.to_world(10, 5) == (camera.x0 + 10, camera.y0 + 5)
    handler.handle_events(MouseMotion(Point(VIEW_W + 5, 5)))  # side panel: not a map tile
    assert tuple(e.mouse_location) == (camera.x0 + 10, camera.y0 + 5)


def test_page_camera_flips_at_the_edge_and_not_before():
    e = flat_engine()
    first = e.camera
    start_x = e.player.x
    seen = {(first.x0, first.y0)}
    for _ in range(3 * VIEW_W):
        step(e, 1, 0)
        cam = e.camera
        assert cam.contains(e.player.x, e.player.y)
        if cam.x0 == first.x0:
            assert e.player.x < first.x0 + VIEW_W   # it only changes page when the player leaves it
        seen.add((cam.x0, cam.y0))
    assert len(seen) >= 3 and e.player.x > start_x


def test_units_cannot_step_into_unloaded_chunks():
    e = flat_engine(near_radius=1, sim_radius=1, unload_radius=1)
    world = e.game_map
    edge_x = 2 * CHUNK_W - 1  # last column of chunk (1, 0); chunk (2, 0) is not loaded
    assert world.in_bounds(edge_x, 20) and not world.in_bounds(edge_x + 1, 20)
    assert e.can_move(edge_x, 20) and not e.can_move(edge_x + 1, 20)


# ── seams ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("seed", [3, 11, 2024])
@pytest.mark.parametrize("neighbour", [(1, 0), (0, 1), (-1, 0), (0, -1)])
def test_terrain_is_continuous_across_chunk_borders(seed, neighbour, monkeypatch):
    """Two chunks generated separately agree with one generation of their union wherever the result does not depend
    on the chunk's RNG (trees and the random 'center' water variation). (Buildings and cave entrances are
    structures laid over the natural terrain and are switched off here.)"""
    import shafts
    from world import World
    import routes
    monkeypatch.setattr(shafts, "structure", lambda master, key: shafts.Structure())
    monkeypatch.setattr(routes, "paint", lambda *args: None)     # (and so are the planned paths)
    import settlements
    monkeypatch.setattr(settlements, "paint", lambda *args: None)  # (and the farms and towns)
    source = NoiseWorldSource(seed)
    world = World(None, source)
    keys = [(0, 0), neighbour]
    chunks = [source.generate(world, key) for key in keys]
    x0, y0 = min(k[0] for k in keys) * CHUNK_W, min(k[1] for k in keys) * CHUNK_H
    width = CHUNK_W * (1 + abs(neighbour[0]))
    height = CHUNK_H * (1 + abs(neighbour[1]))
    with seeded_rng(0):
        big, big_trees = generate_terrain(source.noise, x0, y0, width, height)
    stitched = np.empty_like(big)
    trees = np.zeros(big.shape, dtype=bool)
    for chunk in chunks:
        sx, sy = slice(chunk.x0 - x0, chunk.x0 - x0 + CHUNK_W), slice(chunk.y0 - y0, chunk.y0 - y0 + CHUNK_H)
        stitched[sx, sy] = chunk.tiles
        trees[sx, sy] = chunk.__dict__.get("pending_trees", np.zeros((CHUNK_W, CHUNK_H), bool))
    from procgen import neighbour_masks
    from worldgen import base_terrain
    kinds = base_terrain(source.noise, x0 - 2, y0 - 2, width + 4, height + 4)
    surrounded = np.zeros(kinds.shape, dtype=bool)
    for kind in (0, 2):  # water and walls pick their 'center' sprite at random when surrounded
        left, right, up, down = neighbour_masks(kinds == kind)
        surrounded |= (kinds == kind) & left & right & up & down
    surrounded = surrounded[2:-2, 2:-2]
    random_cells = (
        surrounded
        | (stitched["light"]["sprite"] == tile_types.down_stairs.sprite)
    )
    same = ~random_cells
    assert same.mean() > 0.3      # (seas and mountains are 'surrounded' too: their centre sprites are random)
    for field in ("walkable", "transparent"):
        assert np.array_equal(stitched[field][same], big[field][same]), field
    assert np.array_equal(stitched["light"]["sprite"][same], big["light"]["sprite"][same])
    # and specifically along the seam
    if neighbour[0]:
        seam = (slice(CHUNK_W - 2, CHUNK_W + 2), slice(None))
    else:
        seam = (slice(None), slice(CHUNK_H - 2, CHUNK_H + 2))
    assert np.array_equal(stitched["light"]["sprite"][seam][same[seam]], big["light"]["sprite"][seam][same[seam]])


def test_a_regenerated_chunk_is_identical():
    import setup_game
    from engine import Engine
    from world import GameWorld, World

    def make():
        engine = Engine(player=setup_game.create_player())
        engine.game_world = GameWorld(engine=engine, seed=5)
        world = World(engine, NoiseWorldSource(77), floor=1, seed=77)
        engine.game_map = world
        chunk = world.load_chunk((2, -1))
        entities = sorted(
            (e.x, e.y, type(e).__name__, e.species, e.shade, e.color, e.mirrored, e.name, getattr(e, "hp", None),
             getattr(e, "avg_cycle", None))
            for e in chunk.entities
        )
        return chunk.tiles.copy(), entities

    (tiles_a, entities_a), (tiles_b, entities_b) = make(), make()
    assert np.array_equal(tiles_a, tiles_b)
    assert entities_a == entities_b and len(entities_a) > 10


def test_generating_a_chunk_does_not_disturb_the_global_rng():
    import random
    from world import World
    source = NoiseWorldSource(9)
    random.seed(1)
    expected = random.random()
    random.seed(1)
    source.generate(World(None, source), (4, 4))
    assert random.random() == expected


# ── entities crossing borders ──────────────────────────────────────────────────────
def test_an_npc_crossing_a_border_keeps_identity_and_state():
    e = flat_engine()
    world = e.game_map
    rabbit = Animal()
    rabbit.place(CHUNK_W - 1, 20, world)
    rabbit.hunger, rabbit.hp = 42, 3
    meat = Meat("rabbit", rabbit.inventory)
    rabbit.inventory.add(meat)
    uid, ai = rabbit.uid, rabbit.ai
    old_chunk = world.chunk_of(rabbit)
    rabbit.move(CHUNK_W, 20)
    new_chunk = world.chunk_of(rabbit)
    assert old_chunk.key == (0, 0) and new_chunk.key == (1, 0)
    assert rabbit not in old_chunk.entities and rabbit in new_chunk.entities and rabbit in new_chunk.actors
    assert rabbit.uid == uid and rabbit.ai is ai and rabbit.hunger == 42 and rabbit.hp == 3
    assert rabbit.inventory.items == [meat] and meat.parent is rabbit.inventory
    assert world.get_unit_at_location(CHUNK_W, 20) is rabbit
    assert_index_consistent(world)


def test_ai_walks_an_npc_over_a_border(monkeypatch):
    """A NEAR-tier rabbit fleeing from the player walks from one chunk into the next (same object)."""
    e = flat_engine()
    world = e.game_map
    for _ in range(CHUNK_W - 35 - 3):  # player close to the east border of chunk (0, 0)
        step(e, 1, 0)
    rabbit = Animal()
    rabbit.place(CHUNK_W + 1, e.player.y, world)  # just across the border, in NEAR chunk (1, 0)
    rabbit_id = id(rabbit)
    for _ in range(30):
        actions.WaitAction(e.player).perform()
    assert id(world.get_entities_at_location(rabbit.x, rabbit.y)[0]) == rabbit_id
    assert rabbit.x > CHUNK_W + 1  # fled east, away from the player
    assert world.chunk_of(rabbit).key[0] >= 1


# ── tiers ──────────────────────────────────────────────────────────────────────────
def test_active_chunk_runs_every_turn_near_chunks_every_interval():
    e = flat_engine(near_interval=2)
    world = e.game_map
    active = boxed_rabbit(world, 20, 20)
    near = boxed_rabbit(world, CHUNK_W + 20, 20)
    seen = []
    for _ in range(4):
        actions.WaitAction(e.player).perform()
        seen.append((e.game_world.current_time, active.last_upkeep, near.last_upkeep))
    for now, active_upkeep, near_upkeep in seen:
        assert active_upkeep == now
        assert near_upkeep == (None if now < 2 else now if now % 2 == 0 else now - 1)


def test_far_entities_are_not_simulated_at_all():
    e = flat_engine(near_radius=1, sim_radius=1, unload_radius=3)
    world = e.game_map
    frozen = boxed_rabbit(world, 3 * CHUNK_W + 10, 20) if world.load_chunk((3, 0)) else None
    before = frozen.last_upkeep
    for _ in range(6):
        actions.WaitAction(e.player).perform()
    assert frozen.last_upkeep == before  # loaded (inside unload_radius) but beyond near_radius: frozen


# ── unload / reload with catch-up ──────────────────────────────────────────────────
def _away_and_back(e, key, turns):
    """Unload chunk `key` (as walking far away does), let `turns` pass, load it again; returns the time."""
    world = e.game_map
    world.unload_chunk(key)
    assert key in world.stored and key not in world.chunks
    for _ in range(turns):
        actions.WaitAction(e.player).perform()
    world.load_chunk(key)
    return e.game_world.current_time


def _into_chunk_1_0(e):
    for _ in range(CHUNK_W - 30):  # player into chunk (1, 0): (0, 0) becomes NEAR
        step(e, 1, 0)
    actions.WaitAction(e.player).perform()
    if e.game_world.current_time % 2:
        actions.WaitAction(e.player).perform()  # an even time, so the NEAR chunk is fully up to date


def test_far_chunks_unload_and_reload_with_catch_up():
    e = flat_engine()
    world = e.game_map
    rabbit = boxed_rabbit(world, 10, 10)
    _into_chunk_1_0(e)
    uid = rabbit.uid
    hunger, thirst, hp, last = rabbit.hunger, rabbit.thirst, rabbit.hp, rabbit.last_upkeep
    now = _away_and_back(e, (0, 0), 120)
    back = world.find_uid(uid)
    assert back is not None and back is not rabbit  # restored from bytes: same uid and state, new object
    assert back.last_upkeep == now
    assert back.hunger == max(0, hunger - steps_between(last, now, 4))
    assert back.thirst == max(0, thirst - steps_between(last, now, 2))
    assert back.hp == hp  # nothing reached zero in 120 turns
    assert_index_consistent(world)


def test_plants_grow_while_their_chunk_is_away():
    import random as _random
    import components.plant
    from species import PlantCategory, make_plant_species
    e = flat_engine()
    world = e.game_map
    species = next(s for s in (make_plant_species(PlantCategory.TREE, _random.Random(i)) for i in range(50)) if s.fruit)
    tree = components.plant.Tree(species)
    tree.place(12, 30, world)
    _into_chunk_1_0(e)
    uid, growth, count, last, cycle = tree.uid, tree.growth, len(tree.inventory.items), tree.last_upkeep, int(tree.avg_cycle) + 1
    now = _away_and_back(e, (0, 0), 90)
    back = world.find_uid(uid)
    cycles = (growth + steps_between(last, now, 2)) // cycle
    assert cycles >= 1
    assert len(back.inventory.items) == min(count + 2 * cycles, back.inventory.capacity)
    assert back.growth == (growth + steps_between(last, now, 2)) % cycle and back.last_upkeep == now


def test_long_absence_with_food_counts_as_foraging():
    from simulation import upkeep
    import components.plant
    from species import PlantCategory, make_plant_species
    import random as _random
    e = flat_engine()
    world = e.game_map
    rabbit = boxed_rabbit(world, 10, 10)
    rabbit.last_upkeep = 0
    upkeep(rabbit, 1000)
    assert rabbit.hp == 0 and not rabbit.is_alive  # no food anywhere: starved (quietly)
    species = next(s for s in (make_plant_species(PlantCategory.TREE, _random.Random(i)) for i in range(50)) if s.fruit)
    tree = components.plant.Tree(species)
    tree.place(20, 10, world)
    tree.inventory.add(components.plant.Fruit(tree.inventory, species.fruit))
    survivor = boxed_rabbit(world, 30, 30)
    survivor.last_upkeep = 0
    upkeep(survivor, 1000)
    assert survivor.is_alive and survivor.hunger == survivor.max_hunger // 2


# ── saves ──────────────────────────────────────────────────────────────────────────
def test_save_and_load_in_the_middle_of_the_world(tmp_path):
    import setup_game
    e = flat_engine()
    world = e.game_map
    for _ in range(3 * CHUNK_W):
        step(e, 1, 0)
    for _ in range(CHUNK_H + 5):
        step(e, 0, 1)
    rabbit = Animal()
    rabbit.place(e.player.x + 3, e.player.y, world)
    rabbit.hunger = 37
    rabbit.inventory.add(Meat("rabbit", rabbit.inventory))
    e.player.hp = 9
    e.message_log.add_message("deep in the world")
    stored_before = set(world.stored)
    assert stored_before
    path = str(tmp_path / "save")
    e.save_as(path)

    loaded = setup_game.load_game(path)
    lw = loaded.game_map
    assert (loaded.player.x, loaded.player.y) == (e.player.x, e.player.y) and loaded.player.hp == 9
    assert set(lw.chunks) == set(world.chunks)
    assert set(lw.stored) == stored_before  # far chunks are not loaded, only kept
    twin = lw.find_uid(rabbit.uid)
    assert twin.hunger in (36, 37) and len(twin.inventory.items) == 1 and twin.game_map is lw       # (a creature is brought up to date on loading, so a tick that falls on the save time may take one point)
    assert loaded.game_world.current_time == e.game_world.current_time
    assert loaded.message_log.messages[-1].plain_text == "deep in the world"
    assert_index_consistent(lw)
    # walking back to the start reloads stored chunks from the save
    for _ in range(3 * CHUNK_W):
        step(loaded, -1, 0)
    assert (0, 1) in lw.chunks or (0, 0) in lw.chunks

    # saving again only rewrites what changed and removes files that are no longer referenced
    loaded.save_as(path)
    files = list((tmp_path / "save").rglob("chunk_*.zlib"))
    keys = {f.name.split(".")[0] for f in files}
    assert len(files) == len(keys)  # one file per chunk, old generations deleted


def test_unvisited_chunks_are_never_written(tmp_path):
    e = flat_engine()
    path = tmp_path / "s"
    e.save_as(str(path))
    names = {f.name.split(".")[0] for f in (path / "layer0").iterdir()}
    assert names == {f"chunk_{kx}_{ky}" for kx, ky in e.game_map.chunks}


# ── floors ─────────────────────────────────────────────────────────────────────────
def test_taking_the_stairs_goes_down_into_a_cave_layer(new_engine):
    e = new_engine
    first = e.game_map
    e.player.place(*first.downstairs_location)
    actions.TakeStairsAction(e.player).perform()
    second = e.game_map
    assert second is not first and second.z == -1 and e.game_world.current_z == -1
    assert second.floor == 2 and e.game_world.current_floor == 2
    assert e.player.parent is second and (e.player.x, e.player.y) == first.downstairs_location
    assert second.tile_at(e.player.x, e.player.y)["stairs"] == 1  # arrives on the staircase back up
    assert second.seed != first.seed and not first.chunks
