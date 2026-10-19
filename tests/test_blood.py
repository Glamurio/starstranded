"""Deaths leave a puddle of the species' blood under the corpse: scenery, not an item."""
import atlas
import decals
import render_functions
from animals import Animal
from render_helpers import cell, draw_map
from ui_helpers import SESSION


def kill(e, x, y, **kw):
    animal = Animal()
    animal.place(x, y, e.game_map)
    animal.hp = 0
    animal.die(None)
    return animal


def test_death_leaves_one_red_puddle_under_the_corpse(small_world):
    e = small_world()
    x, y = e.player.x + 2, e.player.y
    kill(e, x, y)
    puddles = [t for t in e.game_map.stack_at(x, y) if decals.is_decal(t)]
    assert len(puddles) == 1 and puddles[0].color == (150, 18, 24)
    assert puddles[0].get_title() == "puddle of blood"
    kill(e, x, y)                                   # a second death on the same tile adds no second stain
    assert len([t for t in e.game_map.stack_at(x, y) if decals.is_decal(t)]) == 1


def test_blood_colour_comes_from_the_species(small_world):
    import dataclasses
    e = small_world()
    x, y = e.player.x + 3, e.player.y
    robot = Animal()
    robot.kind = dataclasses.replace(robot.kind, blood_color=(20, 20, 24), blood_name="oil")
    robot.place(x, y, e.game_map)
    robot.hp = 0
    robot.die(None)
    puddle = next(t for t in e.game_map.stack_at(x, y) if decals.is_decal(t))
    assert puddle.color == (20, 20, 24) and puddle.get_title() == "puddle of oil"


def test_puddle_is_scenery_not_loot_and_not_a_tooltip(small_world):
    e = small_world()
    x, y = e.player.x + 2, e.player.y + 1
    decals.spill(e.game_map, x, y, (150, 18, 24))
    assert not e.game_map.stack_at(x, y)[0].has_inventory
    e.mouse_location = (x, y)
    e.update_fov()
    assert render_functions.get_names_at_location(x, y, e.game_map) in ("puddle of blood", "")  # the HUD names it when visible


def test_puddle_is_drawn_tinted_and_under_the_corpse(small_world):
    e = small_world()
    x, y = e.player.x + 1, e.player.y
    decals.spill(e.game_map, x, y, (200, 0, 0))
    e.update_fov()
    surface = atlas.get_atlas().get_puddle(3, (200, 0, 0))
    reds = [surface.get_at((i, j)) for i in range(24) for j in range(24) if surface.get_at((i, j)).a > 0]
    assert reds and all(c.g == 0 and c.b == 0 and c.r > 100 for c in reds)
    from render_order import LAYERS, RenderOrder
    assert LAYERS[0] is RenderOrder.DECAL
