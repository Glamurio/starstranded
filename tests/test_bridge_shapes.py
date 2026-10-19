"""Bridges in three forms: single horizontal, single vertical, and multi-tile spans with their own end and middle pieces."""
import numpy as np

import tile_types as tt


def lay(deck_cells, land_cells=(), size=(12, 12)):
    deck = np.zeros(size, dtype=bool)
    land = np.zeros(size, dtype=bool)
    for x, y in deck_cells:
        deck[x, y] = True
    for x, y in land_cells:
        land[x, y] = True
    tiles = np.zeros(size, dtype=tt.floor.get_array().dtype)
    tt.lay_bridge(tiles, deck, land)
    return tiles


def sprite_at(tiles, x, y):
    return int(tiles[x, y]["light"]["sprite"])


def test_a_lone_plank_runs_across_the_river():
    east_west = lay([(5, 5)], land_cells=[(4, 5), (6, 5)])       # banks left and right: the bridge is horizontal
    north_south = lay([(5, 5)], land_cells=[(5, 4), (5, 6)])     # banks above and below: it is vertical
    assert sprite_at(east_west, 5, 5) == tt.bridge.sprite
    assert sprite_at(north_south, 5, 5) == tt.bridge_vertical.sprite


def test_a_long_span_gets_start_middle_and_end_pieces():
    h = lay([(3, 4), (4, 4), (5, 4), (6, 4)])
    assert [sprite_at(h, x, 4) for x in range(3, 7)] == [tt.bridge_h_start.sprite, tt.bridge_h_mid.sprite,
                                                         tt.bridge_h_mid.sprite, tt.bridge_h_end.sprite]
    v = lay([(2, 2), (2, 3), (2, 4)])
    assert [sprite_at(v, 2, y) for y in range(2, 5)] == [tt.bridge_v_start.sprite, tt.bridge_v_mid.sprite, tt.bridge_v_end.sprite]


def test_every_piece_is_walkable_and_counts_as_laid():
    for piece in tt.BRIDGE_PIECES:
        tile = piece.get_array()[None]
        assert bool(tile["walkable"][0]) and bool(tt.is_laid(tile)[0]) and bool(tt.is_bridge(tile)[0])
    assert not tt.is_bridge(tt.floor.get_array()[None])[0]


def test_pieces_follow_the_single_tile_until_given_their_own_sprite():
    assert tt.bridge_h_mid.sprite_pos == tt.bridge.sprite_pos
    assert tt.bridge_v_end.sprite_pos == tt.bridge_vertical.sprite_pos


def test_a_built_bridge_reshapes_as_planks_are_added(new_engine):
    import crafting
    world, player = new_engine.game_map, new_engine.player
    y = player.y
    deep = tt.water.get_array()
    deep["depth"], deep["liquid"] = 1, 1
    for x in range(player.x, player.x + 5):
        world.set_tile(x, y, deep)
    world.set_tile(player.x - 1, y, tt.floor.get_array())
    for x in range(player.x, player.x + 3):
        crafting.build_floor(world, x, y)
    sprites = [int(world.tile_at(x, y)["light"]["sprite"]) for x in range(player.x, player.x + 3)]
    assert sprites == [tt.bridge_h_start.sprite, tt.bridge_h_mid.sprite, tt.bridge_h_end.sprite]


def test_generated_bridges_use_the_shaped_pieces():
    import hydrology, worldgen
    from test_hydrology import _bridges
    pieces = set()
    for seed in (1234, 5, 77):
        noise, bridges = _bridges(seed)
        for found in bridges:
            xs, ys = [p[0] for p in found], [p[1] for p in found]
            x0, y0 = min(xs) - 3, min(ys) - 3
            tiles, _ = worldgen.generate_terrain(noise, x0, y0, max(xs) - x0 + 4, max(ys) - y0 + 4)
            for x, y, is_deck in found:
                if is_deck:
                    sprite = int(tiles[x - x0, y - y0]["light"]["sprite"])
                    assert sprite in {p.sprite for p in tt.BRIDGE_PIECES}
                    pieces.add(sprite)
    assert len(pieces) >= 2           # not every plank of every bridge is the same piece
