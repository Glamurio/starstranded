"""Helpers for asserting on what was drawn on the canvas."""
import numpy as np
import pygame

from ui_helpers import SESSION
from atlas import TILE


def cell(canvas, x, y):
    """RGB pixels of grid cell (x, y) as an array of shape (24, 24, 3) indexed [px, py]."""
    return pygame.surfarray.array3d(canvas.surface.subsurface(canvas.cell_rect(x, y))).copy()


def cell_has_color(canvas, x, y, rgb):
    pixels = cell(canvas, x, y).reshape(-1, 3)
    return bool((pixels == np.array(rgb)).all(axis=1).any())


def cell_is_blank(canvas, x, y):
    return not cell(canvas, x, y).any()


def expected_sprite_cell(sprite, tint, flipped=False, bg=(0, 0, 0)):
    """What a cell looks like with `sprite` tinted by `tint` over `bg`."""
    surface = pygame.Surface((TILE, TILE))
    surface.fill(bg)
    surface.blit(SESSION.canvas.sprites.get(sprite, flipped, tint), (0, 0))
    return pygame.surfarray.array3d(surface)


def expected_tile(entities, tile=None):
    """A visible floor cell with `entities` drawn over it in the given order (bottom first), as GameMap.render does."""
    import tile_types
    tile = tile or tile_types.floor
    sprites = SESSION.canvas.sprites
    surface = sprites.get_on(tile.sprite, False, tuple(tile.light_fg), tuple(tile.light_bg)).copy()
    for entity in entities:
        if entity.is_corpse and entity.category.name == "UNIT":
            surface.blit(sprites.get_remains(entity.sprite_id, False, entity.shade), (0, 0))
        else:
            surface.blit(sprites.get(entity.sprite_id, entity.flipped, entity.shade), (0, 0))
    return pygame.surfarray.array3d(surface)


def draw_map(engine):
    """Clear the canvas and draw just the map (no panels)."""
    SESSION.canvas.clear()
    engine.game_map.render(SESSION.canvas)
    return SESSION.canvas
