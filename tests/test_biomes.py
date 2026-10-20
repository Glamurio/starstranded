"""The biome catalogue: what every biome is, that they are distinct from each other and that what they name exists."""
import json
import os

import numpy as np

import biomes
import planet
from biomes import BIOME_IDS, BIOMES, FAMILIES


def test_the_catalogue_has_at_least_fifty_distinct_biomes():
    assert len(BIOMES) >= 50
    assert len(set(BIOME_IDS)) == len(BIOME_IDS)
    signatures = {(b.family, b.ground, b.ground_alt, tuple(sorted(b.plants)), tuple(sorted(b.scenery)), b.cover) for b in BIOMES.values()}
    assert len(signatures) == len(BIOMES), "two biomes look and grow exactly the same"


def test_registry_valid_and_ground_colors():
    biomes.validate_content()
    colors = biomes.ground_colors(np.array([0, 1, 2]))
    assert colors.shape == (3, 3) and colors.dtype == np.uint8
    assert all(b.ambient < 80 and b.night_drop >= 0 for b in BIOMES.values())


def test_every_biome_is_described_and_in_a_known_family():
    for b in BIOMES.values():
        assert b.name and len(b.description) > 8 and len(b.features) > 10, b.key
        assert b.family in FAMILIES, b.key
    assert {"grass", "arid", "forest", "fungal", "crystal", "volcanic", "decay", "alien", "wet", "cold", "urban"} <= {b.family for b in BIOMES.values()}


def test_every_sprite_a_biome_names_is_on_the_sheet():
    for b in BIOMES.values():
        for col, row in b.cover + b.texture:
            assert 0 <= col < 125 and 0 <= row < 50, (b.key, col, row)


def test_the_plants_a_biome_lists_exist_and_every_native_plant_has_a_home():
    planet.validate_plants()


def test_music_pools_named_by_biomes_exist_in_the_manifest():
    import music
    pools = set(music.load_manifest()["pools"])
    for b in BIOMES.values():
        for name in (b.music_pool, b.generic_pool):
            assert not name or name in pools, (b.key, name)


def test_families_name_valid_traits_and_underground_biomes():
    import underground
    for f in FAMILIES.values():
        assert all(t in biomes.TRAITS for t in f.traits), f.key
        assert f.under in underground.UBIOMES, f.key
    for b in BIOMES.values():
        assert all(t in biomes.TRAITS for t in b.traits), b.key
        assert b.under_key in underground.UBIOMES, b.key


def test_variants_flag_a_hot_dry_tile_of_a_biome_and_name_it():
    b = BIOME_IDS.index("plains")
    mid_t, mid_m = BIOMES["plains"].mid_temperature, BIOMES["plains"].mid_moisture
    bits = biomes.variant_bits(np.array([mid_t + 0.5, mid_t, mid_t - 0.5]), np.array([mid_m - 0.5, mid_m, mid_m + 0.5]), np.array([b, b, b]))
    assert bits[0] & biomes.VARIANT_BITS["hot"] and bits[0] & biomes.VARIANT_BITS["dry"]
    assert bits[1] == 0
    assert bits[2] & biomes.VARIANT_BITS["cold"] and bits[2] & biomes.VARIANT_BITS["wet"]
    assert biomes.variant_name("plains", int(bits[0])) == BIOMES["plains"].name       # (a variant does not rename the biome)
    biomes.NAME_VARIANTS = True
    try:
        assert biomes.variant_name("plains", int(bits[0])) == "Hot, Dry plains"
    finally:
        biomes.NAME_VARIANTS = False


def test_native_plants_take_on_the_traits_of_the_country_they_grow_in():
    assert "volcanic" in biomes.plant_traits("ash_shrub") and "hot" in biomes.plant_traits("ash_shrub")
    assert "cold" in biomes.plant_traits("frost_tree")
    heat, cold = [], []
    for seed in range(1, 7):
        p = planet.generate_planet(seed)
        flora = {s.key.split(":")[2]: s for s in p.flora}
        heat.append(flora["ash_shrub"].fiber.flammability)
        cold.append(flora["frost_tree"].material.insulation - flora["broadleaf"].material.insulation)
    assert np.mean(heat) < 5.0          # (a plant of volcanic ground is hard to light; shrubs elsewhere are 6-8)
    assert np.mean(cold) > 0.5


def test_regional_animals_carry_their_familys_traits():
    wild = {"hot": [], "cold": []}
    for seed in range(1, 7):
        p = planet.generate_planet(seed)
        by = {s.key.split(":")[2]: s for s in p.fauna}
        wild["hot"].append(by["strider.volcanic"].hide.flammability)
        wild["cold"].append(by["grazer.cold"].hide.insulation - by["grazer"].hide.insulation)
    assert np.mean(wild["hot"]) < 0.5 and np.mean(wild["cold"]) > 0.5      # (scales of hot rock hardly burn; the cold one is better insulated)
