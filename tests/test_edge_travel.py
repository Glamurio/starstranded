"""Mouse-only play: a left click on the outer ring of the view walks into the next screen."""
import actions
import input_handlers as ih
import tile_types
import view
from chunks import chunk_key
from test_turn_flow import handler_for


def lay_row_to_right_edge(engine):
    """Clear the world around the player's row so a walk from the player past the right edge of the view is possible."""
    world, player = engine.game_map, engine.player
    for unit in list(world.units):
        if unit is not player:
            world.remove_entity(unit)
    cam = view.Camera.follow(world, player.x, player.y)
    edge_x = cam.x0 + cam.width - 1
    for x in range(player.x, edge_x + 6):
        for entity in list(world.get_entities_at_location(x, player.y)):
            if entity is not player:
                world.remove_entity(entity)
        world.set_tile(x, player.y, tile_types.floor.get_array())
    engine.update_fov()
    return edge_x


def test_edge_exit_directions():
    cam = view.Camera(10, 20, 58, 45)
    assert ih.edge_exit(cam, 10 + 57, 20 + 5) == (1, 0)
    assert ih.edge_exit(cam, 10, 20) == (-1, -1)
    assert ih.edge_exit(cam, 10 + 20, 20 + 44) == (0, 1)
    assert ih.edge_exit(cam, 10 + 20, 20 + 20) == (0, 0)


def test_clicking_the_edge_tile_aims_past_it(new_engine):
    edge_x = lay_row_to_right_edge(new_engine)
    y = new_engine.player.y
    assert ih.travel_target(new_engine, edge_x, y) == (edge_x + 1, y)
    assert ih.travel_target(new_engine, edge_x - 3, y) == (edge_x - 3, y)   # inside the view: unchanged


def test_mouse_only_walk_leaves_the_screen(new_engine):
    edge_x = lay_row_to_right_edge(new_engine)
    player = new_engine.player
    y = player.y
    new_engine.mouse_location = (edge_x, y)
    handler = handler_for(new_engine)
    action = handler.ev_mousebuttondown(type("E", (), {"button": ih.MouseButton.LEFT})())
    for _ in range(80):
        if not handler.handle_action(action):
            break
    assert player.x == edge_x + 1
    assert new_engine.camera.x0 > edge_x - 58          # the view has paged onward
