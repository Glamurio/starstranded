"""Monsters and items must spawn on walkable, unoccupied tiles (in every generated chunk)."""
import random

import numpy as np
import pytest

import setup_game
from entity import EntityCategory


@pytest.mark.parametrize("seed", range(6))
def test_units_and_items_spawn_on_walkable_unblocked_tiles(seed):
    random.seed(seed)
    np.random.seed(seed)
    engine = setup_game.new_game(setup_game.create_player())
    m = engine.game_map
    for e in m.entities:
        if e.category in (EntityCategory.UNIT, EntityCategory.ITEM):
            assert m.is_walkable(e.x, e.y), f"{e.get_title()} spawned on an unwalkable tile"
    assert max(int(chunk.blocked.max()) for chunk in m.chunks.values()) <= 1  # never two blockers stacked
