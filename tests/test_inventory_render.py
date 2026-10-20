"""Inventory menu rendering: every entry gets its sprite as a list icon, tinted with the item's colour."""
import numpy as np

from ui_helpers import SESSION
import input_handlers
from components.consumable import Meat
from render_helpers import cell, expected_sprite_cell
import color
import ui


def render_inventory(e):
    handler = input_handlers.InventoryActivateHandler(e, e.player.inventory)
    SESSION.handlers = [input_handlers.MainGameEventHandler(e), handler]
    SESSION.draw(handler)
    return SESSION.canvas


def test_inventory_renders_meat_icon_and_title(small_world):
    e = small_world()
    meat = Meat("rabbit", e.player.inventory)
    e.player.inventory.add(meat)
    canvas = render_inventory(e)
    # window at (0, 0): tab row, then dagger / armour under their headings, then "Food and drink" and the meat (row 5 of the list)
    expected = expected_sprite_cell(meat.sprite_id, meat.color, meat.flipped, bg=ui.Theme.BG)
    assert np.array_equal(cell(canvas, 3, 8), expected)
    assert cell(canvas, 5, 8).any()  # the title text next to the icon


def test_empty_inventory_says_so(small_world):
    e = small_world()
    for item in list(e.player.inventory.items):
        e.player.inventory.remove(item)
    canvas = render_inventory(e)
    assert cell(canvas, 2, 4).any()  # "(nothing here)" starts at the window's inner corner
