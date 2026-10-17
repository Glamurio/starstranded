"""Shared invariant check for the World's spatial index (world-level `_by_pos` + per-chunk indexes)."""
import numpy as np

from chunks import chunk_key
from entity import EntityCategory


def assert_index_consistent(world) -> None:
    entities = list(world.entities)
    assert len(entities) == len(set(entities)), "an entity is indexed in two chunks"
    by_pos = {}
    for e in entities:
        assert e.parent is world
        by_pos.setdefault((e.x, e.y), []).append(e)
    assert {k: set(v) for k, v in by_pos.items()} == {k: set(v) for k, v in world._by_pos.items()}
    for key, chunk in world.chunks.items():
        members = set(chunk.entities)
        assert all(chunk_key(e.x, e.y) == key for e in members), f"entity outside its chunk {key}"
        for category in EntityCategory:
            assert set(chunk.by_category[category]) == {e for e in members if e.category is category}
        assert set(chunk.actors) == {e for e in members if e.ai}
        for order, bucket in chunk.buckets.items():
            assert set(bucket) == {e for e in members if e.render_order is order}
        blocked = np.zeros_like(chunk.blocked)
        for e in members:
            if e.blocks_movement:
                blocked[e.x - chunk.x0, e.y - chunk.y0] += 1
        assert np.array_equal(blocked, chunk.blocked)
    assert set(world.actors) == {e for e in entities if e.ai}
