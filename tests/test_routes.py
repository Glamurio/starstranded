"""Planned paths between the sites of the surface (see `routes`)."""
import numpy as np

import routes
import shafts
import tile_types
from chunks import CHUNK_H, CHUNK_W

SEED = 1234


def _some_routes(count=4):
    found = []
    for kx in range(-10, 11):
        for ky in range(-8, 9):
            if routes.is_site(SEED, (kx, ky)):
                other = routes.nearest(SEED, (kx, ky))
                if other is not None:
                    found.append((min((kx, ky), other), max((kx, ky), other)))
    return sorted(set(found))[:count]


def test_the_site_roll_matches_the_building_chance():
    assert routes.BUILDING_ROLL == shafts.BUILDING_CHANCE
    for key in [(x, y) for x in range(-5, 6) for y in range(-5, 6)]:
        if routes.is_site(SEED, key) and key not in __import__("structures").ruin_chunks(SEED):
            import random
            assert random.Random(shafts._mix(SEED, key[0], key[1], 7)).random() < shafts.BUILDING_CHANCE


def test_routes_are_deterministic_and_join_a_site_to_its_nearest():
    pairs = _some_routes()
    assert pairs
    for a, b in pairs:
        assert routes.laid(SEED, a, b) == routes.laid(SEED, a, b)
        assert routes.nearest(SEED, a) == b or routes.nearest(SEED, b) == a
        assert routes.course(SEED, a, b)[0] == routes.site_point(SEED, a)


def test_the_landing_chunk_is_never_a_site():
    assert not routes.is_site(SEED, (0, 0))


def test_every_laid_tile_shows_in_its_chunk_and_only_over_plain_ground_or_short_water():
    checked = 0
    for a, b in _some_routes(3):
        for (x, y), deck in routes.laid(SEED, a, b).items():
            key = (x // CHUNK_W, y // CHUNK_H)
            if shafts.structure(SEED, key).building is not None or shafts.structure(SEED, key).links:
                continue
            tiles, trees = shafts.surface_layer(SEED, key)
            tile = tiles[x - key[0] * CHUNK_W, y - key[1] * CHUNK_H]
            assert tile["walkable"] and tile["liquid"] == 0 and not trees[x - key[0] * CHUNK_W, y - key[1] * CHUNK_H]
            assert bool(tile_types.is_laid(tile[None])[0])
            checked += 1
    assert checked > 20


def test_bridged_stretches_are_short_with_dry_ground_each_side():
    for a, b in _some_routes(6):
        course = routes.course(SEED, a, b)
        laid = routes.laid(SEED, a, b)
        run = 0
        for i, tile in enumerate(course):
            if laid.get(tile) is True:
                run += 1
                assert run <= routes.MAX_SPAN
            else:
                if run:
                    assert laid.get(course[i - 1 - run]) is False and laid.get(tile) is False
                run = 0
