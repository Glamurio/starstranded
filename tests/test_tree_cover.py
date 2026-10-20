"""Tree cover follows the biome and the large-scale woodland noise (a regression: grass and scrub had fallen under 1%)."""
import numpy as np

import biomes
import worldgen


def cover_by_family(seeds=(1, 2, 3, 4, 5, 6), span=3):
    seen = {}
    for seed in seeds:
        noise = worldgen.TerrainNoise(seed)
        for cx in range(-span, span):
            for cy in range(-span, span):
                x0, y0 = cx * 140 + 300, cy * 80 + 300
                _, trees = worldgen.generate_terrain(noise, x0, y0, 70, 40)
                kinds = worldgen.base_terrain(noise, x0, y0, 70, 40)
                env = worldgen.environment_for(noise, x0, y0, 70, 40, kinds)
                for b in np.unique(env["biome"]):
                    mask = (env["biome"] == b) & (kinds == 1) & (env["edge"] < 0.1)
                    got = seen.setdefault(biomes.BIOMES[biomes.BIOME_IDS[b]].family, [0, 0])
                    got[0] += int(trees[mask].sum())
                    got[1] += int(mask.sum())
    return {k: a / b for k, (a, b) in seen.items() if b > 1500}


def test_forests_are_denser_than_grassland_and_deserts_are_nearly_bare():
    cover = cover_by_family()
    assert cover["forest"] > 0.10
    assert cover["forest"] > 2.0 * cover["grass"]
    assert cover["grass"] > 0.01
    if "arid" in cover:
        assert cover["arid"] < 0.05


def test_woodland_varies_within_a_biome():
    noise = worldgen.TerrainNoise(12345)
    stands = noise.woodland(0, 0, 600, 400)
    assert stands.std() > 0.1 and stands.max() - stands.min() > 0.8
