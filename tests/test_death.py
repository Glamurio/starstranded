"""A death with a full pack still ends the run properly."""
import events
import input_handlers as ih
from components.consumable import Ration
from test_turn_flow import handler_for, quiet_corridor, texts


def test_dying_with_a_full_pack_still_dies_properly(new_engine):
    quiet_corridor(new_engine)
    player = new_engine.player
    while not player.inventory.is_full():
        player.inventory.add(Ration(player.inventory))
    import simulation
    player.hp, player.hunger = 1, 1
    new_engine.game_world.current_time = simulation.HUNGER_PERIOD - 2        # (hunger is paid at the next period: the last point goes)
    handler = handler_for(new_engine)
    start = len(new_engine.message_log.messages)
    shown = handler.handle_events(events.KeyDown(events.Key.SPACE, 0))
    for _ in range(5):
        if not player.is_alive:
            break
        shown = shown.handle_events(events.KeyDown(events.Key.SPACE, 0))
    assert not player.is_alive
    assert any("You died" in line for line in texts(new_engine, start))
    assert "Your Inventory is full." not in texts(new_engine, start)
    assert isinstance(shown, ih.GameOverEventHandler)
