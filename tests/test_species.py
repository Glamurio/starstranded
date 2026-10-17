"""Immutable shared definitions and their pickling identity."""
import dataclasses
import pickle
import random

import pytest

import species
from species import ITEM_KINDS, UNIT_SPECIES, PlantCategory, make_plant_species


def test_definitions_are_frozen_and_hashable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        species.RABBIT.max_hp = 99
    assert hash(species.RABBIT) == hash(species.RABBIT)
    assert {species.MEAT, species.DAGGER}


def test_registries_contain_the_static_content():
    assert {"human", "selenite", "rabbit"} <= set(UNIT_SPECIES)
    assert {"health_potion", "meat", "branch", "dagger", "leather_armor", "wooden_spear", "campfire"} <= set(ITEM_KINDS)
    for key, kind in ITEM_KINDS.items():
        assert kind.key == key and (kind.sprite or kind.glyph)


def test_static_definitions_unpickle_to_the_registered_object():
    for definition in list(UNIT_SPECIES.values()) + list(ITEM_KINDS.values()):
        assert pickle.loads(pickle.dumps(definition)) is definition


def test_procedural_definitions_pickle_by_value_and_stay_shared_within_one_pickle():
    random.seed(3)
    tree = make_plant_species(PlantCategory.TREE)
    copy_a, copy_b = pickle.loads(pickle.dumps([tree, tree]))
    assert copy_a == tree and copy_a is copy_b


@pytest.mark.parametrize("category", list(PlantCategory))
def test_plant_species_generation_matches_old_rules(category):
    rng = random.Random(5)
    rolled = [make_plant_species(category, rng) for _ in range(300)]
    with_fruit = sum(1 for s in rolled if s.fruit) / len(rolled)
    assert 0.7 < with_fruit < 0.9  # old rule: fruit if random() > 0.2
    for s in rolled:
        if s.fruit:
            assert s.name.startswith(s.fruit.species + " ")
            assert s.fruit.hunger_amount == s.fruit.thirst_amount == 10
    if category is PlantCategory.TREE:
        assert all(s.blocks_movement and s.blocks_sight and s.growth_cycle == 10 and s.max_hp == 10 for s in rolled)
    else:
        assert all(not s.blocks_movement and not s.blocks_sight and s.growth_cycle == 5 and s.max_hp == 5 for s in rolled)


def test_plant_species_generation_is_reproducible_from_an_rng():
    a = make_plant_species(PlantCategory.TREE, random.Random(11))
    b = make_plant_species(PlantCategory.TREE, random.Random(11))
    assert a == b


def test_glyphs_are_codepoints_or_text():
    g = species.glyphs(species.RABBIT)
    assert all(isinstance(c, int) and c >= 0xE000 for c in g)
    assert g.sprite != g.mirror != g.corpse
    assert species.glyphs(species.HEALTH_POTION) == ("!", "!", "!")
