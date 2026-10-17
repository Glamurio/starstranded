"""Terrain noise must come out indexed [x, y] with a non-square map (70 x 40), so a transposition is visible."""
import numpy as np
import pytest

import tile_types
from world import GameWorld
from engine import Engine
from setup_game import create_player


@pytest.mark.parametrize("width,height", [(70, 40), (33, 17), (17, 33)])
def test_generated_landscape_is_width_by_height(width, height):
    engine = Engine(player=create_player())
    engine.game_world = GameWorld(engine=engine, map_width=width, map_height=height,
                                  max_rooms=1, room_min_size=1, room_max_size=2)
    engine.game_world.generate_floor()
    m = engine.game_map
    assert m.tiles.shape == m.visible.shape == (width, height)
    assert m.tiles["walkable"].dtype == np.bool_
    p = engine.player
    assert 0 <= p.x < width and 0 <= p.y < height and m.tiles["walkable"][p.x, p.y]
    for e in m.entities:
        assert 0 <= e.x < width and 0 <= e.y < height
