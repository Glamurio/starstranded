"""Shared invariant check for GameMap's spatial index."""
import numpy as np

from entity import EntityCategory


def assert_index_consistent(game_map) -> None:
    entities = list(game_map.entities)
    by_pos = {}
    for e in entities:
        assert e.parent is game_map
        by_pos.setdefault((e.x, e.y), []).append(e)
    assert {k: set(v) for k, v in by_pos.items()} == {k: set(v) for k, v in game_map._by_pos.items()}
    for category in EntityCategory:
        assert set(game_map._by_category[category]) == {e for e in entities if e.category is category}
    assert set(game_map.actors) == {e for e in entities if e.ai}
    for order, bucket in game_map._buckets.items():
        assert set(bucket) == {e for e in entities if e.render_order is order}
    blocked = np.zeros_like(game_map.blocked)
    for e in entities:
        if e.blocks_movement and game_map.in_bounds(e.x, e.y):
            blocked[e.x, e.y] += 1
    assert np.array_equal(blocked, game_map.blocked)
