"""A corpse and a living unit can share a tile; game logic must address the living one."""
import actions
from components.ai import PassiveAI
from components.unit import Animal, Selenite


def corpse_at(e, x, y):
    c = Animal(); c.place(x, y, e.game_map)
    c.hp = 0
    c.die(None)
    return c


def test_unit_lookup_prefers_the_living_unit_in_either_insertion_order(small_world):
    e = small_world()
    corpse = corpse_at(e, 5, 5)
    alive = Animal(); alive.place(5, 5, e.game_map)
    assert e.game_map.get_unit_at_location(5, 5) is alive
    alive2 = Animal(); alive2.place(6, 6, e.game_map)
    corpse2 = corpse_at(e, 6, 6)
    assert e.game_map.get_unit_at_location(6, 6) is alive2


def test_corpse_is_still_found_when_alone(small_world):
    e = small_world()
    corpse = corpse_at(e, 5, 5)
    assert e.game_map.get_unit_at_location(5, 5) is corpse


def test_bump_attacks_the_living_unit_standing_on_a_corpse(small_world):
    e = small_world()
    corpse_at(e, 2, 1)
    s = Selenite(name="Zub"); s.place(2, 1, e.game_map)
    s.ai = None  # passive target
    s.max_hp = s.hp = 50
    actions.BumpAction(e.player, 2, 1).perform()
    assert s.hp < 50 and (e.player.x, e.player.y) == (1, 1)


def test_passive_ai_does_not_flee_from_corpses(small_world, monkeypatch):
    e = small_world()
    rabbit = Animal(); rabbit.place(5, 5, e.game_map)
    e.player.place(11, 9)  # far away
    s = Selenite(name="Dead"); s.place(6, 5, e.game_map)
    s.hp = 0
    s.die(None)
    fled = []
    monkeypatch.setattr(PassiveAI, "flee", lambda self, unit, distance=10: fled.append(unit))
    rabbit.ai.perform()
    assert fled == []
