"""Hovering: the walking path is faint and never lies over a tooltip; rock walls are things you can look at."""
import actions
import input_handlers as ih
import render_functions
from events import MouseMotion, Point
from ui_helpers import SESSION


def find_wall(engine, radius=15):
    world, p = engine.game_map, engine.player
    for r in range(2, radius):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if actions.is_rock_face(world, p.x + dx, p.y + dy) and world.is_visible(p.x + dx, p.y + dy):
                    return p.x + dx, p.y + dy
    return None


def hover(handler, x, y):
    sx, sy = handler.engine.camera.to_screen(x, y)
    handler.handle_events(MouseMotion(Point(sx, sy)))
    SESSION.draw(handler)


def test_rock_wall_is_named_and_has_a_tooltip(new_engine):
    spot = find_wall(new_engine)
    if spot is None:
        import pytest
        pytest.skip("no visible rock face at the start")
    new_engine.update_fov()
    names = render_functions.get_names_at_location(*spot, new_engine.game_map)
    assert names.endswith("wall")
    handler = ih.MainGameEventHandler(new_engine)
    SESSION.handlers = [handler]
    hover(handler, *spot)    # draws the tooltip without raising


def test_the_path_is_hidden_over_an_item_and_drawn_over_open_ground(new_engine, monkeypatch):
    import species as defs
    from items import Stuff
    steps = []
    monkeypatch.setattr(ih, "highlight_world", lambda *a, **k: steps.append(a[2:4]))
    p, world = new_engine.player, new_engine.game_map
    handler = ih.MainGameEventHandler(new_engine)
    SESSION.handlers = [handler]
    free = [(p.x + dx, p.y + 3) for dx in range(-3, 4) if world.is_walkable(p.x + dx, p.y + 3) and not world.is_blocked(p.x + dx, p.y + 3)]
    x, y = free[0]
    hover(handler, x, y)
    assert steps, "a path is drawn over open ground"
    material = new_engine.game_world.planet.materials[0][1]
    from crafting import make_piece
    world.add_entity(make_piece(defs.PIECE_STONE, material), x, y)
    steps.clear()
    hover(handler, x, y)
    assert not steps, "no path over an item: the tooltip is about the item"
