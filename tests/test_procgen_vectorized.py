"""The vectorised lake dilation and edge-variation passes must match the old per-cell loops."""
import random

import numpy as np
import pytest

from ui_helpers import SESSION
import procgen
import tile_types


def old_dilate(lake_map):
    w, h = lake_map.shape
    out = np.zeros(lake_map.shape)
    for x in range(w):
        for y in range(h):
            if lake_map[x, y]:
                out[x, y] = 2
                continue
            if lake_map[min(x + 1, w - 1), y] or lake_map[max(x - 1, 0), y] or lake_map[x, min(y + 1, h - 1)] or lake_map[x, max(y - 1, 0)]:
                out[x, y] = 2
    return out.astype(bool)


def old_replace_variations(tile, landscape, width, height):
    """Verbatim logic of the pre-Phase-2 implementation (per-cell match statement)."""
    tile_map = landscape == tile.get_array()
    char_info = tile.variation_ids
    default = tile.sprite
    for x, row in enumerate(tile_map):
        for y, is_tile in enumerate(row):
            if not is_tile:
                continue
            coords = [[x - 1, y, "left", False], [x + 1, y, "right", False], [x, y - 1, "up", False], [x, y + 1, "down", False]]
            for coord in coords:
                if 0 <= coord[0] < width and 0 <= coord[1] < height and tile_map[coord[0]][coord[1]]:
                    coord[3] = True
            names = {
                (False, False, False, False): 'center_solo', (False, False, False, True): 'north_solo',
                (False, False, True, False): 'south_solo', (False, False, True, True): 'east_west',
                (False, True, False, False): 'west_solo', (False, True, False, True): 'north_west',
                (False, True, True, False): 'south_west', (False, True, True, True): 'west',
                (True, False, False, False): 'east_solo', (True, False, False, True): 'north_east',
                (True, False, True, False): 'south_east', (True, False, True, True): 'east',
                (True, True, False, False): 'north_south', (True, True, False, True): 'north',
                (True, True, True, False): 'south',
            }
            key = tuple(c[3] for c in coords)
            if key == (True, True, True, True):
                center = char_info.get('center', None)
                tile_char = center if center and bool(random.getrandbits(1)) else default
            else:
                tile_char = char_info.get(names[key], default)
            landscape[x][y] = (tile.walkable, tile.transparent, (tile_char, False, tile.dark_fg, tile.dark_bg),
                               (tile_char, False, tile.light_fg, tile.light_bg), tile.open, tile.stairs)
    return landscape


def random_landscape(seed, w=37, h=23, density=0.45):
    rng = np.random.default_rng(seed)
    land = np.full((w, h), tile_types.floor.get_array(), dtype=tile_types.tile_dt, order="F")
    land[rng.random((w, h)) < density] = tile_types.water.get_array()
    land[rng.random((w, h)) < density / 2] = tile_types.wall.get_array()
    return land


@pytest.mark.parametrize("seed", range(10))
def test_dilate_matches_old_loop(seed):
    mask = np.random.default_rng(seed).random((37, 23)) < 0.2
    assert np.array_equal(procgen.dilate(mask), old_dilate(mask))


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("tile", [tile_types.water, tile_types.wall], ids=["water", "wall"])
def test_replace_variations_matches_old_loop(seed, tile):
    land = random_landscape(seed)
    is_tile = land == tile.get_array()
    l, r, u, d = procgen.neighbour_masks(is_tile)
    surrounded = is_tile & l & r & u & d
    old = old_replace_variations(tile, land.copy(), *land.shape)
    new = procgen.replace_variations(tile, land.copy(), *land.shape)
    random_cells = (old["dark"]["sprite"] != new["dark"]["sprite"])
    assert not (random_cells & ~surrounded).any()
    # Only "surrounded" cells pick randomly (center vs default); every other cell must match exactly.
    allowed = {tile.sprite, tile.variation_ids.get("center", tile.sprite)}
    assert set(np.unique(old["dark"]["sprite"][random_cells])) <= allowed
    assert set(np.unique(new["dark"]["sprite"][random_cells])) <= allowed
    same = ~random_cells
    assert np.array_equal(old[same], new[same])
    assert np.array_equal(old["walkable"], new["walkable"]) and np.array_equal(old["light"]["fg"], new["light"]["fg"])
