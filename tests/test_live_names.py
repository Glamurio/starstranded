"""Names are live references: what you see changes once you learn it, and crafted things inherit their material's name."""
import random

import characters
import crafting
import lore
import recipes
import setup_game
from components.unit import Unit
from knowledge import Know


def new_game(seed=41):
    random.seed(seed)
    return setup_game.new_game(characters.create_character("T", "human", "survivalist", sponsor="heavy_industries"))


def kill_planet_animal(engine):
    kind = next(k for k in engine.game_world.planet.fauna if k.hide is not None)
    animal = Unit(kind)
    animal.place(engine.player.x + 1, engine.player.y, engine.game_map)
    animal.die(quiet=True)
    return kind, animal


def test_a_planet_animal_drops_hide_and_meat_but_no_second_leather():
    engine = new_game()
    kind, animal = kill_planet_animal(engine)
    forms = sorted(item.get_title() for item in animal.inventory.items)
    assert len(forms) == 3 and not any("leather" in f.lower() for f in forms)
    assert sum("meat" in f for f in forms) == 2 and sum("hide" in f for f in forms) == 1


def test_names_update_retroactively_when_the_species_and_material_are_learned():
    engine = new_game()
    kind, animal = kill_planet_animal(engine)
    run = engine.game_world.run
    meat = next(i for i in animal.inventory.items if "meat" in i.get_title())
    hide = next(i for i in animal.inventory.items if "hide" in i.get_title())
    assert kind.name not in meat.get_title() and kind.hide.name not in hide.get_title()
    run.knowledge.learn(lore.species_subject(kind), "name", Know.FULL)
    run.knowledge.learn(lore.material_subject(kind.hide), "name", Know.FULL)
    assert kind.name in meat.get_title() and kind.hide.name in hide.get_title()


def test_a_flask_inherits_the_hide_it_is_made_of():
    engine = new_game()
    kind, animal = kill_planet_animal(engine)
    hide = next(i for i in animal.inventory.items if "hide" in i.get_title())
    recipe = recipes.BY_KEY["flask"]
    plan = crafting.Plan(recipe, parts={"hide": kind.hide}, quality=1.0)
    flask = crafting._build(recipe, plan, engine.player, {})[0]
    flask.parent = engine.player.inventory
    assert flask.color == kind.hide.color
    assert flask.get_title().endswith("leather flask (empty)")
    assert lore.material_name(engine.game_world.run, kind.hide).replace(" hide", "") in flask.get_title()
    engine.game_world.run.knowledge.learn(lore.material_subject(kind.hide), "name", Know.FULL)
    assert kind.hide.name.replace(" hide", "") in flask.get_title()


def test_everyday_names_are_lowercase_but_people_keep_their_capital():
    engine = new_game()
    assert crafting.Branch().get_title() == "wood branch" or crafting.Branch().get_title()[0].islower()
    assert engine.player.get_title()[0].isupper() or engine.player.species == "Human"


def test_using_a_survey_kit_opens_the_scanner_instead_of_an_error():
    import input_handlers as ih
    import species
    from items import Made
    engine = new_game()
    from items import DEFAULT_WOOD
    kit = Made(species.SURVEY_KIT, {"body": DEFAULT_WOOD}, 1.0, "survey_kit", parent=engine.player.inventory)
    assert isinstance(kit.activate(engine.player), ih.SingleRangedAttackHandler)
