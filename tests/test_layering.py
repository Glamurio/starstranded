"""Sprite layering: terrain < corpses < items < shrubs < units < trees, everything visible is drawn, and the clutter
safeguard caps piles of ground objects (one config flag)."""
import numpy as np
import pygame
import pytest

from ui_helpers import SESSION
import render_order
import render_functions
from components.consumable import Meat
from components.plant import Shrub, Tree
from animals import Animal
from config import GameConfig
from render_helpers import cell, draw_map, expected_tile
from render_order import RenderOrder


@pytest.fixture(autouse=True)
def no_blood(monkeypatch):
    """These tests count what lies on a tile; the blood a death leaves is covered in test_blood.py."""
    import decals
    monkeypatch.setattr(decals, "spill", lambda *a, **k: None)


def corpse_at(e, x, y):
    animal = Animal()
    animal.place(x, y, e.game_map)
    animal.hp = 0
    animal.die(None)
    return animal


def meat_at(e, x, y):
    meat = Meat("x")
    meat.place(x, y, e.game_map)
    return meat


def test_layer_order_is_terrain_corpse_item_shrub_unit_tree():
    assert list(render_order.LAYERS) == [RenderOrder.DECAL, RenderOrder.CORPSE, RenderOrder.ITEM, RenderOrder.SHRUB, RenderOrder.UNIT, RenderOrder.TREE]
    assert [layer.value for layer in render_order.LAYERS] == sorted(layer.value for layer in render_order.LAYERS)
    assert render_order.GROUND_LAYERS == (RenderOrder.CORPSE, RenderOrder.ITEM)


def test_every_entity_on_a_tile_is_drawn_in_layer_order(small_world):
    e = small_world()
    m = e.game_map
    unit = Animal(); unit.place(5, 5, m)
    tree = Tree(); tree.place(5, 5, m)  # added in a "wrong" order on purpose
    shrub = Shrub(); shrub.place(5, 5, m)
    meat = meat_at(e, 5, 5)
    corpse = corpse_at(e, 5, 5)
    e.update_fov()
    draw_map(e)
    layered = [corpse, meat, shrub, unit, tree]
    assert np.array_equal(cell(SESSION.canvas, 5, 5), expected_tile(layered))
    assert not np.array_equal(cell(SESSION.canvas, 5, 5), expected_tile(list(reversed(layered))))


def test_each_layer_keeps_its_own_tint_and_mirroring(small_world):
    e = small_world()
    m = e.game_map
    left = Animal(); left.place(6, 6, m); left.mirrored = False
    right = Animal(); right.place(7, 6, m); right.mirrored = True
    e.update_fov()
    draw_map(e)
    assert left.flipped is False and right.flipped is True
    assert np.array_equal(cell(SESSION.canvas, 6, 6), expected_tile([left]))
    assert np.array_equal(cell(SESSION.canvas, 7, 6), expected_tile([right]))


def test_corpse_uses_the_corpse_sprite_unmirrored(small_world):
    e = small_world()
    animal = Animal(); animal.place(4, 4, e.game_map); animal.mirrored = True
    live_sprite = animal.sprite_id
    animal.hp = 0; animal.die(None)
    assert animal.sprite_id == live_sprite       # the corpse is the creature itself, lying on its side with bones
    assert animal.flipped is False and animal.render_order is RenderOrder.CORPSE
    atlas = SESSION.canvas.sprites
    remains = atlas.get_remains(live_sprite, False, animal.shade)
    assert remains.get_size() == atlas.get(live_sprite).get_size() and remains is not atlas.get(live_sprite)


def test_entities_on_tiles_out_of_sight_are_not_drawn(small_world):
    e = small_world()
    meat = meat_at(e, 8, 8)
    e.update_fov()
    e.game_map.visible[8, 8] = False
    e.game_map.explored[8, 8] = False
    draw_map(e)
    assert not cell(SESSION.canvas, 8, 8).any()


# ── clutter safeguard ──────────────────────────────────────────────────────────────
def pile(e, x, y, items=4, corpses=1):
    made_corpses = [corpse_at(e, x, y) for _ in range(corpses)]
    made_items = [meat_at(e, x, y) for _ in range(items)]
    e.update_fov()
    return made_corpses, made_items


def test_safeguard_is_on_by_default():
    assert GameConfig().clutter_safeguard is True
    assert render_order.MAX_GROUND_OBJECTS_PER_TILE == 2


def test_safeguard_draws_only_the_top_two_ground_objects_and_a_marker(small_world):
    e = small_world()
    corpses, items = pile(e, 5, 5, items=4, corpses=1)
    assert e.game_map.hidden_ground_counts() == {(5, 5): 3}
    draw_map(e)
    drawn = cell(SESSION.canvas, 5, 5)
    expected = expected_tile(items[-2:]).copy()
    # the stack marker covers the top-right quarter of the cell
    assert np.array_equal(drawn[:12], expected[:12])  # left half: exactly the top two items
    assert not np.array_equal(drawn[12:, :12], expected[12:, :12])  # marker present
    assert not np.array_equal(drawn, expected_tile(corpses + items))


def test_marker_is_drawn_only_on_piled_tiles(small_world):
    e = small_world()
    pile(e, 5, 5, items=3, corpses=0)
    meat_at(e, 7, 5)
    meat_at(e, 7, 5)
    e.update_fov()
    draw_map(e)
    assert e.game_map.hidden_ground_counts() == {(5, 5): 1}
    two = cell(SESSION.canvas, 7, 5)
    assert np.array_equal(two, expected_tile(e.game_map.stack_at(7, 5)[::-1]))  # exactly two: nothing hidden, no marker


def test_flag_off_draws_the_whole_pile(small_world):
    e = small_world()
    e.config = GameConfig(clutter_safeguard=False)
    corpses, items = pile(e, 5, 5, items=4, corpses=1)
    assert e.game_map.hidden_ground_counts() == {}
    draw_map(e)
    assert np.array_equal(cell(SESSION.canvas, 5, 5), expected_tile(corpses + items))


def test_units_are_never_hidden_by_the_safeguard(small_world):
    e = small_world()
    corpses, items = pile(e, 5, 5, items=5, corpses=2)
    unit = Animal(); unit.place(5, 5, e.game_map)
    e.update_fov()
    draw_map(e)
    drawn = cell(SESSION.canvas, 5, 5)
    expected = expected_tile(items[-2:] + [unit])
    assert np.array_equal(drawn[:12], expected[:12])
    opaque = pygame.surfarray.array_alpha(SESSION.canvas.sprites.get(unit.sprite_id, unit.flipped, unit.shade)) > 0
    opaque[12:, :12] = False  # the stack marker covers the top-right quarter of the cell
    assert opaque.any()
    assert np.array_equal(drawn[opaque], expected_tile([unit])[opaque])  # the unit's own pixels win over the pile


def test_player_standing_on_a_corpse_and_item_shows_all_three(small_world):
    e = small_world()
    m = e.game_map
    p = e.player
    corpse = corpse_at(e, p.x, p.y)
    meat = meat_at(e, p.x, p.y)
    e.update_fov()
    draw_map(e)
    assert np.array_equal(cell(SESSION.canvas, p.x, p.y), expected_tile([corpse, meat, p]))


def test_animal_standing_on_a_corpse_and_item_shows_all_three(small_world):
    e = small_world()
    m = e.game_map
    corpse = corpse_at(e, 6, 6)
    meat = meat_at(e, 6, 6)
    animal = Animal(); animal.place(6, 6, m)
    e.update_fov()
    draw_map(e)
    assert np.array_equal(cell(SESSION.canvas, 6, 6), expected_tile([corpse, meat, animal]))


# ── names: the stack, topmost first ────────────────────────────────────────────────
def test_stack_at_lists_topmost_layer_first_newest_first(small_world):
    e = small_world()
    m = e.game_map
    corpse = corpse_at(e, 5, 5)
    first = meat_at(e, 5, 5)
    second = meat_at(e, 5, 5)
    unit = Animal(); unit.place(5, 5, m)
    tree = Tree(); tree.place(5, 5, m)
    assert m.stack_at(5, 5) == [tree, unit, second, first, corpse]
    assert m.stack_at(0, 0) == []


def test_names_at_location_are_topmost_first(small_world):
    e = small_world()
    corpse = corpse_at(e, 5, 5)
    meat = meat_at(e, 5, 5)
    unit = Animal(); unit.place(5, 5, e.game_map)
    e.update_fov()
    names = render_functions.get_names_at_location(5, 5, e.game_map)
    assert names == ", ".join([unit.get_title(), meat.get_title(), corpse.get_title()])
    assert render_functions.get_names_at_location(5, 5, e.game_map).index(unit.get_title()) == 0


def test_long_stack_names_are_cut_with_an_ellipsis(small_world):
    e = small_world()
    for _ in range(6):
        meat_at(e, 5, 5)
    e.update_fov()
    e.mouse_location = (5, 5)
    SESSION.canvas.clear()
    render_functions.render_names_at_mouse_location(SESSION.canvas, 21, 40, e, width=20)
    drawn_columns = [x for x in range(21, 60) if cell(SESSION.canvas, x, 40).any()]
    assert drawn_columns and max(drawn_columns) <= 21 + 19


def test_pickup_lists_the_stack_topmost_first(small_world):
    import input_handlers as ih
    from events import KeyDown, Key, Point
    e = small_world()
    corpse = corpse_at(e, 2, 1)
    meat = meat_at(e, 2, 1)
    e.mouse_location = Point(2, 1)
    handler = ih.PickupHandler(e)
    SESSION.handlers = [ih.MainGameEventHandler(e), handler]
    loot = handler.on_tile_selected(e.game_map.stack_at(2, 1))
    assert loot.entities == [meat, corpse]
