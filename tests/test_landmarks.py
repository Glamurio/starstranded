"""Landmarks: deterministic, climate-bound, non-overlapping, softly edged regions."""
import numpy as np

import landmarks
import worldgen
from ecology import suitability

W, H = 600, 400


def region(seed=77, x0=-300, y0=-200):
    noise = worldgen.TerrainNoise(seed)
    kinds = worldgen.base_terrain(noise, x0, y0, W, H)
    env = worldgen.environment_for(noise, x0, y0, W, H, kinds)
    env["climate"] = landmarks.climate_of(noise, x0, y0, W, H, env)
    return env


def test_registry_is_valid():
    landmarks.validate_content()
    assert len(set(landmarks.LANDMARK_IDS)) == len(landmarks.LANDMARK_IDS) >= 6


def test_same_seed_same_landmarks_and_other_seed_differs():
    a, b, c = region(77), region(77), region(78)
    assert np.array_equal(a["landmark"], b["landmark"]) and np.array_equal(a["landmark_strength"], b["landmark_strength"])
    assert not np.array_equal(a["landmark"], c["landmark"])


def test_cutting_the_world_differently_gives_the_same_landmarks():
    whole = region(77)
    part = region(77, x0=-300 + 150, y0=-200 + 100)
    assert np.array_equal(whole["landmark"][150:150 + 300, 100:100 + 200], part["landmark"][:300, :200])


def test_a_landmark_only_forms_where_the_climate_suits_it():
    env = region()
    for key, number in landmarks.LANDMARK_INDEX.items():
        inside = env["landmark"] == number
        assert inside.any(), f"{key} never appears in a {W}x{H} sample"
        fit = suitability(landmarks.LANDMARKS[key].climate, env["climate"])
        assert fit[inside].min() > 0.0
        # strength is the product of the noise and the fit, so it can never exceed the fit
        assert (env["landmark_strength"][inside] <= fit[inside] + 1e-9).all()


def test_each_tile_has_at_most_one_landmark_and_strength_matches():
    env = region()
    assert ((env["landmark"] == 0) == (env["landmark_strength"] == 0)).all()
    assert env["landmark_strength"].max() <= 1.0


def test_edges_are_gradual():
    """Next to a tile of one landmark the strength changes by a small step, never from full to none."""
    s = region()["landmark_strength"]
    assert np.abs(np.diff(s, axis=0)).max() < 0.5 and np.abs(np.diff(s, axis=1)).max() < 0.5


def test_landmarks_are_coherent_regions_not_speckle():
    """Nearly every landmark tile touches a tile of the same landmark on all four sides: patches, not scattered dots."""
    index = region()["landmark"]
    inner = index[1:-1, 1:-1]
    same = (index[:-2, 1:-1] == inner) & (index[2:, 1:-1] == inner) & (index[1:-1, :-2] == inner) & (index[1:-1, 2:] == inner)
    assert same[inner > 0].mean() > 0.9


def test_terrain_has_no_ground_cover_under_trees():
    noise = worldgen.TerrainNoise(77)
    with worldgen.seeded_rng(5):
        tiles, trees = worldgen.generate_terrain(noise, 0, 0, 70, 40)
    cover = {worldgen.sprite_id(*cell) for cells in worldgen.GROUND_COVER.values() for cell in cells}
    cover |= {worldgen.sprite_id(*cell) for lm in landmarks.LANDMARKS.values() for cell in lm.cover}
    under = np.isin(tiles["light"]["sprite"], list(cover)) & trees
    assert not under.any()
