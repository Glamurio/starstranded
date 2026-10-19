"""A creature without a name entering acid is burned, not crashed."""
from test_turn_flow import quiet_corridor


def test_a_nameless_creature_entering_acid_is_burned_without_crashing(new_engine):
    from components.unit import Unit
    quiet_corridor(new_engine)
    engine, player, world = new_engine, new_engine.player, new_engine.game_map
    x, y = player.x + 1, player.y
    unit = Unit(engine.game_world.planet.fauna[0])
    assert unit.name is None
    world.add_entity(unit, x + 1, y)
    world.modify_tile(x, y, walkable=True, liquid=3, depth=1)
    engine.update_fov()
    hp = unit.hp
    unit.move(x, y)
    assert unit.hp < hp or not unit.is_alive
