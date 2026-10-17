"""Characterization: Engine.get_path_to on small fixed grids."""
import tile_types


def wall_line(engine, x, y0, y1):
    for y in range(y0, y1 + 1):
        engine.game_map.tiles[x, y] = tile_types.wall.get_array()


def test_path_excludes_start_includes_destination(small_world):
    e = small_world()
    p = e.player
    path = e.get_path_to(p.ai, 4, 1)
    assert path[0] != (1, 1) and path[-1] == (4, 1)
    assert len(path) == 3


def test_diagonal_path_is_shorter_in_steps(small_world):
    e = small_world()
    path = e.get_path_to(e.player.ai, 5, 5)
    assert path[-1] == (5, 5) and len(path) == 4


def test_path_routes_around_wall(small_world):
    e = small_world(width=12, height=10)
    wall_line(e, 4, 0, 6)  # gap at y=7..9
    path = e.get_path_to(e.player.ai, 8, 1)
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
    path = e.get_path_to(e.player.ai, 8, 5)
    assert path == []


def test_out_of_bounds_returns_empty_list(small_world):
    e = small_world()
    for dest in [(99, 99), (-1, 0), (0, -1), (12, 5), (5, 10)]:
        assert e.get_path_to(e.player.ai, *dest) == []


def test_main_handler_renders_with_cursor_out_of_bounds(small_world):
    """The hover-path preview iterates get_path_to()'s result; it must not crash for [] ."""
    import g
    import input_handlers
    e = small_world()
    handler = input_handlers.MainGameEventHandler(e)
    handler.mouse_motion = True
    e.mouse_location = (99, 99)
    g.root_console.clear()
    handler.on_render(g.root_console)


def test_unexplored_terrain_is_treated_as_walkable(small_world):
    e = small_world()
    wall_line(e, 4, 0, 9)  # full wall ...
    e.game_map.explored[:] = False  # ... but unexplored: the pathfinder must not "know" about it
    path = e.get_path_to(e.player.ai, 8, 1)
    assert path and path[-1] == (8, 1)


def test_blocking_entities_add_cost_and_are_detoured(small_world):
    from components.unit import Animal
    e = small_world()
    for y in range(0, 10):
        if y != 1:
            e.game_map.tiles[4, y] = tile_types.wall.get_array()
    blocker = Animal(); blocker.ai = None; blocker.place(4, 1, e.game_map)
    path = e.get_path_to(e.player.ai, 8, 1)
    assert (4, 1) in path  # only gap; cost +10 but still the route
    path_ignore = e.get_path_to(e.player.ai, 8, 1, ignore_obstacles=True)
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
