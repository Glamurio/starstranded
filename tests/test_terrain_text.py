"""Hover names for the terrain layer."""
import tile_types
import terrain_text
from render_functions import get_names_at_location


def put(world, x, y, tile):
    world.tiles[x, y] = tile.get_array()


def test_made_terrain_is_named_and_plain_ground_is_not(small_world):
    engine = small_world()
    world = engine.game_map
    put(world, 3, 3, tile_types.path)
    put(world, 4, 3, tile_types.built_floor)
    put(world, 5, 3, tile_types.bridge)
    put(world, 6, 3, tile_types.open_air)
    assert terrain_text.describe(world, 3, 3) == "Trodden path"
    assert terrain_text.describe(world, 4, 3) == "Wooden flooring"
    assert terrain_text.describe(world, 5, 3) == "Bridge"
    assert terrain_text.describe(world, 7, 3) is None
    assert terrain_text.describe(world, 6, 3).startswith("Opening to the level below")


def test_hover_line_includes_the_terrain(small_world):
    engine = small_world()
    world = engine.game_map
    put(world, 3, 3, tile_types.path)
    world.visible[3, 3] = True
    assert "Trodden path" in get_names_at_location(3, 3, world)
