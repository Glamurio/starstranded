"""Day and night: the ambient radius follows the sun, light sources show lit ground from far away."""
import dataclasses

import lighting
import tile_types
from config import DEFAULT_CONFIG
from crafting import Campfire

NOON = 72      # with the default start_phase of 0.35 and a 480 turn day
MIDNIGHT = 312


def test_daylight_curve_is_bright_at_noon_and_dark_at_midnight():
    cfg = DEFAULT_CONFIG
    assert lighting.daylight(NOON, cfg) == 1.0
    assert lighting.daylight(MIDNIGHT, cfg) == 0.0
    assert lighting.daylight(NOON + cfg.day_length, cfg) == 1.0  # periodic


def test_clock_text_counts_days_from_one():
    assert lighting.clock_text(0, DEFAULT_CONFIG).startswith("Day 1")
    assert lighting.clock_text(480, DEFAULT_CONFIG).startswith("Day 2")


def _count(e):
    return int(e.game_map.visible.sum())


def test_night_sees_less_than_day(small_world):
    e = small_world(width=70, height=40)
    e.player.place(35, 20)
    e.game_world.current_time = NOON
    e.update_fov()
    day = _count(e)
    e.game_world.current_time = MIDNIGHT
    e.update_fov()
    night = _count(e)
    assert night < day / 10
    assert e.game_map.visible[35, 20] and e.game_map.visible[37, 20] and not e.game_map.visible[45, 20]


def test_a_lit_campfire_is_seen_from_afar_at_night(small_world):
    e = small_world(width=70, height=40)
    e.game_world.current_time = MIDNIGHT
    e.player.place(10, 20)
    fire = Campfire()
    e.game_map.add_entity(fire, 30, 20)
    fire.is_placed = True
    e.update_fov()
    assert not e.game_map.visible[30, 20]  # unlit: dark
    fire.toggle()
    e.update_fov()
    assert e.game_map.visible[30, 20] and e.game_map.visible[33, 20]
    assert not e.game_map.visible[20, 20]  # the dark between is still dark
    assert e.game_map.window.lit_region((30, 20, 1, 1))[0, 0]


def test_a_wall_stops_firelight(small_world):
    e = small_world(width=70, height=40)
    e.game_world.current_time = MIDNIGHT
    e.player.place(10, 20)
    for y in range(40):
        e.game_map.tiles[25, y] = tile_types.wall.get_array()
    fire = Campfire()
    e.game_map.add_entity(fire, 30, 20)
    fire.is_placed = True
    fire.toggle()
    e.update_fov()
    assert not e.game_map.visible[30, 20]


def test_underground_has_no_sky(small_world):
    e = small_world(width=70, height=40)
    e.game_world.current_time = NOON
    e.game_map.has_sky = False
    assert lighting.ambient_radius(e.game_map, NOON, e.config) == DEFAULT_CONFIG.night_view_radius
