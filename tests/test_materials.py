import pytest

import materials as m
from damage import DamageType
from materials import Burn, Family, Material
from material_helpers import COAL, COPPER, FLINT, GRASS, OAKISH, SAND, VINE


def test_material_validation_rejects_bad_data():
    with pytest.raises(AssertionError):
        Material("x", "X", Family.WOOD, (1, 2, 3), hardness=11)
    with pytest.raises(AssertionError):
        Material("x", "X", Family.WOOD, (1, 2, 300))
    with pytest.raises(AssertionError):
        Material("x", "X", Family.FUEL, (1, 2, 3), burn_yield=5)  # fuel without combustibility / duration
    with pytest.raises(AssertionError):
        Material("x", "X", Family.SAND, (1, 2, 3), is_amorphous=True)  # amorphous but unmeltable


def test_flammability_and_combustibility_are_different_things():
    assert m.ignition_temp(GRASS) < m.ignition_temp(COAL)  # grass ignites far more easily
    assert m.ignite(GRASS, 400) is Burn.FLASH               # ...but only flashes (poor fuel)
    assert m.ignite(COAL, 400) is Burn.NONE                 # coal needs a hotter source
    assert m.ignite(COAL, 600) is Burn.SUSTAINED
    assert m.ignite(FLINT, 2000) is Burn.NONE               # stone does not burn at all
    assert m.burn_energy(COAL) > m.burn_energy(OAKISH) > m.burn_energy(GRASS)
    assert m.burn_turns(COAL, 2) == 40 and m.burn_turns(GRASS) == 1 and m.burn_turns(GRASS, burn=Burn.FLASH) == m.FLASH_TURNS


def test_oxygen_limits_combustion():
    assert m.ignite(OAKISH, 500, oxygen=0.21) is Burn.SUSTAINED
    assert m.ignite(OAKISH, 500, oxygen=0.10) is Burn.FLASH
    assert m.ignite(OAKISH, 500, oxygen=0.01) is Burn.NONE


def test_incandescence_glows_above_threshold():
    glowing = Material("g", "Glowrock", Family.STONE, (200, 80, 20), hardness=5, incandescence=8)
    assert m.glow_radius(glowing, 100) == 0
    assert m.glow_radius(glowing, m.glow_threshold(glowing)) >= 3
    assert m.glow_radius(FLINT, 5000) == 0


def test_amorphous_materials_turn_glassy_when_melted():
    glass = m.melt_and_cool(SAND)
    assert glass.family is Family.GLASS and glass.transparency > SAND.transparency and glass.toughness < SAND.toughness
    cast = m.melt_and_cool(COPPER)
    assert cast.family is Family.METAL and cast.tenacity == COPPER.tenacity + 1
    with pytest.raises(ValueError):
        m.melt_and_cool(FLINT)


def test_structure_one_high_property_does_not_compensate():
    glass = m.melt_and_cool(SAND)
    lead = Material("l", "Lead", Family.METAL, (80, 80, 90), hardness=1.5, toughness=3, tenacity=2, density=9.5, melting_point=327)
    assert m.structural_rating(OAKISH) > m.structural_rating(glass)
    assert m.structural_rating(OAKISH) > m.structural_rating(lead)
    assert not m.can_bear_load(lead) and not m.can_bear_load(glass)
    assert m.can_bear_load(OAKISH) and not m.can_bear_load(OAKISH, span=5)
    assert m.radiation_shielding(lead) > m.radiation_shielding(OAKISH)


def test_damage_interaction_uses_the_documented_properties():
    wood = OAKISH
    # sharp: resisted by hardness and toughness; a hard edge cuts, a soft one does worse
    hard_edge = {"hardness": 8, "toughness": 5}
    soft_edge = {"hardness": 2, "toughness": 5}
    assert m.attack_factor(DamageType.SHARP, hard_edge, wood) > m.attack_factor(DamageType.SHARP, soft_edge, wood)
    # blunt: resisted by toughness and density; mass beats toughness-poor targets
    heavy = {"density": 9, "toughness": 6}
    light = {"density": 2, "toughness": 6}
    assert m.attack_factor(DamageType.BLUNT, heavy, wood) > m.attack_factor(DamageType.BLUNT, light, wood)
    # pierce: resisted by hardness and tenacity
    assert m.attack_factor(DamageType.PIERCE, {"hardness": 8, "tenacity": 6}, VINE) > m.attack_factor(DamageType.PIERCE, {"hardness": 8, "tenacity": 6}, COPPER)
    # bounded
    for t in DamageType:
        f = m.attack_factor(t, {"hardness": 10, "toughness": 10, "density": 10, "tenacity": 10}, GRASS)
        assert 0.2 <= f <= 3.0
    # the same target differs by damage type (not one universal multiplier)
    assert len({round(m.attack_factor(t, None, FLINT), 3) for t in DamageType}) > 1


def test_composition_rules_and_colour():
    parts = {"head": FLINT, "handle": OAKISH, "binding": VINE}
    rules = {"hardness": ("role", "head"), "toughness": ("min", ("head", "handle")), "elasticity": ("mean", {"handle": 3, "binding": 1})}
    props = m.derive_properties(parts, rules)
    assert props["hardness"] == FLINT.hardness
    assert props["toughness"] == min(FLINT.toughness, OAKISH.toughness)
    assert props["elasticity"] == pytest.approx((4 * 3 + 5 * 1) / 4)
    assert props["density"] == pytest.approx((6 + 5 + 0) / 3)  # default: plain mean
    assert m.derive_properties(parts, rules, quality=1.5)["hardness"] == pytest.approx(min(10, FLINT.hardness * 1.5))
    colour = m.blend_colors(parts, {"head": 3, "handle": 1})
    assert colour[0] == int((FLINT.color[0] * 3 + OAKISH.color[0]) / 4)


def test_every_property_has_a_reading_rule():
    assert set(m.PROPERTY_KEYS) == set(m.PROPERTY_READING)


def test_clay_fires_into_ceramic():
    clay = Material("c", "Red clay", Family.CLAY, (170, 90, 60), hardness=2, toughness=3, tenacity=3, density=4, insulation=3)
    brick = m.fire_clay(clay)
    assert brick.family is Family.CERAMIC and brick.hardness == 5 and brick.insulation == 4 and brick.tenacity == 0
