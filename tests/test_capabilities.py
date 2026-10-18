import pytest

import capabilities as cap
from capabilities import CapabilitySet, Grant, grants


def test_registry_is_consistent():
    cap.validate_content()


def test_unknown_tag_is_rejected():
    with pytest.raises(KeyError):
        Grant("not_a_tag")
    with pytest.raises(KeyError):
        CapabilitySet().has("nope")


def test_agility_magnitude_overrides_default_and_is_reusable():
    mau = CapabilitySet(grants(("increased_agility", 2.0)))
    boots = CapabilitySet(grants(("increased_agility", 1.25)))
    plain = CapabilitySet(grants("increased_agility"))
    assert mau.stat("move_speed") == 2.0
    assert boots.stat("move_speed") == 1.25
    assert plain.stat("move_speed") == 1.5  # tag default
    assert CapabilitySet().stat("move_speed") == 1.0


def test_conditional_effect_only_applies_in_context():
    human = CapabilitySet(grants("night_aversion"))
    assert human.stat("move_speed") == 1.0
    assert human.stat("move_speed", dark=False) == 1.0
    assert human.stat("move_speed", dark=True) == 0.5


def test_effects_stack_multiplicatively_and_additively():
    s = CapabilitySet(grants(("increased_agility", 2.0), "night_aversion", "clawed"))
    assert s.stat("move_speed", dark=True) == 1.0  # 2.0 * 0.5
    assert s.stat("unarmed_damage") == 2.0
    # the same tag from two sources counts once (it is a trait, not a stack)
    assert s.with_grants(grants("clawed")).stat("unarmed_damage") == 2.0


def test_capability_magnitudes_combine_by_max():
    s = CapabilitySet(grants(("darkvision", 5), ("darkvision", 9)))
    assert s.magnitude("darkvision") == 9
    assert CapabilitySet(grants("darkvision")).magnitude("darkvision") == 12.0
    assert CapabilitySet().magnitude("darkvision") == 0.0


def test_restriction_can_be_cancelled():
    s = CapabilitySet(grants("liquid_averse"))
    assert s.has("liquid_averse")
    overcome = s.with_grants(grants("liquid_tolerant"))
    assert not overcome.has("liquid_averse") and overcome.has("liquid_tolerant")


def test_stat_is_clamped():
    s = CapabilitySet(grants(("increased_agility", 99.0)))
    assert s.stat("move_speed") == cap.STATS["move_speed"].high


def test_every_stat_effect_refers_to_a_real_stat_and_system():
    for tag in cap.TAGS.values():
        assert tag.systems
        for effect in tag.effects:
            assert effect.stat in cap.STATS
