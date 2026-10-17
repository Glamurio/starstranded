"""World-coordinate noise: chunk samples are exact slices of one big grid, indexed [x, y], for any rectangle."""
import numpy as np
import pytest

from worldgen import TerrainNoise


@pytest.mark.parametrize("width,height", [(70, 40), (33, 17), (17, 33)])
def test_samples_are_width_by_height(width, height):
    assert TerrainNoise(5).sample(0, 0.05, 0, 0, width, height).shape == (width, height)


@pytest.mark.parametrize("x0,y0", [(70, 0), (0, 40), (-70, -40), (140, -80)])
def test_offset_rectangles_are_slices_of_one_big_grid(x0, y0):
    noise = TerrainNoise(5)
    big = noise.sample(0, 0.05, -140, -80, 420, 240)
    part = noise.sample(0, 0.05, x0, y0, 70, 40)
    assert np.array_equal(part, big[x0 + 140:x0 + 210, y0 + 80:y0 + 120])
