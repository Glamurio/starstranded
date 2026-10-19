"""Animals have the covering their kind has, and what it leaves behind is a matching, useful piece."""
import pytest

import acquisition
import lore
import species as defs
from planet import generate_planet

EXPECTED = {"hopper": "fur", "grazer": "fur", "strider": "fur", "hunter": "fur", "stalker": "fur",
            "flitter": "feather", "webspinner": "chitin", "scuttler": "chitin", "serpent": "scale", "rooter": "skin",
            # landmark animals
            "sporehopper": "skin", "dune_burrower": "chitin", "shardback": "chitin", "ember_beetle": "chitin",
            "carrion_hound": "fur", "meadow_grazer": "fur", "bloom_flitter": "feather"}


@pytest.mark.parametrize("culture", ["human", "selenite", "mau"])
def test_each_animal_has_its_covering_and_material_noun(culture):
    planet = generate_planet(9, culture)
    seen = {}
    for kind in planet.fauna:
        key = kind.key.split(":")[-1]
        seen[key] = kind.covering
        noun = defs.COVERINGS[kind.covering][1]
        assert kind.hide.name.endswith(" " + noun), (key, kind.hide.name)
    assert seen == EXPECTED


def test_chitin_is_hard_and_fur_is_not_remarkable_for_hardness():
    planet = generate_planet(9, "human")
    by = {k.key.split(":")[-1]: k for k in planet.fauna}
    assert by["webspinner"].hide.hardness >= 6 and by["hopper"].hide.hardness <= 1.5
    assert by["flitter"].hide.insulation >= 6.5


def test_pieces_are_separate_forms_and_all_reachable():
    planet = generate_planet(9, "human")
    pieces = acquisition.natural_pieces(planet)
    for form in ("Hide", "Feather", "Chitin", "Scale"):
        assert pieces[form], form
    assert {m.name.rsplit(" ", 1)[-1] for m in pieces["Hide"]} <= {"fur", "skin"}


def test_death_drops_the_covering_piece(small_world):
    from animals import Animal
    import dataclasses
    e = small_world()
    planet = generate_planet(9, "human")
    for kind in planet.fauna:
        animal = Animal()
        animal.kind = dataclasses.replace(animal.kind, hide=kind.hide, covering=kind.covering)
        animal.place(3, 3, e.game_map)
        animal.hp = 0
        animal.die(None)
        forms = {i.object_type for i in animal.inventory.items}
        assert defs.COVERINGS[kind.covering][0].object_type in forms, kind.key


def test_no_hardness_gloss_just_because_a_chitin_animal_is_hard():
    import naming
    traits = naming.salient_traits({"hardness": 7, "toughness": 4, "tenacity": 1.5, "density": 3}, family="crawler")
    assert not any(t[0] == "hardness" for t in traits)
