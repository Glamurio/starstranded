"""Tree cover follows the biome and the large-scale woodland noise (a regression: grass and scrub had fallen under 1%)."""
import numpy as np

import biomes
import worldgen


def cover_by_biome(seed=12345, span=4):
    noise = worldgen.TerrainNoise(seed)
    seen = {}
    for cx in range(-span, span):
        for cy in range(-span, span):
            x0, y0 = cx * 70, cy * 40
            _, trees = worldgen.generate_terrain(noise, x0, y0, 70, 40)
            kinds = worldgen.base_terrain(noise, x0, y0, 70, 40)
            env = worldgen.environment_for(noise, x0, y0, 70, 40, kinds)
            for b in np.unique(env["biome"]):
                mask = (env["biome"] == b) & (kinds == 1)
                got = seen.setdefault(biomes.BIOME_IDS[b], [0, 0])
                got[0] += int(trees[mask].sum())
                got[1] += int(mask.sum())
    return {k: a / b for k, (a, b) in seen.items() if b > 1500}


def test_open_biomes_have_scattered_trees_and_forests_are_denser():
    cover = cover_by_biome()
    assert cover["grassland"] > 0.03
    assert cover["temperate_forest"] > 0.12
    assert cover["temperate_forest"] > 2.5 * cover["grassland"]
    assert cover["desert"] < 0.04


def test_woodland_varies_within_a_biome():
    noise = worldgen.TerrainNoise(12345)
    stands = noise.woodland(0, 0, 600, 400)
    assert stands.std() > 0.1 and stands.max() - stands.min() > 0.8
