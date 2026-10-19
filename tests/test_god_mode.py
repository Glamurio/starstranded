"""God Mode (debug runs only): safe, free exploration that leaves terrain generation alone."""
import numpy as np
import pytest

import actions
import debug
import events
import exceptions
import input_handlers as ih
import tile_types
from chunks import CHUNK_H, CHUNK_W, chunk_key
from test_turn_flow import handler_for, quiet_corridor


@pytest.fixture
def debug_run(monkeypatch):
    monkeypatch.setattr(debug, "_enabled", True)


def key(engine, sym, mod=0):
    handler = ih.MainGameEventHandler(engine)
    engine.session.reset(handler)
    return handler.handle_events(events.KeyDown(sym, mod))


def test_god_mode_is_unavailable_in_an_ordinary_run(new_engine, monkeypatch):
    monkeypatch.setattr(debug, "_enabled", False)
    with pytest.raises(exceptions.Impossible):
        debug.toggle_god(new_engine)
    key(new_engine, events.Key.F10)                  # the key does nothing in an ordinary run
    assert not new_engine.god_mode
    assert not debug.is_god(new_engine)


def test_f10_toggles_god_mode_in_a_debug_run(new_engine, debug_run):
    key(new_engine, events.Key.F10)
    assert new_engine.god_mode and debug.is_god(new_engine)
    key(new_engine, events.Key.F10)
    assert not new_engine.god_mode


def test_god_mode_takes_no_damage_and_has_no_needs(new_engine, debug_run):
    player = new_engine.player
    debug.toggle_god(new_engine)
    hp, hunger, thirst = player.hp, player.hunger, player.thirst
    player.handle_health(-5, None)
    player.poison = 10
    for _ in range(40):
        new_engine.game_world.pass_time(unit=player, time=1)
    assert (player.hp, player.hunger, player.thirst) == (hp, hunger, thirst)
    assert player.is_alive


def test_ordinary_mode_still_takes_damage(new_engine, debug_run):
    player = new_engine.player
    hp = player.hp
    player.handle_health(-5, None)
    assert player.hp == hp - 5


def test_god_mode_walks_through_walls_and_water(new_engine, debug_run):
    quiet_corridor(new_engine, 6)
    player, world = new_engine.player, new_engine.game_map
    x = player.x
    world.set_tile(x + 1, player.y, tile_types.wall.get_array())
    world.set_tile(x + 2, player.y, tile_types.water.get_array())
    handler = handler_for(new_engine)
    with pytest.raises(exceptions.Impossible):         # ordinary walking is stopped by the wall
        actions.BumpAction(player, x + 1, player.y).perform()
    debug.toggle_god(new_engine)
    actions.BumpAction(player, x + 1, player.y).perform()
    actions.BumpAction(player, x + 2, player.y).perform()
    assert player.x == x + 2


def test_god_mode_click_walk_goes_straight_through_everything(new_engine, debug_run):
    quiet_corridor(new_engine, 12)
    player, world = new_engine.player, new_engine.game_map
    x = player.x
    world.set_tile(x + 3, player.y, tile_types.wall.get_array())
    debug.toggle_god(new_engine)
    handler = handler_for(new_engine)
    assert handler.handle_action(actions.BumpAction(player, x + 9, player.y))
    assert player.x == x + 9


def test_chunk_jumps_cross_borders_and_load_the_neighbours(new_engine, debug_run):
    debug.toggle_god(new_engine)
    player, world = new_engine.player, new_engine.game_map
    start = chunk_key(player.x, player.y)
    key(new_engine, events.Key.RIGHT, events.Mod.LALT)
    assert chunk_key(player.x, player.y) == (start[0] + 1, start[1])
    key(new_engine, events.Key.DOWN, events.Mod.LALT)
    assert chunk_key(player.x, player.y) == (start[0] + 1, start[1] + 1)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            assert (start[0] + 1 + dx, start[1] + 1 + dy) in world.chunks
    key(new_engine, events.Key.LEFT, events.Mod.LCTRL)
    assert player.is_alive


def test_god_mode_does_not_change_the_terrain_that_gets_generated(debug_run):
    """The same seed gives the same chunks whether they were reached by God Mode jumps or simply loaded."""
    from test_review_fixes import new_game
    jumped, plain = new_game(seed=77), new_game(seed=77)
    debug.toggle_god(jumped)
    for _ in range(3):
        key(jumped, events.Key.RIGHT, events.Mod.LALT)
    for k, chunk in jumped.game_map.chunks.items():
        other = plain.game_map.load_chunk(k)
        assert np.array_equal(chunk.tiles, other.tiles), k
        assert sorted(e.kind.key for e in chunk.entities if e is not jumped.player) == \
            sorted(e.kind.key for e in other.entities if e is not plain.player), k
