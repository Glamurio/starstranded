"""Landmark species live only in their landmark; plants and ground cover never share a tile."""
import numpy as np
import pytest

import biomes
import debug
import landmarks
import planet as pl
import shafts
from ecology import suitability
from chunks import CHUNK_H, CHUNK_W, chunk_origin
from components.plant import Shrub, Tree
from worldgen import GROUND_COVER, sprite_id


@pytest.fixture(scope="module")
def p():
    return pl.generate_planet(5)


def env_of(landmark: str, strength: float = 1.0):
    base = dict(temperature=0.3, moisture=0.2, elevation=0.0, fertility=0.6, light=1.0, water=0.0,
                biome=biomes.BIOME_INDEX["grassland"], landmark=landmarks.LANDMARK_INDEX.get(landmark, 0), landmark_strength=strength)
    return {k: np.array(v) for k, v in base.items()}


def own(p, key):
    return [s for s in list(p.flora) + list(p.fauna) if s.habitat is not None and s.habitat.landmarks == (key,)]


def test_every_landmark_has_its_own_plants_and_animals(p):
    for key in landmarks.LANDMARK_IDS:
        mine = own(p, key)
        assert any(s in p.flora for s in mine), f"{key} has no plant of its own"
        assert any(s in p.fauna for s in mine), f"{key} has no animal of its own"


@pytest.mark.parametrize("key", landmarks.LANDMARK_IDS)
def test_landmark_species_live_nowhere_else(p, key):
    for env in (env_of(""), env_of(next(k for k in landmarks.LANDMARK_IDS if k != key))):
        for species in own(p, key):
            assert float(np.max(suitability(species.habitat, env))) == 0.0, (key, species.key)
    inside = env_of(key)
    for species in own(p, key):
        assert float(np.max(suitability(species.habitat, inside))) > 0.0, (key, species.key)


def test_landmark_species_thin_out_towards_the_edge(p):
    species = own(p, "mushroom_forest")[0]
    core, edge = suitability(species.habitat, env_of("mushroom_forest", 1.0)), suitability(species.habitat, env_of("mushroom_forest", 0.2))
    assert float(core) > float(edge) > 0.0


def find_chunk(key, seed):
    """A chunk key with a lot of ground deep inside the landmark `key`."""
    for cx in range(-12, 13):
        for cy in range(-12, 13):
            env = shafts.environment(seed, (cx, cy))
            number = landmarks.LANDMARK_INDEX[key]
            if ((env["landmark"] == number) & (env["landmark_strength"] > 0.6)).sum() > 400:
                return (cx, cy)
    return None


def test_no_ground_cover_under_trees_or_shrubs_in_landmarks(new_engine, monkeypatch):
    monkeypatch.setattr(debug, "_enabled", True)
    engine = new_engine
    cover = {sprite_id(*cell) for cells in GROUND_COVER.values() for cell in cells}
    cover |= {sprite_id(*cell) for lm in landmarks.LANDMARKS.values() for cell in lm.cover}
    checked = 0
    for key in ("mushroom_forest", "decayed_land", "flowering_meadow"):
        chunk = find_chunk(key, engine.game_world.master_seed)
        if chunk is None:
            continue
        x0, y0 = chunk_origin(chunk)
        debug.teleport(engine, x0 + CHUNK_W // 2, y0 + CHUNK_H // 2)
        world = engine.game_map
        for e in list(world.entities):
            if isinstance(e, (Tree, Shrub)):
                assert int(world.tile_at(e.x, e.y)["light"]["sprite"]) not in cover, (key, e.x, e.y)
                checked += 1
    assert checked > 20


def test_landmark_plants_grow_in_their_landmark_and_nowhere_else(new_engine, monkeypatch):
    monkeypatch.setattr(debug, "_enabled", True)
    engine = new_engine
    found = {}
    for key in ("mushroom_forest", "decayed_land", "cactus_desert"):
        chunk = find_chunk(key, engine.game_world.master_seed)
        if chunk is None:
            continue
        x0, y0 = chunk_origin(chunk)
        debug.teleport(engine, x0 + CHUNK_W // 2, y0 + CHUNK_H // 2)
        found[key] = {e.kind.habitat.landmarks for e in engine.game_map.entities if isinstance(e, (Tree, Shrub))}
    assert found, "no landmark chunk found to test"
    for key, groups in found.items():
        assert (key,) in groups, f"no {key} plant grew in a {key} chunk"
    # near the landing site there is no landmark, so no landmark plant
    debug.teleport(engine, 35, 20)
    near = [e for e in engine.game_map.entities if isinstance(e, (Tree, Shrub)) and 0 <= e.x < CHUNK_W and 0 <= e.y < CHUNK_H]
    assert near and all(not e.kind.habitat.landmarks for e in near)
