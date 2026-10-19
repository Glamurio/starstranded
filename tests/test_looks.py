"""How things are drawn: calm foliage, wreckage that lies at an angle, remains without a skull, and stone that is stone-coloured."""
import random

import numpy as np
import pygame

import atlas
import shafts
import structures
import tile_types
from ui_helpers import SESSION


def sprites():
    return SESSION.canvas.sprites


def test_foliage_is_calmer_and_a_little_transparent():
    plain = sprites().get(2000, False, (60, 220, 40))
    calm = sprites().get_foliage(2000, False, (60, 220, 40))
    solid = pygame.surfarray.array_alpha(plain) > 0
    assert solid.any()
    assert pygame.surfarray.array_alpha(calm)[solid].max() < 255
    red, green, blue = (pygame.surfarray.array3d(calm)[solid].mean(axis=0))
    pr, pg, pb = (pygame.surfarray.array3d(plain)[solid].mean(axis=0))
    assert (green - red) < (pg - pr)                       # less saturated


def test_remains_carry_no_skull():
    assert not hasattr(atlas, "draw_bones")


def test_wreckage_lies_at_a_multiple_of_45_degrees_and_stays_in_its_tile():
    seen = set()
    for seed in range(40):
        rng = random.Random(seed)
        piece = structures.Wreckage(1, rng)
        assert piece.rotation % 45 == 0 and 0 <= piece.rotation < 360
        seen.add((piece.rotation, piece.pose_flip))
        turned = sprites().get_rotated(piece.sprite_id, piece.pose_flip, piece.shade, piece.rotation)
        assert turned.get_size() == (24, 24)
    assert len({r for r, _ in seen}) >= 4 and {f for _, f in seen} == {True, False}
    assert structures.Wreckage(0).rotation == 0           # (an older save keeps the way it was drawn)


def test_stone_is_grey_brown_not_a_random_colour():
    r, g, b = tile_types.wall_color
    assert abs(r - g) < 25 and abs(g - b) < 30
    for key in [(3, 2), (-8, 5), (10, -4)]:
        tiles, _ = shafts.raw_surface(321, key)
        rock = ~tiles["walkable"] & ~tiles["transparent"] & (tiles["liquid"] == 0)
        if rock.any():
            r, g, b = tiles["light"]["fg"][..., :3][rock].astype(float).mean(axis=0)
            assert r - b < 45 and abs(r - g) < 30           # never the old pink/red
