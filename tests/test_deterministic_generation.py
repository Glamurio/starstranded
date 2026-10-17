"""Seeding `random` (and numpy) makes a whole game reproducible; chunks regenerate identically from their seed."""
import random

import numpy as np

import setup_game


def signature(engine):
    m = engine.game_map
    tiles = {key: chunk.tiles.copy() for key, chunk in m.chunks.items()}
    entities = sorted((e.x, e.y, type(e).__name__, getattr(e, "species", None)) for e in m.entities)
    return tiles, entities


def generate(seed):
    random.seed(seed)
    np.random.seed(seed)
    return setup_game.new_game(setup_game.create_player())


def test_same_seed_same_floor():
    (ta, ea), (tb, eb) = signature(generate(42)), signature(generate(42))
    assert ta.keys() == tb.keys() and all(np.array_equal(ta[k], tb[k]) for k in ta) and ea == eb


def test_different_seed_different_floor():
    ta, _ = signature(generate(1))
    tb, _ = signature(generate(2))
    assert not np.array_equal(ta[(0, 0)]["walkable"], tb[(0, 0)]["walkable"])
