import numpy as np
import pygame
import pytest

import atlas


@pytest.fixture
def sheet_atlas():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    return atlas.SpriteAtlas.load("urizen_nogrid_white.png")


def test_sheet_geometry(sheet_atlas):
    assert (sheet_atlas.columns, sheet_atlas.rows) == (atlas.COLUMNS, atlas.ROWS) == (50, 50)
    assert sheet_atlas.sheet.get_size() == (1200, 1200)


def test_sprite_id_roundtrip():
    assert atlas.sprite_id(0, 0) == 0
    assert atlas.sprite_id(3, 15) == 15 * 50 + 3
    assert atlas.sprite_position(atlas.sprite_id(44, 21)) == (44, 21)
    with pytest.raises(AssertionError):
        atlas.sprite_id(50, 0)


def test_background_is_transparent_and_sprite_opaque(sheet_atlas):
    human = sheet_atlas.get(atlas.sprite_id(0, 9))
    alpha = pygame.surfarray.array_alpha(human)
    assert alpha.max() == 255 and alpha.min() == 0
    assert 20 < (alpha > 0).sum() < human.get_width() * human.get_height()
    blank = pygame.surfarray.array_alpha(sheet_atlas.get(atlas.sprite_id(49, 49)))
    assert blank.max() in (0, 255)


def test_variants_are_cached_and_shared(sheet_atlas):
    sprite = atlas.sprite_id(3, 15)
    assert sheet_atlas.get(sprite) is sheet_atlas.get(sprite)
    assert sheet_atlas.get(sprite, True, (255, 0, 0)) is sheet_atlas.get(sprite, True, (255, 0, 0))
    assert sheet_atlas.get(sprite) is not sheet_atlas.get(sprite, True)
    assert sheet_atlas.get(sprite) is not sheet_atlas.get(sprite, False, (1, 2, 3))


def test_flip_mirrors_horizontally(sheet_atlas):
    sprite = atlas.sprite_id(3, 15)
    plain = pygame.surfarray.array_alpha(sheet_atlas.get(sprite))
    flipped = pygame.surfarray.array_alpha(sheet_atlas.get(sprite, True))
    assert np.array_equal(plain[::-1], flipped)


def test_tint_multiplies_colour_and_keeps_alpha(sheet_atlas):
    sprite = atlas.sprite_id(3, 15)
    plain = sheet_atlas.get(sprite)
    red = sheet_atlas.get(sprite, False, (200, 100, 0))
    assert np.array_equal(pygame.surfarray.array_alpha(plain), pygame.surfarray.array_alpha(red))
    mask = pygame.surfarray.array_alpha(red) > 0
    rgb = pygame.surfarray.array3d(red)[mask]
    assert (rgb == (200, 100, 0)).all()


def test_get_on_composites_over_background(sheet_atlas):
    tile = sheet_atlas.get_on(atlas.sprite_id(3, 15), False, (255, 255, 255), (10, 20, 30))
    assert tile.get_size() == (24, 24)
    assert tile.get_at((0, 0))[:3] == (10, 20, 30) or tile.get_at((0, 0))[:3] == (255, 255, 255)
    assert not (tile.get_flags() & pygame.SRCALPHA)
    shroud = sheet_atlas.get_on(atlas.NO_SPRITE, False, (255, 255, 255), (0, 0, 0))
    assert pygame.surfarray.array3d(shroud).max() == 0


def test_cache_is_bounded(sheet_atlas, monkeypatch):
    monkeypatch.setattr(atlas, "MAX_CACHED_VARIANTS", 20)
    for i in range(100):
        sheet_atlas.get(atlas.sprite_id(i % 50, 0), False, (i, i, i))
    assert sheet_atlas.cached_variants <= 21
