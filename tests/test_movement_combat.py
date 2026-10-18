"""Characterization: bump/movement/melee resolution and time passing."""
import pytest

import actions
import exceptions
from components.unit import Animal


class IdleAI:
    """Truthy no-op AI: keeps NPCs deterministic. (A unit whose `ai` is falsy can never die:
    Unit.handle_health only calls die() `if self.hp == 0 and self.ai`.)"""
    is_hostile = False

    def perform(self):
        pass


def spawn_animal(engine, x, y):
    a = Animal()
    a.ai = IdleAI()
    a.place(x, y, engine.game_map)
    return a


def test_bump_into_free_tile_moves_player_and_passes_time(small_world):
    e = small_world()
    t0 = e.game_world.current_time
    actions.BumpAction(e.player, 2, 1).perform()
    assert (e.player.x, e.player.y) == (2, 1)
    assert e.game_world.current_time == t0 + 1


def test_bump_into_wall_is_impossible_and_player_stays(small_world):
    import tile_types
    e = small_world()
    e.game_map.tiles[2, 1] = tile_types.wall.get_array()
    with pytest.raises(exceptions.Impossible):
        actions.BumpAction(e.player, 2, 1).perform()
    assert (e.player.x, e.player.y) == (1, 1)


def test_bump_out_of_bounds_is_impossible(small_world):
    e = small_world()
    e.player.place(0, 0)
    with pytest.raises(exceptions.Impossible):
        actions.BumpAction(e.player, -1, 0).perform()


def test_diagonal_bump_moves(small_world):
    e = small_world()
    actions.BumpAction(e.player, 2, 2).perform()
    assert (e.player.x, e.player.y) == (2, 2)


def test_bump_into_living_unit_resolves_as_melee(small_world):
    e = small_world()
    target = spawn_animal(e, 2, 1)
    target.max_hp = target.hp = 100
    damage = e.player.power - target.defense
    assert damage > 0
    actions.BumpAction(e.player, 2, 1).perform()
    assert (e.player.x, e.player.y) == (1, 1)  # did not move
    assert target.hp == 100 - damage


def test_melee_kill_makes_corpse_with_meat_and_awards_xp(small_world):
    from components.consumable import Meat
    e = small_world()
    target = spawn_animal(e, 2, 1)
    xp0 = e.player.level.current_xp
    actions.BumpAction(e.player, 2, 1).perform()  # rabbit has 1 hp
    assert target.hp == 0 and not target.is_alive
    assert not target.blocks_movement
    assert target.ai is None  # die() clears the AI
    assert sorted(type(i).__name__ for i in target.inventory.items) == ["Leather", "Meat", "Meat"]
    assert e.player.level.current_xp == xp0 + target.level.xp_given


def test_melee_with_zero_damage_does_nothing(small_world):
    e = small_world()
    target = spawn_animal(e, 2, 1)
    target.base_defense = 99
    target.max_hp = target.hp = 5
    actions.MeleeAction(e.player, 2, 1).perform()
    assert target.hp == 5


def test_melee_without_target_is_impossible(small_world):
    e = small_world()
    with pytest.raises(exceptions.Impossible):
        actions.MeleeAction(e.player, 2, 1).perform()


def test_blocking_entity_prevents_movement(small_world):
    e = small_world()
    from components.plant import Tree
    tree = Tree()
    e.game_map.add_entity(tree, 2, 1)
    e.game_map.tiles[2, 1]["walkable"] = True  # isolate: only the entity should block
    assert not e.can_move(2, 1)
    assert e.can_move(1, 2)


def test_wait_passes_one_minute(small_world):
    e = small_world()
    actions.WaitAction(e.player).perform()
    assert e.game_world.current_time == 1


def test_enemy_turns_run_after_player_action(small_world):
    e = small_world()
    calls = []

    class Probe:
        is_hostile = False
        def perform(self):
            calls.append(1)

    a = spawn_animal(e, 5, 5)
    a.ai = Probe()
    actions.WaitAction(e.player).perform()
    assert calls == [1]


def test_unit_without_ai_still_dies_at_zero_hp(small_world):
    """Fixed: dying no longer depends on having an AI."""
    e = small_world()
    a = spawn_animal(e, 2, 1)
    a.ai = None
    a.handle_health(-5, e.player)
    assert a.hp == 0 and not a.is_alive