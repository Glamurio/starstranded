"""AreaRangedAttackHandler draws a frame around the (2r+1) x (2r+1) affected area."""
import pytest

import g
from render_helpers import cell_has_color
import input_handlers
from input_handlers import area_frame_rect


@pytest.mark.parametrize("radius", [0, 1, 2, 3, 5])
def test_frame_encloses_the_whole_affected_area(radius):
    x, y = 20, 15
    fx, fy, w, h = area_frame_rect(x, y, radius)
    assert w == h == 2 * radius + 3
    # affected tiles: x-r .. x+r ; frame ring is one tile outside on every side
    assert fx == x - radius - 1 and fy == y - radius - 1
    assert fx + w - 1 == x + radius + 1 and fy + h - 1 == y + radius + 1
    # frame is centred on the cursor
    assert fx + (w - 1) / 2 == x and fy + (h - 1) / 2 == y


def test_old_formula_was_wrong_for_radius_3():
    # radius ** 2 == 9 wide vs the correct 2*3+3 == 9 coincides only at r=3 and is wrong elsewhere
    assert area_frame_rect(0, 0, 2)[2] == 7 != 2 ** 2
    assert area_frame_rect(0, 0, 1)[2] == 5 != 1 ** 2


def test_area_handler_on_render_draws_the_frame(small_world):
    e = small_world()
    handler = input_handlers.AreaRangedAttackHandler(e, radius=2, callback=lambda xy: None)
    g.handlers = [input_handlers.MainGameEventHandler(e), handler]
    e.mouse_location = (6, 5)
    g.draw(handler)  # must not raise
    x0, y0, w, h = area_frame_rect(6, 5, 2)
    corners = [(x0, y0), (x0 + w - 1, y0), (x0, y0 + h - 1), (x0 + w - 1, y0 + h - 1)]
    red = tuple(input_handlers.color.red)
    assert all(cell_has_color(g.canvas, cx, cy, red) for cx, cy in corners)
    centre_x, centre_y = 6, 5
    assert not cell_has_color(g.canvas, centre_x, centre_y, red)  # only the ring is drawn
