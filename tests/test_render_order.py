"""GameMap draws entities bucketed by RenderOrder (no per-frame sort); later layers overwrite earlier ones."""
import numpy as np
import pygame

import color
from ui_helpers import SESSION
from render_helpers import cell, expected_sprite_cell
from components.consumable import Meat
from components.unit import Animal
from render_order import RenderOrder


def test_render_order_iteration_is_layered(small_world):
    e = small_world()
    m = e.game_map
    meat = Meat("x"); meat.place(4, 4, m)
    corpse = Animal(); corpse.place(4, 4, m); corpse.hp = 0; corpse.die(None)
    order = [x.render_order.value for x in m.entities_in_render_order()]
    assert order == sorted(order)
    assert list(m.entities_in_render_order()).index(corpse) < list(m.entities_in_render_order()).index(meat)


def test_living_unit_is_drawn_over_corpse_and_item(small_world):
    e = small_world()
    m = e.game_map
    alive = Animal(); alive.place(4, 4, m)  # added first, still drawn last (UNIT layer)
    Meat("x").place(4, 4, m)
    dead = Animal(); dead.place(4, 4, m); dead.hp = 0; dead.die(None)
    e.update_fov()
    SESSION.canvas.clear()
    m.render(SESSION.canvas)
    drawn = cell(SESSION.canvas, 4, 4)
    expected = expected_sprite_cell(alive.sprite_id, alive.shade, alive.flipped, bg=color.nigh_black)
    # Sprites are transparent between their strokes, so lower layers show through; wherever the unit's own
    # sprite is opaque it must win over the corpse and the item underneath.
    opaque = pygame.surfarray.array_alpha(SESSION.canvas.sprites.get(alive.sprite_id, alive.flipped, alive.shade)) > 0
    assert opaque.any() and np.array_equal(drawn[opaque], expected[opaque])
    assert not np.array_equal(drawn, expected)  # ... and something is indeed drawn beneath it
