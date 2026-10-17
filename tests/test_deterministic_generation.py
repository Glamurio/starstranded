"""Seeding `random` (and numpy) makes a whole floor reproducible, terrain noise included."""
import random

import numpy as np

import setup_game


def generate(seed):
    random.seed(seed)
    np.random.seed(seed)
    engine = setup_game.new_game(setup_game.create_player())
    m = engine.game_map
    return m.tiles["walkable"].copy(), sorted((e.x, e.y, type(e).__name__) for e in m.entities)


def test_same_seed_same_floor():
    a, b = generate(42), generate(42)
    assert np.array_equal(a[0], b[0]) and a[1] == b[1]


def test_different_seed_different_floor():
    assert not np.array_equal(generate(1)[0], generate(2)[0])
