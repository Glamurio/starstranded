"""Shared pytest setup.

The game uses flat imports (``import g``) and loads assets relative to ``src/``,
so tests put ``src`` on ``sys.path`` and run with ``src`` as the working directory.
SDL must use the dummy video driver *before* ``g`` is imported (it opens a window).
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
os.chdir(SRC)

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import setup_game  # noqa: E402,F401  (import first: resolves the circular import order)


@pytest.fixture(autouse=True)
def seeded():
    """Seed python and numpy RNGs. NOTE: tcod.noise.Noise() is NOT seeded by these."""
    random.seed(1234)
    np.random.seed(1234)


@pytest.fixture
def small_world():
    """Factory: a tiny all-floor map with a player at (1, 1). Fully deterministic."""
    import tile_types
    from engine import Engine
    from world import GameMap, GameWorld
    from setup_game import create_player

    def make(width: int = 12, height: int = 10, explored: bool = True):
        player = create_player()
        engine = Engine(player=player)
        engine.game_world = GameWorld(
            engine=engine, map_width=width, map_height=height,
            max_rooms=1, room_min_size=1, room_max_size=2,
        )
        landscape = np.full(
            (width, height), fill_value=tile_types.floor.get_array(),
            order="F", dtype=tile_types.tile_dt,
        )
        game_map = GameMap(engine.game_world, landscape, engine, width, height, entities=[player])
        engine.game_map = game_map
        player.place(1, 1, game_map)
        game_map.explored[:] = explored
        engine.update_fov()
        return engine

    return make


@pytest.fixture
def new_engine():
    """A full noise-generated game, exactly as the New Game flow builds it."""
    return setup_game.new_game(setup_game.create_player())
