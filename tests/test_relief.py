"""Relief: continents, seas and ranges, and a landing site that is always dry, mild and has water nearby."""
import numpy as np
import pytest

import biomes
import relief
import worldgen

SEEDS = (1, 2, 3, 5, 11, 99, 12345)


def terrain(seed, x0, y0, width, height):
    noise = worldgen.TerrainNoise(seed)
    kinds = worldgen.base_terrain(noise, x0, y0, width, height)
    return noise, kinds, worldgen.environment_for(noise, x0, y0, width, height, kinds)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_landing_site_is_dry_open_and_mild(seed):
    noise, kinds, env = terrain(seed, 0, 0, 70, 40)
    assert not (kinds == 0).any(), "water on the landing chunk"
    assert (kinds == 1).mean() > 0.9, "mostly open ground at the landing site"
    centre = int(env["biome"][35, 20])
    assert biomes.BIOME_IDS[centre] not in ("glacial", "desert", "badlands", "tundra")
    assert not (env["landmark"] > 0).any()


@pytest.mark.parametrize("seed", SEEDS)
def test_there_is_water_within_a_walk_of_the_landing_site(seed):
    noise, kinds, env = terrain(seed, -60, -60, 260, 180)
    assert (kinds == 0).sum() >= 60


def test_seas_and_ranges_cover_a_sensible_share_of_the_world():
    for seed in (1, 5, 12345):
        noise = worldgen.TerrainNoise(seed)
        wet = relief.basin_height(noise, -1000, -600, 2000, 1200) < relief.SEA_LEVEL
        rock = relief.elevation(noise, -1000, -600, 2000, 1200) > relief.ROCK_LEVEL
        assert 0.05 < wet.mean() < 0.40, (seed, wet.mean())
        assert 0.02 < rock.mean() < 0.20, (seed, rock.mean())


def test_relief_is_the_same_however_the_world_is_cut():
    noise = worldgen.TerrainNoise(5)
    whole = relief.elevation(noise, -300, -200, 600, 400)
    part = relief.elevation(noise, -100, -50, 200, 120)
    assert np.allclose(whole[200:400, 150:270], part)


def test_mountain_air_is_colder():
    noise = worldgen.TerrainNoise(12345)
    w, h = 1200, 600
    kinds = worldgen.base_terrain(noise, -600, -300, w, h)
    env = worldgen.environment_for(noise, -600, -300, w, h, kinds)
    high = env["elevation"] > 0.9
    plain = (env["elevation"] > 0.0) & (env["elevation"] < 0.3)
    assert high.any() and plain.any()
    base = noise.temperature(-600, -300, w, h)
    assert (env["temperature"][high] - base[high]).mean() < -0.2
    assert abs((env["temperature"][plain] - base[plain]).mean()) < 0.05


def test_land_is_reachable_through_or_around_the_ranges():
    """Passes and gaps keep the mountains from walling the world: most dry ground near the landing site can be walked to."""
    import tcod
    import worldgen
    for seed in (1, 5, 99):
        noise = worldgen.TerrainNoise(seed)
        w, h = 500, 300
        x0, y0 = 35 - w // 2, 20 - h // 2
        walk = worldgen.base_terrain(noise, x0, y0, w, h) == 1
        cost = walk.astype(np.int32)
        dist = np.full((w, h), np.iinfo(np.int32).max, dtype=np.int32)
        dist[w // 2, h // 2] = 0
        tcod.path.dijkstra2d(dist, cost, 2, 3, out=dist)
        reach = (dist < np.iinfo(np.int32).max) & walk
        assert reach.sum() >= 0.85 * walk.sum(), seed


def test_ridges_have_passes():
    import worldgen
    noise = worldgen.TerrainNoise(1234)
    gaps = relief.passes(noise, -400, -400, 800, 800)
    assert gaps.min() < 0.4 and gaps.max() > 0.95


def test_chasms_are_open_air_in_high_rock_only():
    import worldgen
    noise = worldgen.TerrainNoise(1234)
    seen = 0
    for x in range(-600, 600, 140):
        for y in range(-350, 350, 80):
            tiles, trees = worldgen.generate_terrain(noise, x, y, 70, 40)
            chasm = tiles["open"]
            seen += int(chasm.sum())
            assert not tiles["walkable"][chasm].any() and not trees[chasm].any()
    assert seen > 0
