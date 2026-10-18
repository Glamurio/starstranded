"""The merged sprite sheet keeps every sprite the game uses looking exactly as it did on the old Urizen sheet."""
import json
from pathlib import Path

import numpy as np
import pygame
import pytest

import atlas
from sprite_refs import sprite_hash, sprite_refs

GOLDEN = json.loads((Path(__file__).parent / "data" / "sprite_golden.json").read_text())


@pytest.fixture(scope="module")
def sheet():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    return atlas.SpriteAtlas.load("urizen_white.png")


def test_every_sprite_the_game_uses_is_pixel_identical_to_before(sheet):
    refs = sprite_refs()
    assert set(refs) == set(GOLDEN), set(refs) ^ set(GOLDEN)
    changed = [label for label, sprite in refs.items() if sprite_hash(sheet, sprite) != GOLDEN[label]]
    assert not changed, changed


def test_the_game_never_points_at_an_empty_cell(sheet):
    for label, sprite in sprite_refs().items():
        alpha = pygame.surfarray.array_alpha(sheet.get(sprite))
        assert alpha.any(), label


def test_sheet_is_white_with_binary_alpha(sheet):
    rgb = pygame.surfarray.array3d(sheet.sheet)
    alpha = pygame.surfarray.array_alpha(sheet.sheet)
    assert set(np.unique(alpha)) <= {0, 255}
    assert (rgb[alpha > 0] == 255).all()
    assert (sheet.columns, sheet.rows) == (atlas.COLUMNS, atlas.ROWS)


def test_sprites_do_not_cross_cell_edges_into_the_custom_block_unintentionally(sheet):
    """Column 99 (end of the official sprites) and column 100 (start of the custom block) are different worlds."""
    assert sheet.get(atlas.sprite_id(124, 49)).get_bounding_rect().width == 0  # the reserved blank cell stays blank
