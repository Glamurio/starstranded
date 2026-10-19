"""Animals are spawned by what the ground suits: every species can live somewhere, and different environments favour different ones."""
import numpy as np

import biomes
import planet as pl
import worldgen


def _environment(seed):
    noise = worldgen.TerrainNoise(seed)
    out = {}
    for x0, y0 in ((-600, -600), (0, -600), (-600, 0), (0, 0), (600, 0), (-600, 600)):
        kinds = worldgen.base_terrain(noise, x0, y0, 200, 200)
        env = worldgen.environment_for(noise, x0, y0, 200, 200, kinds)
        land = kinds == 1
        for k, v in env.items():
            out.setdefault(k, []).append(v[land])
    return {k: np.concatenate(v) for k, v in out.items()}


def test_every_baseline_species_has_somewhere_to_live_and_environments_differ():
    planet = pl.generate_planet(41, "human")
    env = _environment(41)
    pool, weights = planet.fauna_weights(env)
    base = [i for i, s in enumerate(pool) if "." not in s.key.split("fauna:")[1]]
    assert base
    for i in base:
        assert (weights[i] > 0).sum() > 50, f"{pool[i].name} can hardly spawn anywhere"
    # the favourite species of each biome is not the same everywhere
    favourites = {}
    for index, key in enumerate(biomes.BIOME_IDS):
        here = env["biome"] == index
        if here.sum() < 200:
            continue
        share = weights[base][:, here].mean(axis=1)
        if share.sum() > 0:
            favourites[key] = int(np.argmax(share))
    assert len(set(favourites.values())) >= 3, favourites
