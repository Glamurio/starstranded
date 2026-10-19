"""Underground biomes: regions of the caves with their own look and creatures, the same on both sides of a chunk border."""
import random

import numpy as np

import planet as pl
import shafts
import structures
import underground as ug
from chunks import CHUNK_H, CHUNK_W

MASTER = 1234


def _share():
    counts = np.zeros(len(ug.UBIOME_IDS))
    for kx in range(-6, 7):
        for ky in range(-6, 7):
            counts += np.bincount(ug.field(MASTER, -1, (kx, ky)).ravel(), minlength=len(ug.UBIOME_IDS))
    return dict(zip(ug.UBIOME_IDS, counts / counts.sum()))


def test_every_biome_is_common_enough_and_none_is_everything():
    share = _share()
    for key in ug.UBIOME_IDS:
        if key != "ruins":
            assert 0.05 < share[key] < 0.5, share
    assert share["ruins"] > 0


def test_the_biome_under_a_chunk_border_is_the_same_from_both_sides():
    big = ug.field(MASTER, -1, (2, 3), margin=4)
    right = ug.field(MASTER, -1, (3, 3), margin=0)
    assert np.array_equal(big[4 + CHUNK_W:4 + CHUNK_W + 4, 4:4 + CHUNK_H], right[:4])      # (the margin of one chunk is the first columns of the next)


def test_the_chunk_under_a_precursor_ruin_is_the_ruins_biome():
    key = next(iter(structures.ruin_chunks(MASTER)))
    biome = ug.field(MASTER, -1, key)
    assert biome[CHUNK_W // 2, CHUNK_H // 2] == ug.RUINS and (biome == ug.RUINS).mean() > 0.4 and (biome != ug.RUINS).any()
    assert biome[0, 0] != ug.RUINS                      # an oval, not the whole chunk: no hard chunk-shaped edge


def test_cave_floors_are_coloured_by_their_biome():
    seen = set()
    for kx in range(-3, 4):
        for ky in range(-3, 4):
            tiles = shafts.cave_layer(MASTER, -1, (kx, ky))
            biome = ug.field(MASTER, -1, (kx, ky))
            for i, key in enumerate(ug.UBIOME_IDS):
                mask = (biome == i) & tiles["walkable"] & (tiles["light"]["bg"].sum(axis=-1) == sum(ug.UBIOMES[key].floor_bg))
                if mask.any():
                    seen.add(key)
    assert len(seen) >= 5, seen


def test_cave_creatures_live_below_only_and_every_biome_has_some():
    planet = pl.generate_planet(5, "human")
    surface, _ = planet.fauna_weights({"temperature": np.zeros(1), "moisture": np.zeros(1), "elevation": np.zeros(1), "fertility": np.ones(1),
                                       "light": np.ones(1), "water": np.zeros(1), "biome": np.zeros(1, dtype=int)})
    assert not any(s.key.split(":")[-1].startswith("cave_") for s in surface)
    for key in ug.UBIOME_IDS:
        species, weights = planet.cave_fauna(key)
        assert species and len(species) == len(weights), key
        assert all(s.habitat is None for s in species)


def test_cave_animals_have_their_own_names_and_are_scannable_like_the_rest():
    planet = pl.generate_planet(5, "human")
    names = [s.name for s in planet.fauna if s.key.split(":")[-1].startswith("cave_")]
    assert len(names) == len(set(names)) == len(pl.CAVE_FAUNA)
    assert all(any(form in name for form in ("beetle", "moth", "slug", "bat", "worm", "crab")) for name in names)


def test_visitors_are_rare_below_and_commoner_in_the_ruins():
    assert ug.VISITORS["default"][0] + ug.VISITORS["default"][1] < 0.15
    assert sum(ug.VISITORS["ruins"]) > 3 * sum(ug.VISITORS["default"])


def test_cave_ground_is_named_after_its_biome_on_hover(small_world):
    import terrain_text
    import underground
    engine = small_world()
    world = engine.game_map
    world.z = -1
    master = engine.game_world.master_seed
    name = terrain_text.describe(world, 3, 3)
    assert name == underground.UBIOMES[underground.biome_at(master, -1, 3, 3)].name
    world.z = 0
    assert terrain_text.describe(world, 3, 3) is None
