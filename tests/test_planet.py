import numpy as np
import pytest

import biomes
import planet as pl
from ecology import suitability
from naming import CULTURES
from species import PlantCategory


@pytest.fixture(scope="module")
def p():
    return pl.generate_planet(12345, "human")


def test_generation_is_deterministic():
    a, b = pl.generate_planet(7, "human"), pl.generate_planet(7, "human")
    assert a == b
    assert a.name == b.name and [s.name for s in a.flora] == [s.name for s in b.flora]
    assert pl.generate_planet(8, "human").name != a.name or pl.generate_planet(8, "human").flora != a.flora


def test_every_flora_template_has_a_variant_and_a_material(p):
    assert {s.key.split(":")[2] for s in p.flora} == {t.key for t in pl.FLORA_TEMPLATES}
    for s in p.flora:
        assert ((s.material or s.fiber) is not None or s.category.name == "FLOWER") and (s.habitat is not None or s.key.endswith("crop:0"))   # a flower has a bloom instead; the farm crop has no wild habitat
        assert s.material is None or s.material.name == s.name  # the wood is named after its tree


def test_names_are_unique_across_the_planet(p):
    names = [m.name for _, m in p.materials] + [s.name for s in p.flora] + [s.name for s in p.fauna]
    norm = [n.lower().replace(" ", "").replace("-", "") for n in names]
    # wood material shares the tree's name on purpose; everything else is distinct
    wood_names = {m.name for _, m in p.materials if m.id.startswith(("wood:", "fiber:"))}
    others = [n for n in names if n not in wood_names]
    assert len(set(map(str.lower, others))) == len(others)


def test_every_planet_has_what_crafting_needs(p):
    ids = dict(p.materials)
    assert "sand:0" in ids and "clay:0" in ids and "coal:0" in ids
    flint = [i for i in ids if i.startswith("stone:flint")]
    assert flint and ids[flint[0]].hardness >= 8
    porous = [i for i in ids if i.startswith("stone:porous")]
    assert ids[porous[0]].insulation >= 8
    assert len(p.ore_ids) == 3
    for ore in p.ore_ids:
        metal = ids[ids[ore].refines_to]
        assert metal.melting_point > 0
    conductive = ids["metal:conductive"]
    assert conductive.electrical_conductivity >= 9
    assert ids["sand:0"].is_amorphous


@pytest.mark.parametrize("seed", range(6))
def test_every_planet_can_make_a_hatchet_and_has_fuel_wood(seed):
    planet = pl.generate_planet(seed)
    woods = [s.material for s in planet.flora if s.material]
    assert any(w.toughness >= 5 for w in woods), "no handle wood"
    assert any(w.combustibility >= 5 for w in woods), "no fuel wood"
    fibers = [s.fiber for s in planet.flora if s.fiber]
    assert any(f.tenacity >= 5 for f in fibers), "no binding fibre"


def test_species_only_spawn_where_their_habitat_allows(p):
    def env(**kw):
        base = dict(temperature=0.0, moisture=0.0, elevation=0.0, fertility=0.6, light=1.0, water=0.0, biome=biomes.BIOME_INDEX["grassland"])
        base.update(kw)
        return {k: np.array(v) for k, v in base.items()}
    desert = env(temperature=0.8, moisture=-0.8, fertility=0.05, biome=biomes.BIOME_INDEX["desert"])
    pool, w = p.species_weights(desert, PlantCategory.TREE)
    live = {s.key.split(":")[2] for s, x in zip(pool, w) if x > 0}
    assert "cactus" in live and "conifer" not in live and "broadleaf" not in live
    glacier = env(temperature=-1.2, moisture=0.0, fertility=0.0, biome=biomes.BIOME_INDEX["glacial"])
    pool, w = p.species_weights(glacier, PlantCategory.TREE)
    assert not (w > 0).any()
    fauna, fw = p.fauna_weights(desert)
    live = {s.key.split(":")[2] for s, x in zip(fauna, fw) if x > 0}
    assert "serpent" in live and "grazer" not in live


def test_cultures_name_the_same_planet_differently():
    names = {c: pl.generate_planet(3, c).flora[0].name for c in CULTURES}
    assert len(set(names.values())) == len(CULTURES)
    # but the world itself (materials' properties) is identical
    a, b = pl.generate_planet(3, "human"), pl.generate_planet(3, "mau")
    assert [m.hardness for _, m in a.materials] == [m.hardness for _, m in b.materials]
