"""Animals: landmark variants are generated from the baselines, most creatures are passive, the hostile ones are dangerous."""
import dataclasses

import pytest

import landmarks
import species as defs
from components.unit import Unit
from planet import CAVE_FAUNA, FAUNA_TEMPLATES, LANDMARK_FAUNA, generate_planet, landmark_variants
from species import AIKind


def _by_key(planet):
    return {k.key.split(":")[-1]: k for k in planet.fauna}


def test_no_hand_written_landmark_species_remain():
    keys = {t.key for t in FAUNA_TEMPLATES}
    assert not keys & {"meadow_grazer", "ember_beetle", "sporehopper", "shardback", "carrion_hound", "dune_burrower",
                       "shore_crab", "sea_flitter", "bloom_flitter"}
    assert all("." not in key for key in keys)


def test_every_landmark_has_variants_of_baselines_living_only_there():
    variants = landmark_variants()
    baselines = {t.key: t for t in FAUNA_TEMPLATES}
    assert set(LANDMARK_FAUNA) == set(landmarks.LANDMARKS)
    for template in variants:
        base = baselines[template.base]
        assert template.key.startswith(base.key + ".")
        assert template.habitat.landmarks and template.habitat.landmarks[0] in landmarks.LANDMARKS
        assert template.ai is base.ai and template.sprite == base.sprite and template.diet is base.diet
        assert template.tint is not None and template.rarity > base.rarity
    assert {t.habitat.landmarks[0] for t in variants} == set(landmarks.LANDMARKS)


@pytest.mark.parametrize("culture", ["human", "selenite", "mau"])
def test_variants_are_generated_species_with_their_own_names(culture):
    planet = generate_planet(5, culture)
    by = _by_key(planet)
    assert len(planet.fauna) == len(FAUNA_TEMPLATES) + len(landmark_variants()) + len(CAVE_FAUNA)
    grazer, meadow = by["grazer"], by["grazer.flowering_meadow"]
    assert meadow.habitat.landmarks == ("flowering_meadow",) and not grazer.habitat.landmarks
    assert meadow.ai is grazer.ai and meadow.name and meadow.name != grazer.name
    assert len({k.name for k in planet.fauna}) == len(planet.fauna)


def test_baseline_animals_do_not_change_with_the_variants():
    planet = generate_planet(5, "human")
    assert [k.key for k in planet.fauna[:len(FAUNA_TEMPLATES)]] == ["planet:fauna:" + t.key for t in FAUNA_TEMPLATES]


def test_landmark_traits_apply():
    by = _by_key(generate_planet(5, "human"))
    assert by["scuttler.crystal_badlands"].defense == by["scuttler"].defense + 2
    assert by["hunter.volcanic_mountains"].power == by["hunter"].power + 1
    assert by["grazer.flowering_meadow"].power == by["grazer"].power     # peaceful animals get no sharper
    assert by["strider.cactus_desert"].covering == "scale" and by["strider"].covering == "fur"
    assert by["scuttler.beach"].covering == "chitin"                      # chitin stays chitin


def test_most_species_are_passive_and_hostile_ones_are_rare():
    planet = generate_planet(5, "human")
    hostile = [k for k in planet.fauna if k.ai is AIKind.HOSTILE]
    assert len(hostile) * 3 <= len(planet.fauna)
    weight = lambda ks: sum(k.rarity for k in ks)
    assert weight(hostile) * 4 < weight(planet.fauna)


def test_hostile_animals_hurt():
    from damage import resolve
    player = defs.HUMAN
    for k in generate_planet(5, "human").fauna:
        if k.ai is AIKind.HOSTILE:
            hit = resolve(k.power, player.defense, k.damage_type)
            assert hit >= 4, k.key                    # a handful of hits kills a fresh player
            assert k.max_hp >= 10, k.key


def test_selenites_are_humanoids_and_robot_is_a_machine():
    for species in (defs.HUMAN, defs.SELENITE_PEOPLE, defs.MAU, defs.SELENITE):
        assert "humanoid" in Unit(species).capabilities.tags
    robot = Unit(defs.ROBOT)
    assert "robot" in robot.capabilities.tags and "humanoid" not in robot.capabilities.tags
    assert defs.ROBOT.ai is AIKind.HOSTILE


def test_combat_skill_adds_power_and_is_practised(small_world):
    import actions
    from animals import Animal
    from skills import Skill, SkillSet
    import characters
    assert Skill.COMBAT in dict(characters.BACKGROUNDS["bounty_hunter"].skills)

    def hit_with(level):
        e = small_world()
        e.player.skills = SkillSet({Skill.COMBAT: level})
        target = Animal()
        target.ai = type("Idle", (), {"is_hostile": False, "perform": lambda self: None})()
        target.base_defense = 0
        target.max_hp = target.hp = 100
        target.place(2, 1, e.game_map)
        actions.MeleeAction(e.player, 2, 1).perform()
        return e, 100 - target.hp

    _, plain = hit_with(0)
    e, trained = hit_with(3)
    assert trained == plain + 3
    assert e.player.skill_practice.get(Skill.COMBAT, 0) >= 1
