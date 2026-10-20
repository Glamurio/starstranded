"""The world map (M): what is recorded, that it only shows what was seen, that it never generates terrain, and that it
fits any window."""
import pickle

import numpy as np
import pygame

import screens
import worldmap
from test_lore import new_game
from ui_helpers import SESSION


def _canvas(width, height):
    import ui
    return ui.Canvas(pygame.Surface((width, height)), SESSION.canvas.font)


def test_only_explored_chunks_are_recorded():
    engine = new_game()
    engine.update_fov()
    known = worldmap.records(engine.game_world.run)
    assert known
    world = engine.game_map
    for key, info in known.items():
        chunk = world.chunks[key]
        assert chunk.explored.any() and info.seen == int(chunk.explored.sum())
    unexplored = [k for k, c in world.chunks.items() if not c.explored.any()]
    assert not set(unexplored) & set(known)


def test_the_record_grows_with_exploring_and_never_shrinks():
    engine = new_game()
    engine.update_fov()
    key = (engine.player.x // 70, engine.player.y // 40)
    before = worldmap.records(engine.game_world.run)[key]
    chunk = engine.game_map.chunks[key]
    chunk.explored[:] = True
    engine.update_fov()
    after = worldmap.records(engine.game_world.run)[key]
    assert after.seen == 70 * 40 > before.seen
    chunk.explored[:] = False
    engine.update_fov()
    assert worldmap.records(engine.game_world.run)[key].seen == 70 * 40


def test_drawing_the_map_never_generates_terrain(monkeypatch):
    import worldgen
    engine = new_game()
    engine.update_fov()
    world = engine.game_map
    loads = world.loads

    def forbidden(*args, **kwargs):
        raise AssertionError("the map must not generate terrain")

    monkeypatch.setattr(worldgen, "generate_terrain", forbidden)
    monkeypatch.setattr(worldgen, "chunk_environment", forbidden)
    handler = screens.WorldMapHandler(engine)
    handler.cursor = (40, -30)        # far from anything known
    SESSION.draw(handler)
    assert world.loads == loads
    assert handler.cursor == (40, -30)


def test_the_map_fits_small_and_large_windows():
    engine = new_game()
    engine.update_fov()
    for size in ((640, 360), (1280, 720), (1920, 1080), (480, 480), (2560, 1000)):
        canvas = _canvas(*size)
        handler = screens.WorldMapHandler(engine)
        handler.on_render(canvas)
        area, cell, kx0, ky0 = handler._geometry
        assert canvas.surface.get_rect().contains(area)
        assert 3 <= cell <= 32


def test_cell_size_fits_the_known_world():
    assert worldmap.fit_cell(10, 10, 400, 400) == 32
    assert worldmap.fit_cell(100, 50, 400, 400) == 4
    assert worldmap.fit_cell(40, 20, 400, 400) == 10


def test_cursor_zoom_and_home_keys():
    import events
    engine = new_game()
    handler = screens.WorldMapHandler(engine)
    home = handler.cursor
    handler.ev_keydown(events.KeyDown(events.Key.RIGHT, 0))
    assert handler.cursor == (home[0] + 1, home[1])
    handler.ev_keydown(events.KeyDown(events.Key.HOME, 0))
    assert handler.cursor == home
    SESSION.draw(handler)
    handler.ev_keydown(events.KeyDown(events.Key.PLUS, 0))
    assert handler.zoom and handler.zoom >= 3
    SESSION.draw(handler)


def test_the_map_survives_a_save():
    engine = new_game()
    engine.update_fov()
    known = worldmap.records(engine.game_world.run)
    again = pickle.loads(pickle.dumps(engine.game_world.run))
    assert again.flags["map"] == known


def test_an_old_save_without_a_map_starts_an_empty_one():
    engine = new_game()
    engine.game_world.run.flags.pop("map", None)
    assert worldmap.records(engine.game_world.run) == {}
    SESSION.draw(screens.WorldMapHandler(engine))


def test_left_click_travel_crosses_chunk_edges_and_corners(new_engine):
    """Walking by clicking a far tile carries on over a chunk border, also over the corner between four chunks."""
    import actions
    import debug
    import input_handlers as ih
    import tile_types
    from chunks import CHUNK_H, CHUNK_W
    engine = new_engine
    world, player = engine.game_map, engine.player
    debug.teleport(engine, CHUNK_W - 6, CHUNK_H - 6)
    for key in ((0, 0), (1, 0), (0, 1), (1, 1)):
        world.load_chunk(key)
    for unit in list(world.units):
        if unit is not player:
            world.remove_entity(unit)
    for x in range(CHUNK_W - 10, CHUNK_W + 10):
        for y in range(CHUNK_H - 10, CHUNK_H + 10):
            for entity in list(world.get_entities_at_location(x, y)):
                if entity is not player:
                    world.remove_entity(entity)
            world.set_tile(x, y, tile_types.floor.get_array())
    engine.update_fov()
    target = (CHUNK_W + 5, CHUNK_H + 5)
    handler = ih.MainGameEventHandler(engine)
    engine.session.reset(handler)
    handler.handle_action(actions.BumpAction(player, *target))
    assert (player.x, player.y) == target


def test_chunk_borders_agree_with_a_region_generated_across_them():
    """Terrain shape (walkable, liquid, depth, open) of a chunk next to its neighbour equals the same tiles generated as one
    wider rectangle: no gaps or conflicts at the shared borders, whatever the seed."""
    import worldgen
    from chunks import CHUNK_H, CHUNK_W
    for seed in (3, 1234):
        noise = worldgen.TerrainNoise(seed)
        for kx, ky in ((0, 0), (4, -3), (-7, 5)):
            x0, y0 = kx * CHUNK_W, ky * CHUNK_H
            wide, _ = worldgen.generate_terrain(noise, x0, y0, 2 * CHUNK_W, 2 * CHUNK_H)
            for ox, oy in ((0, 0), (CHUNK_W, 0), (0, CHUNK_H), (CHUNK_W, CHUNK_H)):
                one, _ = worldgen.generate_terrain(noise, x0 + ox, y0 + oy, CHUNK_W, CHUNK_H)
                part = wide[ox:ox + CHUNK_W, oy:oy + CHUNK_H]
                for field in ("walkable", "liquid", "depth", "open"):
                    assert np.array_equal(one[field], part[field]), (seed, kx, ky, ox, oy, field)


def test_player_built_bridge_grows_from_the_bank_and_can_be_walked(new_engine):
    import tile_types
    from crafting import WoodenFloor
    from test_turn_flow import quiet_corridor
    engine = new_engine
    quiet_corridor(engine)
    world, player = engine.game_map, engine.player
    for dx in (1, 2, 3):
        for dy in (-1, 0, 1):
            world.set_tile(player.x + dx, player.y + dy, tile_types.water.get_array())
            world.modify_tile(player.x + dx, player.y + dy, liquid=1, depth=2, walkable=False)
    floor = WoodenFloor()
    assert floor.can_place_at(world, player.x + 2, player.y)            # (next to water, not to land)
    assert floor.can_place_at(world, player.x + 1, player.y) is None
    floor.build(world, player.x + 1, player.y)
    assert world.is_walkable(player.x + 1, player.y)
    assert floor.can_place_at(world, player.x + 2, player.y) is None     # now it touches a plank
    floor.build(world, player.x + 2, player.y)
    floor.build(world, player.x + 3, player.y)
    path = engine.get_path_to(player, player.x + 4, player.y)
    assert path and path[-1] == (player.x + 4, player.y)                 # pathfinding crosses it
    assert tile_types.is_laid(world.tile_at(player.x + 2, player.y)[None])[0]


def test_no_bridge_over_lava(new_engine):
    import liquids
    import tile_types
    from crafting import WoodenFloor
    from test_turn_flow import quiet_corridor
    engine = new_engine
    quiet_corridor(engine)
    world, player = engine.game_map, engine.player
    world.set_tile(player.x + 1, player.y, tile_types.water.get_array())
    world.modify_tile(player.x + 1, player.y, liquid=int(liquids.LiquidKind.LAVA), depth=3, walkable=False)
    assert "molten" in WoodenFloor().can_place_at(world, player.x + 1, player.y)


def test_known_places_come_with_their_world_sprites_and_the_map_draws_them_as_icons():
    import species as defs
    engine = new_game()
    engine.update_fov()
    run = engine.game_world.run
    run.wreck = (engine.player.x + 3, engine.player.y)
    run.pod = (engine.player.x + 5, engine.player.y)
    run.flags["sites"] = {0: (engine.player.x + 7, engine.player.y), 3: (engine.player.x + 9, engine.player.y)}
    places = {name: sprite for name, _, _, sprite in screens.known_places(engine)}
    assert places["Your ship"] == defs.SHIP.sprite and places["Sponsor cargo pod"] == defs.CARGO_POD.sprite
    handler = screens.WorldMapHandler(engine)
    handler.zoom = 24
    canvas = _canvas(1280, 720)
    handler.on_render(canvas)                                    # (an icon is blitted, not just a square: drawing must not fail)
    area, cell, kx0, ky0 = handler._geometry
    assert cell == 24


def test_every_seen_block_of_a_chunk_has_a_picture():
    engine = new_game()
    engine.update_fov()
    known = worldmap.records(engine.game_world.run)
    seen_blocks = 0
    for key, info in known.items():
        assert len(info.blocks) == worldmap.BLOCKS_X * worldmap.BLOCKS_Y
        chunk = engine.game_map.chunks[key]
        for index, block in enumerate(info.blocks):
            bx, by = index % worldmap.BLOCKS_X, index // worldmap.BLOCKS_X
            seen = chunk.explored[bx * worldmap.BLOCK:(bx + 1) * worldmap.BLOCK, by * worldmap.BLOCK:(by + 1) * worldmap.BLOCK].any()
            assert (block is not None) == bool(seen)       # (a block is drawn exactly when part of it was seen)
            if block is not None:
                sprite, fg, bg = block
                assert sprite >= 0 and len(fg) == 3 and len(bg) == 3
                seen_blocks += 1
    assert seen_blocks


def test_a_block_shows_what_stands_in_it():
    engine = new_game()
    chunk = next(iter(engine.game_map.chunks.values()))
    chunk.explored[:] = True
    chunk.tiles["depth"][:] = 0
    chunk.tiles["depth"][:worldmap.BLOCK, :worldmap.BLOCK] = 2           # the first block is a pond
    blocks = worldmap._blocks(chunk)
    water_sprite = int(chunk.tiles["light"]["sprite"][0, 0])
    assert blocks[0][0] == water_sprite
    from entity import EntityCategory
    trees = [p for p in chunk.by_category[EntityCategory.PLANT] if p.kind.category.name == "TREE"]
    assert all(b is not None for b in blocks)
    assert trees        # (the fixture world grows trees: some block shows one)
    shown = {b[0] for b in blocks}
    assert any(t.sprite_id in shown for t in trees)


def test_the_map_draws_pictures_at_every_zoom_and_old_records_still_draw():
    engine = new_game()
    engine.update_fov()
    run = engine.game_world.run
    known = worldmap.records(run)
    for zoom in (3, 6, 8, 16, 24, 40):
        handler = screens.WorldMapHandler(engine)
        handler.zoom = zoom
        handler.on_render(_canvas(1280, 720))
    old = {k: worldmap.Known(v.seen, v.color, v.water, v.rock, v.biome) for k, v in known.items()}
    run.flags["map"] = old
    assert all(v.blocks == () for v in old.values())
    screens.WorldMapHandler(engine).on_render(_canvas(1280, 720))


def test_block_size_fits_the_known_world():
    assert worldmap.fit_block(1, 1, 4000, 4000) == 24
    assert worldmap.fit_block(100, 100, 400, 400) == 3
    size = worldmap.fit_block(6, 4, 1000, 800)
    assert 6 * worldmap.BLOCKS_X * size <= 1000 and 4 * worldmap.BLOCKS_Y * size <= 800
