"""Scanning, provisional names and the codex."""
import random

import pytest

import actions
import characters
import exceptions
import lore
import setup_game
from components.unit import Animal
from knowledge import Know


def new_game(background="survivalist", seed=31):
    random.seed(seed)
    return setup_game.new_game(characters.create_character("T", "human", background, sponsor="heavy_industries"))


def make_visible(engine):
    engine.update_fov()


def place_creature(engine, dx=2):
    planet = engine.game_world.planet
    kind = planet.fauna[0]
    from components.unit import Animal
    animal = Animal(kind) if kind else Animal()
    animal.place(engine.player.x + dx, engine.player.y, engine.game_map)
    return animal, kind


def test_scan_out_of_range_is_impossible():
    engine = new_game()
    with pytest.raises(exceptions.Impossible):
        actions.ScanAction(engine.player, engine.player.x + 20, engine.player.y).perform()


def test_scan_wall_teaches_something_and_a_second_scan_nothing_new():
    engine = new_game()
    make_visible(engine)
    p = engine.player
    spot = None
    for dx in range(-6, 7):
        for dy in range(-6, 7):
            x, y = p.x + dx, p.y + dy
            if engine.game_map.is_visible(x, y) and lore.subject_at(engine, x, y) is not None \
                    and not engine.game_map.tile_at(x, y)["walkable"]:
                spot = (x, y)
                break
        if spot:
            break
    assert spot is not None
    first = lore.scan(engine, *spot)
    assert first is not None and first[1]
    again = lore.scan(engine, *spot)
    assert again[1] == []


def test_provisional_name_until_name_learned():
    engine = new_game()
    run = engine.game_world.run
    planet = engine.game_world.planet
    material = planet.materials[0][1]
    subject = lore.material_name(run, material)
    assert subject != material.name
    run.knowledge.learn(lore.material_subject(material), "name", Know.FULL)
    assert lore.material_name(run, material) == material.name


def test_learn_names_by_crafting_helper():
    engine = new_game()
    run = engine.game_world.run
    material = engine.game_world.planet.materials[0][1]
    lore.learn_names(run, [material])
    assert lore.name_known(run, lore.material_subject(material))


def test_scan_depth_depends_on_skill():
    low = new_game("translator")
    high = new_game("chemist")
    material = high.game_world.planet.materials[0][1]
    facts = lore.facts_for_material(material, high.game_world.planet)
    def learned(engine):
        return len(engine.game_world.run.knowledge.scan(
            lore.material_subject(material), facts, engine.player.skills, engine.player.capabilities))
    assert learned(high) >= learned(low)


def test_codex_lists_scanned_subjects_only():
    engine = new_game()
    run = engine.game_world.run
    assert all(not items for items in lore.codex_entries(engine).values())
    material = engine.game_world.planet.materials[0][1]
    run.knowledge.learn(lore.material_subject(material), "name", Know.FULL)
    entries = lore.codex_entries(engine)
    assert len(entries["Materials"]) == 1


def test_codex_handler_renders_and_pages():
    import input_handlers
    engine = new_game()
    handler = input_handlers.CodexHandler(engine)
    pages = handler.pages()
    assert [c for c, _ in pages][:2] == ["Materials", "Creatures"]


def test_navigation_lists_ship_and_pod_with_bearings():
    import screens
    engine = new_game()
    lines = screens.navigation_lines(engine)
    assert any(l.startswith("Your ship:") for l in lines)
    assert any(l.startswith("Sponsor cargo pod:") for l in lines)
    assert screens.bearing(3, -2) == "3 east, 2 north"
    assert screens.bearing(0, 0) == "here"
    from ui_helpers import SESSION
    import input_handlers
    SESSION.draw(input_handlers.NavigationHandler(engine))


def test_help_screen_renders_and_lists_new_keys():
    import input_handlers
    import screens
    from ui_helpers import SESSION
    engine = new_game()
    SESSION.draw(input_handlers.HelpHandler(engine))
    text = " ".join(k + w for k, w in screens.CONTROLS)
    for word in ("scan", "sleep", "pistol", "navigation"):
        assert word in text
