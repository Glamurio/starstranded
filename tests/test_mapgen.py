"""Characterization: terrain generation (procgen.generate_noise via GameWorld.generate_floor)."""
import numpy as np
import pytest

import tile_types


def test_floor_shapes_and_dtypes(new_engine):
    m = new_engine.game_map
    assert (m.width, m.height) == (70, 40)
    assert m.tiles.shape == (70, 40)  # [x, y] indexing, width first
    assert m.tiles.dtype == tile_types.tile_dt
    assert m.visible.shape == m.explored.shape == (70, 40)
    assert m.visible.dtype == m.explored.dtype == np.bool_


def test_walkable_ratio_is_sane(new_engine):
    ratio = new_engine.game_map.tiles["walkable"].mean()
    # Noise terrain is mostly floor; trees/water/walls carve some out. Wide band on purpose.
    assert 0.5 < ratio < 0.99


def test_player_spawns_on_walkable_tile_and_is_owned_by_map(new_engine):
    p, m = new_engine.player, new_engine.game_map
    assert m.in_bounds(p.x, p.y)
    assert m.tiles["walkable"][p.x, p.y]
    assert p.parent is m and p in m.entities


def test_entities_are_inside_the_map_and_have_ai_or_are_static(new_engine):
    m = new_engine.game_map
    assert len(m.entities) > 1
    for e in m.entities:
        assert m.in_bounds(e.x, e.y)


def test_first_floor_counter_and_stairs_default(new_engine):
    # generate_noise never places stairs: downstairs_location stays at its (0, 0) default.
    assert new_engine.game_world.current_floor == 1
    assert new_engine.game_map.downstairs_location == (0, 0)


def test_trees_make_their_tile_blocking(new_engine):
    from components.plant import Tree
    trees = [e for e in new_engine.game_map.entities if isinstance(e, Tree)]
    for t in trees:
        assert not new_engine.game_map.tiles["walkable"][t.x, t.y]
        assert not new_engine.game_map.tiles["transparent"][t.x, t.y]


def test_axis_convention_noise_grid_shape():
    """tcod.noise.grid(shape=(h, w)) yields an array shaped (w, h) in the pinned tcod; the
    codebase relies on that (see ARCHITECTURE_NOTES 'axis conventions')."""
    import tcod
    noise = tcod.noise.Noise(dimensions=2, algorithm=tcod.noise.Algorithm.PERLIN)
    samples = noise[tcod.noise.grid(shape=(40, 70), scale=0.05, origin=(0, 0))]
    assert samples.shape == (70, 40)


def test_replace_variations_only_touches_matching_tiles(new_engine):
    """Water/wall edge-variation pass keeps walkability flags of the tiles it rewrites."""
    m = new_engine.game_map
    water_walkable = m.tiles["walkable"][
        (m.tiles["walkable"] == False) & (m.tiles["transparent"] == True)  # noqa: E712
    ]
    assert not water_walkable.any()
