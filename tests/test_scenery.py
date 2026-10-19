"""Scenery and foliage placement rules."""
import random

import numpy as np
import pytest

import scenery
import worldgen
from entity import EntityCategory


@pytest.fixture(scope="module")
def world_entities():
    import characters
    import setup_game
    from session import Session
    random.seed(9)
    session = Session.create(headless=True)
    engine = setup_game.new_game(characters.create_character("P", "human", "survivalist", sponsor="heavy_industries"), session=session)
    world = engine.game_map
    from debug import teleport
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            try:
                teleport(engine, dx * 70 + 35, dy * 40 + 20)
            except Exception:
                pass
    return engine, world


def by_tile(world):
    out = {}
    for e in world.entities:
        out.setdefault((e.x, e.y), []).append(e)
    return out


def test_only_a_flower_may_share_a_tile_with_a_tree_and_no_foliage_stacks(world_entities):
    engine, world = world_entities
    for pos, here in by_tile(world).items():
        plants = [e for e in here if e.category is EntityCategory.PLANT]
        trees = [e for e in plants if e.blocks_movement]
        others = [e for e in plants if not e.blocks_movement]
        assert len(trees) <= 1, pos
        if trees:
            assert all(type(e).__name__ == "Flower" for e in others), (pos, [type(e).__name__ for e in others])
        else:
            assert len(others) <= 1, (pos, [type(e).__name__ for e in others])


def test_nothing_you_can_pick_up_is_hidden_under_foliage_or_scenery(world_entities):
    engine, world = world_entities
    for pos, here in by_tile(world).items():
        if any(e.category is EntityCategory.ITEM for e in here):
            assert not any(getattr(e, "scenery", False) for e in here), pos


def test_scenery_follows_the_environment():
    shape = (4, 3)
    desert = {"biome": np.full(shape, 10), "landmark": np.full(shape, -1), "landmark_strength": np.zeros(shape)}
    forest = {"biome": np.full(shape, 4), "landmark": np.full(shape, -1), "landmark_strength": np.zeros(shape)}
    bones = scenery.BY_KEY["bones"]
    assert scenery.weights(bones, desert).mean() > 4 * scenery.weights(bones, forest).mean()
    rubble = scenery.BY_KEY["rubble"]
    assert scenery.weights(rubble, desert).max() == 0.0     # rubble only belongs to ruined land


def test_scenery_is_a_pure_function_of_the_tile_not_of_the_chunk():
    noise = worldgen.TerrainNoise(5)
    a = noise.scatter(2000, 0, 0, 70, 40)
    b = noise.scatter(2000, 35, 20, 70, 40)
    assert np.array_equal(a[35:, 20:], b[:35, :20])


def test_scenery_has_a_name_and_is_not_an_item(world_entities):
    engine, world = world_entities
    found = [e for e in world.entities if getattr(e, "scenery", False)]
    assert found, "no scenery generated near the start"
    assert all(e.category is not EntityCategory.ITEM and not e.blocks_movement and e.get_title() for e in found)
