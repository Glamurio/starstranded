"""Ore that does not fit in a full pack lands where the message says."""
import tile_types
from test_turn_flow import quiet_corridor


def test_ore_that_does_not_fit_lands_under_the_player(new_engine, monkeypatch):
    import actions
    from components.consumable import Ration
    quiet_corridor(new_engine)
    player, world = new_engine.player, new_engine.game_map
    while not player.inventory.is_full():
        player.inventory.add(Ration(player.inventory))
    target = (player.x + 1, player.y)
    world.set_tile(*target, tile_types.wall.get_array())
    before = set(world.get_entities_at_location(player.x, player.y))
    monkeypatch.setattr(actions, "mining_tool", lambda unit: object())   # the mining rules are tested elsewhere
    monkeypatch.setattr(actions, "tool_head", lambda tool: type("Head", (), {"hardness": 99.0})())
    actions.MineAction(player, *target).perform()
    after = set(world.get_entities_at_location(player.x, player.y))
    assert len(after - before) == 1                       # the piece lies on the player's own tile
    assert not [e for e in world.get_entities_at_location(*target) if e is not player]
