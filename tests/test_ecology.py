import numpy as np
import pytest

from biomes import BIOME_INDEX
from ecology import Habitat, membership, suitability


def env(**kw):
    base = dict(temperature=0.0, moisture=0.0, elevation=0.0, fertility=0.5, light=1.0, water=0.0, biome=BIOME_INDEX["plains"])
    base.update(kw)
    return base


def test_membership_trapezoid():
    assert membership(0.5, (0, 1)) == 1.0
    assert membership(-0.1, (0, 1)) == pytest.approx(0.5)
    assert membership(-0.3, (0, 1)) == 0.0
    assert membership(1.1, (0, 1)) == pytest.approx(0.5)


def test_every_requirement_is_binding():
    cactus = Habitat(temperature=(0.3, 1.0), moisture=(-1.0, -0.1))
    assert suitability(cactus, env(temperature=0.6, moisture=-0.5)) == 1.0
    assert suitability(cactus, env(temperature=-0.5, moisture=-0.5)) == 0.0   # too cold
    assert suitability(cactus, env(temperature=0.6, moisture=0.5)) == 0.0     # too wet


def test_substrate_restricts_to_listed_biomes():
    bog_plant = Habitat(substrate=("bog",))
    assert suitability(bog_plant, env(biome=BIOME_INDEX["bog"])) == 1.0
    assert suitability(bog_plant, env(biome=BIOME_INDEX["desert"])) == 0.0


def test_light_and_water_and_arrays():
    shade = Habitat(light=(0.0, 0.3))
    assert suitability(shade, env(light=1.0)) == 0.0
    reed = Habitat(water=(0.7, 1.0))
    t = np.linspace(0, 1, 5)
    out = suitability(reed, env(water=t))
    assert out.shape == (5,) and out[0] == 0.0 and out[-1] == 1.0 and np.all(np.diff(out) >= 0)


def test_a_substrate_may_name_a_biome_or_a_whole_family():
    from biomes import BIOME_INDEX
    shapes = np.zeros(3)
    env = dict(temperature=shapes, moisture=shapes, elevation=shapes, fertility=np.ones(3), light=np.ones(3), water=shapes,
               biome=np.array([BIOME_INDEX["plains"], BIOME_INDEX["fungal_forest"], BIOME_INDEX["glass_desert"]]))
    assert suitability(Habitat(substrate=("fungal",)), env).tolist() == [0.0, 1.0, 0.0]            # a family
    assert suitability(Habitat(substrate=("glass_desert",)), env).tolist() == [0.0, 0.0, 1.0]      # one biome
    assert suitability(Habitat(substrate=("mushroom_forest",)), env).tolist() == [0.0, 1.0, 0.0]   # the old landmark name still means the fungal family
    assert suitability(Habitat(substrate=("nonexistent",)), env).tolist() == [1.0, 1.0, 1.0]     # unknown: no restriction


def test_a_region_border_shares_the_neighbours_species():
    from biomes import BIOME_INDEX
    env = dict(temperature=np.zeros(2), moisture=np.zeros(2), elevation=np.zeros(2), fertility=np.ones(2), light=np.ones(2), water=np.zeros(2),
               biome=np.full(2, BIOME_INDEX["plains"]), other=np.full(2, BIOME_INDEX["fungal_forest"]), edge=np.array([0.0, 0.4]))
    assert suitability(Habitat(substrate=("fungal",)), env).tolist() == pytest.approx([0.0, 0.4])
