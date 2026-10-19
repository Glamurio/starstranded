import numpy as np

import blend


def _strip(left, right, width=20):
    bg = np.zeros((width, 5, 3), dtype=np.int64)
    bg[: width // 2] = left
    bg[width // 2:] = right
    return bg, bg.copy(), np.ones((width, 5), dtype=bool)


def test_a_border_is_eased_over_a_few_tiles_and_far_ground_is_untouched():
    bg, fg, ground = _strip((60, 110, 50), (110, 120, 60))
    new_bg, _ = blend.soften(bg, fg, ground)
    row = new_bg[:, 2, 0]
    assert (np.diff(row) >= 0).all()                         # a monotone ramp, no jump back
    assert 60 < row[9] < row[10] < 110                       # the two tiles at the border moved towards each other
    assert row[0] == 60 and row[-1] == 110                   # far from the border: unchanged
    assert row[10] - row[9] < 50                             # the step of 50 is now shared out


def test_only_ground_tiles_change_and_unlike_tiles_do_not_smear():
    bg, fg, ground = _strip((60, 110, 50), (200, 40, 40))   # a very different colour: a floor or a road, not a biome
    new_bg, _ = blend.soften(bg, fg, ground)
    assert np.array_equal(new_bg, bg)
    bg, fg, ground = _strip((60, 110, 50), (110, 120, 60))
    ground[10:] = False                                      # the right half is not ground (water, a wall)
    new_bg, new_fg = blend.soften(bg, fg, ground)
    assert np.array_equal(new_bg[10:], bg[10:]) and np.array_equal(new_fg[10:], fg[10:])


def test_speckle_inside_a_biome_is_kept():
    rng = np.random.default_rng(1)
    bg = (np.full((20, 20, 3), 100) + rng.integers(-6, 7, (20, 20, 3))).astype(np.int64)
    new_bg, _ = blend.soften(bg, bg.copy(), np.ones((20, 20), dtype=bool))
    assert np.abs(new_bg - bg).max() <= 8                    # the speckle is not blurred away
