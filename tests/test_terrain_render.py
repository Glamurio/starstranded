"""Terrain is drawn by a packed per-cell key; every sprite id on the sheet must survive the packing."""
import numpy as np
import pygame

import atlas
import tile_types
from render_helpers import cell, draw_map
from ui_helpers import SESSION


def test_every_sprite_id_on_the_sheet_draws_as_itself(small_world):
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
