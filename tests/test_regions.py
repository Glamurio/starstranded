"""Regions: large, deterministic, independent of how the world is cut into chunks, mild around the landing site."""
import numpy as np
import pytest

import biomes
import regions
import relief
import worldgen

SEEDS = (1, 2, 3, 5, 11, 99, 12345)


def test_a_region_does_not_depend_on_the_chunk_that_asks():
    for seed in (3, 12345):
        noise = worldgen.TerrainNoise(seed)
        big = regions.field(noise, -140, -80, 280, 160)
        for cx in (-2, 0, 1):
            for cy in (-1, 1):
                x0, y0 = cx * 70, cy * 40
                small = regions.field(noise, x0, y0, 70, 40)
                sl = (slice(x0 + 140, x0 + 210), slice(y0 + 80, y0 + 120))
                assert np.array_equal(big.biome[sl], small.biome)
                assert np.array_equal(big.other[sl], small.other)
                assert np.allclose(big.edge[sl], small.edge)
                assert np.array_equal(big.region[sl], small.region)


def test_the_same_seed_gives_the_same_regions_in_any_order():
    noise = worldgen.TerrainNoise(5)
    first = regions.field(noise, 900, -400, 70, 40).biome.copy()
    regions.clear_caches()
    for x in (2000, -3000, 0):
        regions.field(noise, x, 0, 70, 40)
    assert np.array_equal(regions.field(worldgen.TerrainNoise(5), 900, -400, 70, 40).biome, first)


@pytest.mark.parametrize("seed", SEEDS)
def test_regions_are_large_coherent_areas(seed):
    noise = worldgen.TerrainNoise(seed)
    f = regions.field(noise, 300, 300, 700, 400)
    ids, counts = np.unique(f.region, return_counts=True)
    assert counts.max() > 8000, "some region is big"
    assert counts[counts < 300].sum() < 0.12 * f.region.size, "slivers are rare"
    assert 0.0 <= f.edge.min() and f.edge.max() <= 0.5
    assert (f.edge[f.biome == f.other] == 0).all()


@pytest.mark.parametrize("seed", SEEDS)
def test_the_landing_site_lies_in_mild_country(seed):
    noise = worldgen.TerrainNoise(seed)
    f = regions.field(noise, int(relief.SPAWN[0]) - 120, int(relief.SPAWN[1]) - 120, 240, 240)
    for index in np.unique(np.concatenate([f.biome.ravel(), f.other.ravel()])):
        assert regions.mild(biomes.BIOMES[biomes.BIOME_IDS[index]]), biomes.BIOME_IDS[index]


def test_seeds_show_variety_across_families():
    seen, families = set(), set()
    for seed in SEEDS:
        f = regions.field(worldgen.TerrainNoise(seed), 0, 0, 1000, 600)
        kinds = {biomes.BIOME_IDS[i] for i in np.unique(f.biome)}
        assert len({biomes.BIOMES[k].family for k in kinds}) >= 3, seed
        seen |= kinds
        families |= {biomes.BIOMES[k].family for k in kinds}
    assert len(seen) >= 25 and len(families) >= 9


def test_the_ground_colour_blends_across_a_border():
    noise = worldgen.TerrainNoise(3)
    area = (0, 0, 400, 300)
    kinds = np.ones((400, 300), dtype=np.int8)
    env = worldgen.environment_for(noise, *area, kinds)
    ground = worldgen.ground_colours(noise, area, env).astype(int)
    step = np.abs(np.diff(ground, axis=0)).sum(axis=2)
    assert np.percentile(step, 99.5) < 90, "no hard seam in the ground colours"
