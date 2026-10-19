"""Plant and fruit names: built from shape and colour, no catalogue numerals, fruit named after the plant that bears it."""
import re

import pytest

import lore
import planet as pl
from components.consumable import Fruit
from knowledge import Know

SEEDS = range(1, 25)
NUMERAL = re.compile(r"\b[IVX]+$")


def planets():
    return [pl.generate_planet(seed, "human") for seed in SEEDS]


def test_no_name_carries_a_numeral_or_repeats_a_word():
    for planet in planets():
        names = [s.name for s in planet.flora] + [s.fruit.species for s in planet.flora if s.fruit] + [m.name for _, m in planet.materials]
        for name in names:
            assert not NUMERAL.search(name), name
            words = name.split()
            assert len(set(words)) == len(words), name
        assert len({s.name for s in planet.flora}) == len(planet.flora)


def test_a_plant_is_named_by_a_word_and_the_form_its_sprite_shows():
    for planet in planets()[:6]:
        for species in planet.flora:
            template = species.key.split(":")[2]
            forms = pl.FORMS.get(template, ("bush", "tree"))
            assert any(species.name.endswith(form) for form in forms), (species.name, forms)


def test_fruit_is_named_after_its_parent_and_points_back_to_it():
    for planet in planets():
        by_key = {s.key: s for s in planet.flora}
        for species in planet.flora:
            if species.fruit is None:
                continue
            fruit = species.fruit
            assert fruit.parent_key == species.key and by_key[fruit.parent_key] is species
            modifier = species.name.split(" ")[0]
            assert fruit.species.startswith(modifier) or fruit.species == species.name, (species.name, fruit.species)


def test_an_oak_bears_acorns_and_palms_bear_dates_not_bananas():
    for planet in planets():
        for species in planet.flora:
            template = species.key.split(":")[2]
            if species.fruit is None or template not in ("conifer", "palm", "cactus", "fungal_tree"):
                continue
            allowed = {noun for _, nouns in pl.FRUITS[template] for noun in nouns}
            assert any(species.fruit.species.endswith(noun) for noun in allowed), (species.name, species.fruit.species)


def test_the_unidentified_names_describe_shape_and_colour(new_engine):
    engine = new_engine
    run = engine.game_world.run
    planet = engine.game_world.planet
    tree = next(s for s in planet.flora if s.key.split(":")[2] == "conifer")
    shown = lore.species_name(run, tree)
    assert shown.endswith("needle tree") and shown != tree.name


def test_a_fruit_can_be_scanned_on_its_own(new_engine):
    engine = new_engine
    planet = engine.game_world.planet
    species = next(s for s in planet.flora if s.fruit is not None)
    fruit = Fruit(engine.player.inventory, species.fruit)
    engine.player.inventory.add(fruit)
    run = engine.game_world.run
    assert lore.fruit_name(run, species.fruit) in (f"{__import__('naming').hue_name(species.fruit.color)} fruit",
                                                   f"{__import__('naming').hue_name(species.fruit.color)} bloom")
    assert lore.scan_state(engine, fruit) == "unscanned"
    title, learned = lore.scan(engine, 0, 0, entity=fruit)
    assert any(f.key == "name" for f, _ in learned)
    assert fruit.get_title().endswith(species.fruit.species)
    assert lore.scan_state(engine, fruit) in ("scanned", "partly scanned")
    assert run.knowledge.level(lore.fruit_subject(species.fruit), "name") is Know.FULL
