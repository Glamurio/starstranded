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
        if (routes.is_site(SEED, key) and key not in __import__("structures").ruin_chunks(SEED)
                and __import__("settlements").kind_of(SEED, key) is None):
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
    for a, b in _some_routes(12):
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
        laid = routes.laid(SEED, a, b)
        course = next((c for c in (routes.course(SEED, a, b, n) for n in range(routes.ATTEMPTS)) if laid and all(t in laid for t in c)), [])
        run = 0
        for i, tile in enumerate(course):
            if laid.get(tile) is True:
                run += 1
                assert run <= routes.MAX_SPAN
            else:
                if run:
                    assert laid.get(course[i - 1 - run]) is False and laid.get(tile) is False
                run = 0


def test_a_route_is_walkable_from_end_to_end_or_not_laid_at_all():
    laid_routes = dropped = 0
    for a, b in _some_routes(12):
        laid = routes.laid(SEED, a, b)
        if not laid:
            dropped += 1
            continue
        laid_routes += 1
        courses = [routes.course(SEED, a, b, n) for n in range(routes.ATTEMPTS)]
        whole = [c for c in courses if all(t in laid for t in c)]
        assert whole, "a laid route must cover every tile of one of its courses (no broken road)"
        steps = whole[0]
        for (x0, y0), (x1, y1) in zip(steps, steps[1:]):
            assert max(abs(x1 - x0), abs(y1 - y0)) == 1       # unbroken
    assert laid_routes > 0
