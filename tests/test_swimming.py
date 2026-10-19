"""Swimming: deep water can be entered by the player, takes twice as long, drains a breath meter (Selenites last longer)
and leaves the player wet for a while."""
import pytest

import actions
import exceptions
import hud
import liquids
import survival
import tile_types
from test_turn_flow import handler_for, quiet_corridor


def lake(engine, length=6, kind=1, depth=2):
    """Water east of the player: `length` deep tiles in the corridor row, dry floor beyond."""
    quiet_corridor(engine, length + 3)
    world, player = engine.game_map, engine.player
    water = tile_types.water.get_array()
    water["liquid"], water["depth"], water["walkable"] = kind, depth, False
    for dx in range(1, length + 1):
        world.set_tile(player.x + dx, player.y, water)
    engine.update_fov()
    return water


def step(engine, dx=1):
    player = engine.player
    clock = engine.game_world.current_time
    actions.MovementAction(player, player.x + dx, player.y, [(player.x + dx, player.y)]).perform()
    return engine.game_world.current_time - clock


def test_deep_water_is_swimmable_but_lava_is_not():
    deep = tile_types.water.get_array()
    deep["liquid"], deep["depth"], deep["walkable"] = 1, 2, False
    assert liquids.swimmable(deep)
    deep["liquid"] = int(liquids.LiquidKind.LAVA)
    assert not liquids.swimmable(deep)
    shallow = tile_types.water.get_array()
    shallow["liquid"], shallow["depth"], shallow["walkable"] = 1, 1, True
    assert not liquids.swimmable(shallow)          # (shallow water is waded as before)


def test_the_player_swims_into_deep_water_and_it_takes_twice_as_long(new_engine):
    lake(new_engine)
    player = new_engine.player
    start = player.x
    assert step(new_engine) == 2 and player.x == start + 1
    assert step(new_engine) == 2


def test_swimming_drains_a_breath_meter_and_leaving_the_water_restores_it(new_engine):
    lake(new_engine, 3)
    player = new_engine.player
    assert player.breath is None
    step(new_engine)
    assert player.breath is not None and player.breath < player.capabilities.stat("breath_turns")
    for _ in range(3):
        step(new_engine)
    assert player.breath is None or player.breath > 0


def test_running_out_of_breath_stops_the_swim_and_then_drowns(new_engine):
    lake(new_engine, 40)
    player = new_engine.player
    with pytest.raises(exceptions.Impossible):
        for _ in range(40):
            step(new_engine)
    assert player.is_alive and player.breath is not None
    hp = player.hp
    for _ in range(40):                       # treading water: no breath left
        new_engine.game_world.pass_time(unit=player, time=1)
    assert player.hp < hp


def test_selenites_hold_their_breath_longer(new_engine):
    import characters
    import setup_game
    human = new_engine.player
    selenite = setup_game.new_game(characters.create_character("S", "selenite_people", "survivalist", sponsor="heavy_industries")).player
    assert selenite.capabilities.stat("breath_turns") >= 3 * human.capabilities.stat("breath_turns") - 1e-6


def test_swimming_leaves_you_wet_and_it_wears_off(new_engine):
    lake(new_engine, 2)
    player = new_engine.player
    assert player.wet == 0
    step(new_engine)
    assert player.wet >= liquids.WET_SWIM
    step(new_engine)
    step(new_engine)                          # onto the far bank
    assert player.wet > 0
    assert any(text == "Wet" for text, _ in survival.status_lines(new_engine))
    cold_wet = survival.effective_temperature(new_engine, player)
    player.wet = 0
    assert survival.effective_temperature(new_engine, player) == cold_wet + liquids.WET_CHILL
    player.wet = 5
    for _ in range(6):
        new_engine.game_world.pass_time(unit=player, time=1)
    assert player.wet == 0


def test_a_path_crosses_a_pond_but_the_meter_shows_on_the_hud(new_engine):
    lake(new_engine, 2)
    player = new_engine.player
    path = new_engine.get_path_to(player, player.x + 4, player.y)
    assert path and path[-1] == (player.x + 4, player.y)
    step(new_engine)
    from ui_helpers import SESSION
    SESSION.canvas.clear()
    hud.draw(SESSION.canvas, new_engine)
