"""Inventory menu rendering: every entry gets its sprite as a list icon, tinted with the item's colour."""
import numpy as np

import g
import input_handlers
from components.consumable import Meat
from render_helpers import cell, expected_sprite_cell
import color


def render_inventory(e):
    handler = input_handlers.InventoryActivateHandler(e, e.player.inventory)
    g.handlers = [input_handlers.MainGameEventHandler(e), handler]
    g.draw(handler)
    return g.canvas


def test_inventory_renders_meat_icon_and_title(small_world):
    e = small_world()
    meat = Meat("rabbit", e.player.inventory)
    e.player.inventory.add(meat)
    canvas = render_inventory(e)
    expected = expected_sprite_cell(meat.sprite_id, meat.color, meat.flipped, bg=color.nigh_black)
    assert np.array_equal(cell(canvas, 12, 7), expected)
    assert cell(canvas, 14, 7).any()  # the title text next to the icon


def test_empty_inventory_says_so(small_world):
    e = small_world()
    for item in list(e.player.inventory.items):
        e.player.inventory.remove(item)
    canvas = render_inventory(e)
    assert cell(canvas, 11, 3).any()  # "(Empty)" starts at console_x + 1, console_y + 2
