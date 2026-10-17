"""Characterization of a generated floor: a chunked world around the start in chunk (0, 0)."""
import numpy as np

import tile_types
from chunks import CHUNK_H, CHUNK_W, chunk_key, keys_around


def test_loaded_chunks_shapes_and_dtypes(new_engine):
    m = new_engine.game_map
    assert set(m.chunks) == set(keys_around((0, 0), new_engine.config.near_radius))
    for chunk in m.chunks.values():
        assert chunk.tiles.shape == chunk.explored.shape == (CHUNK_W, CHUNK_H)  # [x, y] indexing, width first
        assert chunk.tiles.dtype == tile_types.tile_dt and chunk.explored.dtype == np.bool_
    window = m.window.ensure()
    assert window.visible.shape == (3 * CHUNK_W, 3 * CHUNK_H) and window.origin == (-CHUNK_W, -CHUNK_H)


def test_walkable_ratio_is_sane(new_engine):
    ratio = np.mean([c.tiles["walkable"].mean() for c in new_engine.game_map.chunks.values()])
    # Noise terrain is mostly floor; trees/water/walls carve some out. Wide band on purpose.
    assert 0.5 < ratio < 0.99


def test_player_starts_on_a_walkable_tile_of_chunk_0_0(new_engine):
    p, m = new_engine.player, new_engine.game_map
    assert chunk_key(p.x, p.y) == (0, 0)
    assert m.in_bounds(p.x, p.y) and m.is_walkable(p.x, p.y)
    assert p.parent is m and p in m.entities


def test_entities_sit_in_the_chunk_that_indexes_them(new_engine):
    m = new_engine.game_map
    assert len(m.entities) > 1
    for key, chunk in m.chunks.items():
        for e in chunk.entities:
            assert chunk_key(e.x, e.y) == key and m.in_bounds(e.x, e.y)


def test_first_floor_has_a_reachable_staircase_near_the_start(new_engine):
    m, p = new_engine.game_map, new_engine.player
    assert new_engine.game_world.current_floor == 1
    sx, sy = m.downstairs_location
    assert chunk_key(sx, sy) == (0, 0)
    tile = m.tile_at(sx, sy)
    assert tile["light"]["sprite"] == tile_types.down_stairs.sprite and tile["walkable"]
    assert 8 <= max(abs(sx - p.x), abs(sy - p.y)) <= 20


def test_trees_make_their_tile_blocking(new_engine):
    from components.plant import Tree
    m = new_engine.game_map
    trees = [e for e in m.entities if isinstance(e, Tree)]
    assert trees
    for t in trees:
        assert not m.is_walkable(t.x, t.y) and not m.is_transparent(t.x, t.y)


def test_axis_convention_noise_grid_shape():
    """tcod.noise.grid(shape=(h, w)) yields an array shaped (w, h) in the pinned tcod; the
    codebase relies on that (see ARCHITECTURE_NOTES 'axis conventions')."""
    import tcod
    noise = tcod.noise.Noise(dimensions=2, algorithm=tcod.noise.Algorithm.PERLIN)
    samples = noise[tcod.noise.grid(shape=(40, 70), scale=0.05, origin=(0, 0))]
    assert samples.shape == (70, 40)


def test_water_is_never_walkable(new_engine):
    for chunk in new_engine.game_map.chunks.values():
        water = chunk.tiles["light"]["sprite"] == tile_types.water.sprite
        assert not chunk.tiles["walkable"][water].any()
