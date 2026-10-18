import numpy as np

import biomes
from biomes import BIOME_IDS, BIOMES, classify


def test_every_climate_point_gets_exactly_one_biome():
    t, m = np.meshgrid(np.linspace(-1.2, 1.2, 97), np.linspace(-1.2, 1.2, 97))
    h = np.zeros_like(t)
    region = np.zeros_like(t)
    out = classify(t, m, h, region)
    assert out.min() >= 0 and out.max() < len(BIOME_IDS)
    base = {BIOME_IDS[i] for i in np.unique(out)}
    assert {"glacial", "tundra", "taiga", "steppe", "temperate_forest", "grassland", "shrubland", "jungle", "savanna", "badlands", "desert"} <= base


def test_known_points():
    assert biomes.biome_at(-0.9, 0, 0, 0).key == "glacial"
    assert biomes.biome_at(0.8, 0.8, 0.5, 0).key == "jungle"
    assert biomes.biome_at(0.8, -0.8, 0.5, 0).key == "desert"
    assert biomes.biome_at(0.0, 0.5, 0.5, 0).key == "temperate_forest"


def test_wet_lowlands_become_swamp_or_bog():
    assert biomes.biome_at(0.5, 0.7, -0.5, 0).key == "swamp"
    assert biomes.biome_at(-0.1, 0.7, -0.5, 0).key == "bog"


def test_special_regions_follow_climate():
    assert biomes.biome_at(0.6, 0.0, 0.5, 0.8).key == "volcanic"
    assert biomes.biome_at(0.0, 0.0, 0.5, 0.8).key == "crystalline"
    assert biomes.biome_at(0.0, 0.5, 0.5, -0.8).key == "fungal"
    assert biomes.biome_at(0.0, -0.5, 0.5, -0.8).key != "fungal"  # fungi need moisture


def test_registry_valid_and_ground_colors():
    biomes.validate_content()
    colors = biomes.ground_colors(np.array([0, 1, 2]))
    assert colors.shape == (3, 3) and colors.dtype == np.uint8
    assert all(b.ambient < 60 for b in BIOMES.values())
