"""Characterization: Engine.get_path_to on small fixed grids."""
import tile_types


def wall_line(engine, x, y0, y1):
    for y in range(y0, y1 + 1):
        engine.game_map.tiles[x, y] = tile_types.wall.get_array()


def test_path_excludes_start_includes_destination(small_world):
    e = small_world()
    p = e.player
    path = e.get_path_to(p, 4, 1)
    assert path[0] != (1, 1) and path[-1] == (4, 1)
    assert len(path) == 3


def test_diagonal_path_is_shorter_in_steps(small_world):
    e = small_world()
    path = e.get_path_to(e.player, 5, 5)
    assert path[-1] == (5, 5) and len(path) == 4


def test_path_routes_around_wall(small_world):
    e = small_world(width=12, height=10)
    wall_line(e, 4, 0, 6)  # gap at y=7..9
    path = e.get_path_to(e.player, 8, 1)
    assert path[-1] == (8, 1)
    assert all(e.game_map.tiles["walkable"][x, y] for x, y in path)
    assert any(y >= 7 for _, y in path)


def test_path_is_empty_when_destination_enclosed(small_world):
    e = small_world()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx, dy) != (0, 0):
                e.game_map.tiles[8 + dx, 5 + dy] = tile_types.wall.get_array()
    # destination itself walkable but unreachable
    path = e.get_path_to(e.player, 8, 5)
    assert path == []


def test_out_of_bounds_returns_empty_list(small_world):
    e = small_world()
    for dest in [(99, 99), (-1, 0), (0, -1), (12, 5), (5, 10)]:
        assert e.get_path_to(e.player, *dest) == []


def test_main_handler_renders_with_cursor_out_of_bounds(small_world):
    """The hover-path preview iterates get_path_to()'s result; it must not crash for [] ."""
    import g
    import input_handlers
    e = small_world()
    handler = input_handlers.MainGameEventHandler(e)
    handler.mouse_motion = True
    e.mouse_location = (99, 99)
    g.draw(handler)


def test_unexplored_terrain_is_treated_as_walkable(small_world):
    e = small_world()
    wall_line(e, 4, 0, 9)  # full wall ...
    e.game_map.explored[:] = False  # ... but unexplored: the pathfinder must not "know" about it
    path = e.get_path_to(e.player, 8, 1)
    assert path and path[-1] == (8, 1)


def test_blocking_entities_add_cost_and_are_detoured(small_world):
    from components.unit import Animal
    e = small_world()
    for y in range(0, 10):
        if y != 1:
            e.game_map.tiles[4, y] = tile_types.wall.get_array()
    blocker = Animal(); blocker.ai = None; blocker.place(4, 1, e.game_map)
    path = e.get_path_to(e.player, 8, 1)
    assert (4, 1) in path  # only gap; cost +10 but still the route
    path_ignore = e.get_path_to(e.player, 8, 1, ignore_obstacles=True)
    assert (4, 1) in path_ignore


def test_can_move_rules(small_world):
    e = small_world()
    assert e.can_move(2, 1)
    assert not e.can_move(-1, 0)
    e.game_map.tiles[2, 1] = tile_types.wall.get_array()
    assert not e.can_move(2, 1)


def test_distance_helpers(small_world):
    e = small_world()
    assert e.distance((0, 0), (3, 4)) == 4  # Chebyshev by default
    assert abs(e.distance((0, 0), (3, 4), diag=False, euclidean=True) - 5.0) < 1e-9
    # BUG-ish (noted in notes): manhattan branch compares p1 with p1 -> always 0
    assert e.distance((0, 0), (3, 4), diag=False) == 0


def _old_get_path_to(engine, origin, dest_x, dest_y, ignore_obstacles=False):
    """The pre-Phase-2 implementation (per-call cost rebuild + loop over all entities), kept as a reference."""
    import numpy as np
    import tcod
    gm = origin.game_map
    if not gm.in_bounds(dest_x, dest_y):
        return []
    walkable = np.array(gm.tiles["walkable"])
    cost = np.logical_or(walkable, np.logical_not(gm.explored)).astype(int)
    for entity in gm.entities:
        if not ignore_obstacles and entity.blocks_movement and cost[entity.x, entity.y]:
            cost[entity.x, entity.y] += 10
    pf = tcod.path.Pathfinder(tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3))
    pf.add_root((origin.x, origin.y))
    return [tuple(p) for p in pf.path_to((dest_x, dest_y))[1:].tolist()]


def test_new_pathfinding_returns_exactly_the_old_paths(small_world):
    """On a bounded 70x40 map with an unlimited search radius the window-based search equals the old whole-map one."""
    import dataclasses
    import random
    import numpy as np
    from components.unit import Animal
    for seed in range(3):
        random.seed(seed)
        np.random.seed(seed)
        e = small_world(70, 40)
        e.config = dataclasses.replace(e.config, path_radius=100)
        m = e.game_map
        walls = np.random.rand(70, 40) < 0.3
        walls[1, 1] = False
        m.tiles[walls] = tile_types.wall.get_array()
        m.explored[:] = np.random.rand(*m.explored.shape) < 0.8
        for _ in range(40):
            x, y = random.randrange(m.width), random.randrange(m.height)
            if e.can_move(x, y):
                Animal().place(x, y, m)
        units = list(m.units)
        for _ in range(150):
            origin = random.choice(units)
            dest = (random.randrange(m.width), random.randrange(m.height))
            for ignore in (False, True):
                assert e.get_path_to(origin, *dest, ignore_obstacles=ignore) == _old_get_path_to(
                    e, origin, *dest, ignore_obstacles=ignore)


def test_paths_follow_terrain_and_exploration_changes(small_world):
    e = small_world()
    m = e.game_map
    wall_line(e, 4, 0, 9)
    assert e.get_path_to(e.player, 8, 1) == []  # a known wall blocks
    m.explored[4, 5] = False
    path = e.get_path_to(e.player, 8, 1)
    assert (4, 5) in path  # an unexplored gap counts as walkable
    window_before = m.window.rebuilds
    m.modify_tile(4, 5, walkable=True)
    m.explored[4, 5] = True
    assert (4, 5) in e.get_path_to(e.player, 8, 1)
    assert m.window.rebuilds == window_before + 1  # the terrain change invalidated the stitched window


def test_destinations_beyond_the_search_radius_get_no_path(small_world):
    import dataclasses
    e = small_world(70, 40)
    e.config = dataclasses.replace(e.config, path_radius=10)
    assert e.get_path_to(e.player, 11, 1) != []
    assert e.get_path_to(e.player, 12, 1) == []
