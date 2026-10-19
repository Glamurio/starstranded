"""A step ends cleanly, and death or an ending that happens during an action is noticed at once."""
import pytest

import actions
import events
import input_handlers as ih
import tile_types


def quiet_corridor(engine, length=30):
    """Remove every other unit and lay `length` floor tiles east of the player (nothing hostile in view)."""
    world, player = engine.game_map, engine.player
    for unit in list(world.units):
        if unit is not player:
            world.remove_entity(unit)
    for dx in range(length):
        x = player.x + dx
        for entity in list(world.get_entities_at_location(x, player.y)):
            if entity is not player:
                world.remove_entity(entity)
        world.set_tile(x, player.y, tile_types.floor.get_array())
    engine.update_fov()


def handler_for(engine):
    handler = ih.MainGameEventHandler(engine)
    engine.session.reset(handler)
    return handler


def texts(engine, start):
    return [m.plain_text for m in engine.message_log.messages[start:]]


def test_a_single_step_does_not_log_blocked(new_engine):
    quiet_corridor(new_engine)
    handler = handler_for(new_engine)
    start, x = len(new_engine.message_log.messages), new_engine.player.x
    handler.handle_events(events.KeyDown(events.Key.RIGHT, 0))
    assert new_engine.player.x == x + 1
    assert "That way is blocked." not in texts(new_engine, start)


def test_a_click_walk_arrives_without_a_blocked_message(new_engine):
    quiet_corridor(new_engine)
    handler = handler_for(new_engine)
    player = new_engine.player
    start, x = len(new_engine.message_log.messages), player.x
    assert handler.handle_action(actions.BumpAction(player, x + 12, player.y))
    assert player.x == x + 12
    assert "That way is blocked." not in texts(new_engine, start)


def test_dying_during_a_walk_stops_the_walk_and_shows_game_over(new_engine):
    quiet_corridor(new_engine)
    player = new_engine.player
    player.hp, player.poison = 3, 10
    handler = handler_for(new_engine)
    x = player.x
    action = actions.BumpAction(player, x + 25, player.y)
    handler.dispatch = lambda event: action
    shown = handler.handle_events(events.KeyDown(events.Key.SPACE, 0))
    assert not player.is_alive
    assert player.x - x < 25                    # the walk stopped when the player died
    assert isinstance(shown, ih.GameOverEventHandler)


def test_an_ending_reached_during_a_step_is_shown_at_once(new_engine):
    quiet_corridor(new_engine)
    run = new_engine.game_world.run
    run.flags["rescue_due"] = new_engine.game_world.current_time + 1
    run.sponsor = "heavy_industries"
    handler = handler_for(new_engine)
    shown = handler.handle_events(events.KeyDown(events.Key.RIGHT, 0))
    assert run.ending is not None
    import screens
    assert isinstance(shown, screens.EndingHandler)

