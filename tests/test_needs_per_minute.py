"""Hunger, thirst and poison are paid per elapsed minute, whatever the size of the step."""
import pytest


def drained(engine, step, total=1020):
    player, world = engine.player, engine.game_world
    world.current_time = 0
    player.hunger, player.thirst = player.max_hunger, player.max_thirst
    player.max_hp = player.hp = 10 ** 6            # (the weather of a long wait is not what is measured here)
    done = 0
    while done < total:
        world.pass_time(unit=player, time=step)
        done += step
    return player.max_hunger - player.hunger, player.max_thirst - player.thirst


@pytest.mark.parametrize("step", [1, 2, 3, 5, 6])
def test_long_actions_cost_as_much_hunger_and_thirst_as_single_minutes(small_world, step):
    engine = small_world()
    import simulation
    assert drained(engine, step) == (1020 // simulation.HUNGER_PERIOD, 1020 // simulation.THIRST_PERIOD) == (30, 68)


def test_poison_burns_once_per_minute(small_world):
    engine = small_world()
    player = engine.player
    player.hp, player.poison = 20, 10
    engine.game_world.pass_time(unit=player, time=5)
    assert player.poison == 5 and player.hp == 15


def test_a_death_in_the_middle_of_a_long_action_stops_the_clock(small_world):
    engine = small_world()
    player = engine.player
    player.hp, player.poison = 1, 10
    t0 = engine.game_world.current_time
    engine.game_world.pass_time(unit=player, time=6)
    assert not player.is_alive and engine.game_world.current_time == t0 + 1
