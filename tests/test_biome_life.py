"""Native species live only in the biomes that list them; a biome's own plants thin out and mix over a border; plants and ground cover never share a tile."""
import numpy as np
import pytest

import biomes
import debug
import planet as pl
import shafts
from chunks import CHUNK_H, CHUNK_W, chunk_origin
from components.plant import Shrub, Tree
from ecology import suitability
from worldgen import cover_sprites, sprite_id


@pytest.fixture(scope="module")
def p():
    return pl.generate_planet(5)


def env_of(biome: str, other: str = "", edge: float = 0.0):
    base = dict(temperature=0.3, moisture=0.2, elevation=0.0, fertility=0.6, light=1.0, water=0.0, biome=biomes.BIOME_INDEX[biome])
    if other:
        base.update(other=biomes.BIOME_INDEX[other], edge=edge)
    return {k: np.array(v) for k, v in base.items()}


def live(p, env, category=None):
    pool, weights = p.species_weights(env, category)
    return {s.key.split(":")[2] for s, w in zip(pool, weights) if float(np.max(w)) > 0}


def test_native_plants_grow_exactly_in_the_biomes_that_list_them(p):
    native = {t.key for t in pl.FLORA_TEMPLATES if t.native}
    for key in biomes.BIOME_IDS:
        found = live(p, env_of(key)) | live(p, env_of(key), pl.PlantCategory.FLOWER)
        assert {k for k in found if k in native} == {k for k in biomes.BIOMES[key].plants if k in native}, key


def test_a_biome_that_lists_only_its_own_plants_has_nothing_else(p):
    only = [b for b in biomes.BIOMES.values() if b.plants_only]
    assert only
    for b in only:
        assert live(p, env_of(b.key)) | live(p, env_of(b.key), pl.PlantCategory.FLOWER) <= set(b.plants), b.key


def test_a_fungal_forest_holds_only_fungi_and_a_plain_has_ordinary_plants(p):
    assert live(p, env_of("fungal_forest")) <= set(biomes.BIOMES["fungal_forest"].plants) | {"bush", "reeds", "marsh_flower"}
    assert not {"fungal_tree", "giant_cap", "glowcap"} & live(p, env_of("plains"))


def test_every_family_has_animals_of_its_own_that_live_nowhere_else(p):
    for family in pl.FAMILY_FAUNA:
        mine = [s for s in p.fauna if s.habitat is not None and s.habitat.substrate == (family,)]
        assert mine, family
        inside = [k for k in biomes.FAMILY_MEMBERS[family] if not biomes.BIOMES[k].coastal or family == "coast"][0]
        outside = "plains" if family != "grass" else "desert"
        for s in mine:
            assert float(np.max(suitability(s.habitat, env_of(inside)))) > 0.0, (family, s.key)
            assert float(np.max(suitability(s.habitat, env_of(outside)))) == 0.0, (family, s.key)


def test_species_mix_across_a_region_border(p):
    fungal_only = {k for k in biomes.BIOMES["fungal_forest"].plants if pl.plant_factors(k)[biomes.BIOME_INDEX["plains"]] == 0}
    deep = live(p, env_of("plains"))
    edge = live(p, env_of("plains", "fungal_forest", 0.3))
    assert not fungal_only & deep and fungal_only & edge
    pool, w0 = p.species_weights(env_of("plains", "fungal_forest", 0.1))
    _, w1 = p.species_weights(env_of("plains", "fungal_forest", 0.4))
    index = next(i for i, s in enumerate(pool) if s.key.split(":")[2] in fungal_only)
    assert float(np.max(w1[index])) > float(np.max(w0[index])) > 0.0


def find_chunk(family, seed):
    """A chunk key with a lot of ground deep inside a region of a biome family."""
    index = np.array([i for i, k in enumerate(biomes.BIOME_IDS) if biomes.BIOMES[k].family == family])
    for cx in range(-14, 15, 2):
        for cy in range(-14, 15, 2):
            env = shafts.environment(seed, (cx, cy))
            if (np.isin(env["biome"], index) & (env["edge"] < 0.05)).sum() > 1200:
                return (cx, cy)
    return None


def test_no_ground_cover_under_trees_or_shrubs(new_engine, monkeypatch):
    monkeypatch.setattr(debug, "_enabled", True)
    engine = new_engine
    cover = cover_sprites()
    checked = 0
    for family in ("fungal", "forest", "wet", "grass"):
        chunk = find_chunk(family, engine.game_world.master_seed)
        if chunk is None:
            continue
        x0, y0 = chunk_origin(chunk)
        debug.teleport(engine, x0 + CHUNK_W // 2, y0 + CHUNK_H // 2)
        world = engine.game_map
        for e in list(world.entities):
            if isinstance(e, (Tree, Shrub)):
                assert int(world.tile_at(e.x, e.y)["light"]["sprite"]) not in cover, (family, e.x, e.y)
                checked += 1
    assert checked > 20


def test_native_plants_grow_in_their_region_and_not_at_the_landing_site(new_engine, monkeypatch):
    monkeypatch.setattr(debug, "_enabled", True)
    engine = new_engine
    native = {t.key for t in pl.FLORA_TEMPLATES if t.native}
    checked = 0
    for family in ("fungal", "crystal", "volcanic", "decay"):
        chunk = find_chunk(family, engine.game_world.master_seed)
        if chunk is None:
            continue
        x0, y0 = chunk_origin(chunk)
        debug.teleport(engine, x0 + CHUNK_W // 2, y0 + CHUNK_H // 2)
        kinds = {e.kind.key.split(":")[2] for e in engine.game_map.entities if isinstance(e, (Tree, Shrub)) and e.kind.key.startswith("planet:flora")}
        assert kinds & native, f"nothing native grew in a {family} chunk"
        checked += 1
    assert checked >= 1, "no region found to test"
