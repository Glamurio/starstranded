"""Layers (z-levels): deterministic stairs, caves, buildings, seeing down, building floors and stairs, saving."""
import numpy as np
import pytest

import actions
import exceptions
import shafts
import tile_types
from chunks import CHUNK_H, CHUNK_W, chunk_key, chunk_origin
from components import unit as units
from crafting import WoodenFloor, WoodenStairs, Branch


def _stairs(tiles, local):
    return int(tiles[local[0], local[1]]["stairs"])


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_every_link_has_matching_stairs_on_both_layers(seed):
    found = 0
    for kx in range(-3, 4):
        for ky in range(-3, 4):
            key = (kx, ky)
            x0, y0 = chunk_origin(key)
            for link in shafts.structure(seed, key).links:
                found += 1
                lx, ly = link.x - x0, link.y - y0
                assert 0 <= lx < CHUNK_W and 0 <= ly < CHUNK_H
                lower, upper = link.z, link.z + 1
                tiles = {z: (shafts.surface_layer(seed, key)[0] if z == 0 else
                             shafts.cave_layer(seed, z, key) if z < 0 else shafts.sky_layer(seed, z, key))
                         for z in (lower, upper)}
                assert _stairs(tiles[lower], (lx, ly)) == 1, (key, link)  # up on the lower layer
                assert _stairs(tiles[upper], (lx, ly)) == -1, (key, link)  # down on the upper layer
    assert found > 20


def test_layer_generation_is_pure():
    a = shafts.cave_layer(7, -1, (0, 0)).copy()
    shafts.clear_caches()
    assert np.array_equal(a, shafts.cave_layer(7, -1, (0, 0)))
    assert shafts.structure(7, (2, 1)) == shafts.structure.__wrapped__(7, (2, 1))


def test_start_chunk_has_an_entrance_8_to_20_tiles_from_the_spawn():
    for seed in range(1, 10):
        entrance = shafts.entrance_of(seed)
        spawn = shafts.start_point(seed)[0]
        assert entrance is not None and shafts.structure(seed, (0, 0)).building is None
        assert chunk_key(*entrance) == (0, 0)
        assert 1 <= max(abs(entrance[0] - spawn[0]), abs(entrance[1] - spawn[1])) <= 20


def test_stairs_are_connected_inside_caves():
    import tcod
    for seed in (1, 2, 3):
        for key in [(0, 0), (1, 0), (0, 1)]:
            x0, y0 = chunk_origin(key)
            for z in (-1, -2, -3):
                ups, downs = shafts.layer_stairs(shafts.structure(seed, key).links, z)
                tiles = shafts.cave_layer(seed, z, key)
                cost = tiles["walkable"].astype(np.int8)
                for x, y in ups + downs:
                    path = tcod.path.AStar(cost, diagonal=1).get_path(CHUNK_W // 2, CHUNK_H // 2, x - x0, y - y0)
                    assert path, (seed, key, z, (x, y))


def test_buildings_have_walls_a_door_and_open_air_above():
    seen = 0
    for kx in range(-4, 5):
        for ky in range(-4, 5):
            found = shafts.structure(3, (kx, ky))
            b = found.building
            if b is None:
                continue
            seen += 1
            key = (kx, ky)
            ground = shafts.surface_layer(3, key)[0]
            assert not ground["walkable"][b.x, b.y] and ground["walkable"][b.door]
            first = shafts.sky_layer(3, 1, key)
            assert not first["walkable"][b.x, b.y] and first["open"][b.x - 1, b.y - 1]
            assert first["walkable"][b.x + 1, b.y + 1] and not first["open"][b.x + 1, b.y + 1]
            assert shafts.sky_layer(3, b.floors + 1, key)["open"].all()
    assert seen > 5


def test_climbing_and_descending_round_trip(new_engine):
    e = new_engine
    surface = e.game_map
    rabbit = units.Animal()
    spot = surface.downstairs_location
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if surface.is_walkable(spot[0] + dx, spot[1] + dy) and not surface.is_blocked(spot[0] + dx, spot[1] + dy):
            surface.add_entity(rabbit, spot[0] + dx, spot[1] + dy)
            break
    e.player.place(*spot)
    actions.TakeStairsAction(e.player, -1).perform()
    assert e.game_map.z == -1 and rabbit.parent is None  # stored with its chunk
    actions.TakeStairsAction(e.player, 1).perform()
    assert e.game_map is surface and (e.player.x, e.player.y) == spot
    assert any(u.species == rabbit.species and (u.x, u.y) == (rabbit.x, rabbit.y) for u in surface.units)


def test_stairs_errors(new_engine):
    e = new_engine
    with pytest.raises(exceptions.Impossible):
        actions.TakeStairsAction(e.player).perform()  # not on stairs
    e.player.place(*e.game_map.downstairs_location)
    with pytest.raises(exceptions.Impossible):
        actions.TakeStairsAction(e.player, 1).perform()  # these only go down


def test_caves_are_dark_and_hold_selenites(new_engine):
    e = new_engine
    e.player.place(*e.game_map.downstairs_location)
    actions.TakeStairsAction(e.player).perform()
    cave = e.game_map
    assert cave.has_sky is False and cave.z == -1
    import lighting
    assert lighting.ambient_radius(cave, 72, e.config) == e.config.night_view_radius  # noon, still dark
    species = {u.species for u in cave.units if u is not e.player}
    assert species and "Selenite" in species


def test_open_tiles_show_the_layer_below(new_engine):
    from world import World
    e = new_engine
    key = next(k for k in ((x, y) for x in range(-6, 7) for y in range(-6, 7)) if shafts.structure(e.game_world.master_seed, k).building)
    b = shafts.structure(e.game_world.master_seed, key).building
    x0, y0 = chunk_origin(key)
    upper = e.game_world.world_at(1)
    upper.load_chunk(key)
    rect = (x0, y0, CHUNK_W, CHUNK_H)
    gfx = upper.region("light", rect)
    mask = upper.region("open", rect)
    assert mask[b.x - 1, b.y - 1] and not mask[b.x + 1, b.y + 1]
    upper._look_down(gfx, mask, rect)
    below = e.game_world.world_at(0).terrain_region("dark", rect)
    assert np.array_equal(gfx[b.x - 1, b.y - 1], below[b.x - 1, b.y - 1])  # the ground, dimmed


def _player_on_first_floor(e):
    seed = e.game_world.master_seed
    key = next(k for k in ((x, y) for x in range(-6, 7) for y in range(-6, 7)) if shafts.structure(seed, k).building)
    link = shafts.structure(seed, key).links[0]
    surface = e.game_map
    surface.load_chunk(chunk_key(link.x, link.y))
    e.player.place(link.x, link.y, surface)  # stairs up on the ground floor
    actions.TakeStairsAction(e.player, 1).perform()
    return key, shafts.structure(seed, key).building


def test_building_stairs_lead_up_into_the_room(new_engine):
    e = new_engine
    key, building = _player_on_first_floor(e)
    assert e.game_map.z == 1
    assert e.game_map.tile_at(e.player.x, e.player.y)["stairs"] == -1
    assert e.game_map.has_sky


def test_wooden_floor_is_built_on_open_air_only(new_engine):
    e = new_engine
    key, b = _player_on_first_floor(e)
    world = e.game_map
    x0, y0 = chunk_origin(key)
    e.player.place(x0 + b.x + 1, y0 + b.y + 1)  # inside the room, next to the wall
    outside = (x0 + b.x - 1, y0 + b.y)
    floor = WoodenFloor()
    assert floor.can_place_at(world, x0 + b.x + 2, y0 + b.y + 2)  # a room tile is not open air
    assert world.tile_at(*outside)["open"] and floor.can_place_at(world, *outside) is None
    floor.build(world, *outside)
    assert world.tile_at(*outside)["walkable"] and not world.tile_at(*outside)["open"]


def test_place_action_builds_a_floor_through_the_wall_gap(new_engine):
    e = new_engine
    key, b = _player_on_first_floor(e)
    world = e.game_map
    x0, y0 = chunk_origin(key)
    # stand on a wall-adjacent tile and build onto the open air next to the building's wall via the action
    world.set_tile(x0 + b.x, y0 + b.y + 3, tile_types.floor.get_array())  # a gap in the wall
    e.player.place(x0 + b.x, y0 + b.y + 3)
    item = WoodenFloor()
    e.player.inventory.add(item)
    actions.PlaceConstructableAction(e.player, item, x0 + b.x - 1, y0 + b.y + 3).perform()
    assert world.tile_at(x0 + b.x - 1, y0 + b.y + 3)["walkable"]
    assert item not in e.player.inventory.items
    with pytest.raises(exceptions.Impossible):
        actions.PlaceConstructableAction(e.player, WoodenFloor(), x0 + b.x + 1, y0 + b.y + 3).perform()


def test_wooden_stairs_connect_two_layers(new_engine):
    e = new_engine
    surface = e.game_map
    px, py = e.player.x, e.player.y
    for dx in (1, 2, 3):  # a free floor tile beside the player
        if surface.is_walkable(px + dx, py) and not surface.get_entities_at_location(px + dx, py, True):
            x, y = px + dx, py
            break
    # the layer above is open air there: stairs lead up to a lone landing
    stairs = WoodenStairs()
    assert stairs.can_place_at(surface, x, y) is None
    stairs.build(surface, x, y)
    assert surface.tile_at(x, y)["stairs"] == 1
    assert e.game_world.tile_on_layer(1, x, y)["stairs"] == -1
    e.player.place(x, y)
    actions.TakeStairsAction(e.player).perform()
    assert e.game_map.z == 1 and (e.player.x, e.player.y) == (x, y)
    actions.TakeStairsAction(e.player).perform()
    assert e.game_map is surface


def test_save_and_load_keeps_every_layer(new_engine, tmp_path):
    import setup_game
    e = new_engine
    e.player.place(*e.game_map.downstairs_location)
    actions.TakeStairsAction(e.player).perform()
    e.game_map.set_tile(e.player.x + 1, e.player.y, tile_types.built_floor.get_array())
    path = str(tmp_path / "s")
    e.save_as(path)
    loaded = setup_game.load_game(path)
    assert loaded.game_map.z == -1 and set(loaded.game_world.layers) == {0, -1}
    assert loaded.game_map.tile_at(e.player.x + 1, e.player.y)["light"]["sprite"] == tile_types.built_floor.sprite
    actions.TakeStairsAction(loaded.player, 1).perform()
    assert loaded.game_map.z == 0 and loaded.game_map.tile_at(loaded.player.x, loaded.player.y)["stairs"] == -1


def test_terrain_of_a_stored_layer_is_readable_without_loading(new_engine):
    e = new_engine
    surface = e.game_map
    here = surface.tile_at(e.player.x, e.player.y)
    pos = (e.player.x, e.player.y)
    e.player.place(*surface.downstairs_location)
    actions.TakeStairsAction(e.player).perform()
    assert not surface.chunks and surface.stored
    again = e.game_world.tile_on_layer(0, *pos)
    assert again["light"]["sprite"] == here["light"]["sprite"]


def test_the_view_never_leaves_the_players_layer(new_engine):
    """Single-player: what is on screen, under the cursor and targetable is the player's own layer; the only glimpse of another
    one is the dimmed terrain seen through open air (never creatures or items)."""
    e = new_engine
    gw = e.game_world
    e.player.place(*e.game_map.downstairs_location)
    for direction in (-1, 1):
        actions.TakeStairsAction(e.player, direction).perform()
        assert e.game_map is gw.world_at(gw.current_z) and e.player.parent is e.game_map
        assert e.game_map.z == gw.current_z
        assert [w for z, w in gw.layers.items() if z != gw.current_z and w.chunks] == []  # others are stored, not shown
