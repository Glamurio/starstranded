"""Terrain is drawn by a packed per-cell key; every sprite id on the sheet must survive the packing."""
import numpy as np
import pygame

import atlas
import tile_types
import world
from render_helpers import cell, draw_map
from ui_helpers import SESSION


def test_every_sprite_id_on_the_sheet_draws_as_itself(small_world, monkeypatch):
    monkeypatch.setattr(world, "BLEND_BORDERS", False)    # this checks the key packing, not the colours
    e = small_world(width=12, height=10)
    ids = sorted({0, 1, 4094, 4095, 4096, 5125, 5134, 6000, atlas.COLUMNS * atlas.ROWS - 1, *range(100, 6250, 211)})
    spots = [(x, y) for y in range(2, 8) for x in range(1, 11)]
    sheet = SESSION.canvas.sprites
    for start in range(0, len(ids), len(spots)):
        batch = ids[start:start + len(spots)]
        for sprite, (x, y) in zip(batch, spots):
            tile = tile_types.floor.get_array()
            tile["light"]["sprite"] = sprite
            tile["light"]["fg"] = (200, 120, 60)
            e.game_map.set_tile(x, y, tile)
        e.update_fov()
        draw_map(e)
        for sprite, (x, y) in zip(batch, spots):
            expected = pygame.surfarray.array3d(sheet.get_on(sprite, False, (200, 120, 60), tuple(tile_types.floor.light_bg)))
            assert np.array_equal(cell(SESSION.canvas, x, y), expected), sprite


def test_ground_colours_ease_across_a_biome_border_but_sprites_stay_sharp(small_world):
    e = small_world(width=20, height=10)
    for y in range(1, 9):
        for x in range(1, 19):
            tile = tile_types.floor.get_array()
            tile["light"]["bg"] = (50, 100, 50) if x < 10 else (100, 110, 60)
            e.game_map.set_tile(x, y, tile)
    e.update_fov()
    draw_map(e)
    left, right = cell(SESSION.canvas, 9, 4), cell(SESSION.canvas, 10, 4)
    far_left, far_right = cell(SESSION.canvas, 2, 4), cell(SESSION.canvas, 17, 4)
    assert np.abs(left.astype(int) - far_left).sum() > 0 and np.abs(right.astype(int) - far_right).sum() > 0   # the border tiles moved
    assert 50 < left[0, 0, 0] < right[0, 0, 0] < 100                     # a ramp between the two ground colours
    assert far_left[0, 0, 0] == 50 and far_right[0, 0, 0] == 100         # untouched away from the border
