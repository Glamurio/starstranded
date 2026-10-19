"""Creatures hunt across distance and chunks, round obstacles, and use stairs."""
import actions
import behavior
import exceptions
import tile_types
from components.unit import Selenite
from animals import Animal


def _wall(e, x, y):
    e.game_map.set_tile(x, y, tile_types.wall.get_array() if hasattr(tile_types, "wall") else tile_types.floor.get_array())


def _act(hunter, turns):
    for _ in range(turns):
        try:
            behavior.act(hunter, hunter.ai, cheap=True)
        except exceptions.Impossible:
            pass


def _hunter(e, x, y):
    hunter = Selenite(name="Zub")
    hunter.place(x, y, e.game_map)
    hunter.hunger = hunter.max_hunger
    hunter.thirst = hunter.max_thirst
    return hunter


def test_hostile_in_sight_closes_in_on_the_player(small_world):
    e = small_world(width=70, height=20)
    e.player.place(30, 5)
    e.update_fov()
    hunter = _hunter(e, 22, 5)
    _act(hunter, 6)
    assert hunter.x > 22


def test_hostile_far_away_does_not_home_in_on_the_player(small_world):
    e = small_world(width=70, height=20)
    e.player.place(66, 5)
    e.update_fov()
    hunter = _hunter(e, 22, 5)
    assert behavior.find_enemy(hunter) is None
    for _ in range(40):
        _act(hunter, 1)
        assert hunter.x < 22 + 14, "a hunter 44 tiles away has no idea where the player is"


def test_a_wall_hides_the_player_and_the_hunter_gives_up_after_its_memory(small_world):
    e = small_world(width=70, height=20)
    e.player.place(30, 5)
    e.update_fov()
    hunter = _hunter(e, 24, 5)
    assert behavior.find_enemy(hunter) is hunter.game_map.get_unit_at_location(30, 5)
    for y in range(0, 20):
        e.game_map.set_tile(27, y, tile_types.wall.get_array())
    assert behavior.find_enemy(hunter) is None
    hunter.ai.memory = [30, 5, 3]
    assert behavior._search(hunter, hunter.ai, True)             # still heading for where it last saw him
    hunter.ai.memory = [30, 5, 0]
    assert not behavior._search(hunter, hunter.ai, True) and hunter.ai.memory is None


def test_hostile_remembers_and_follows_to_the_last_seen_spot(small_world):
    e = small_world(width=70, height=20)
    e.player.place(40, 5)
    hunter = _hunter(e, 20, 5)
    hunter.ai.memory = [40, 5, behavior.MEMORY_TURNS]
    start = hunter.x
    _act(hunter, 5)
    assert hunter.x > start


def test_greedy_hunter_gets_round_a_wall_by_planning(small_world):
    e = small_world(width=40, height=30)
    e.player.place(30, 10)
    for y in range(0, 24):
        e.game_map.set_tile(20, y, tile_types.wall.get_array())
    e.update_fov()
    hunter = _hunter(e, 10, 10)
    hunter.ai.memory = [30, 10, 200]
    for _ in range(80):
        if hunter.x > 20:
            break
        _act(hunter, 1)
    assert hunter.x > 20


def test_hostile_next_to_the_player_follows_through_the_stairs(new_engine):
    e = new_engine
    gw = e.game_world
    surface = e.game_map
    spot = surface.downstairs_location
    e.player.place(*spot)
    hunter = Selenite(name="Zub")
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if surface.is_walkable(spot[0] + dx, spot[1] + dy) and not surface.is_blocked(spot[0] + dx, spot[1] + dy):
            hunter.place(spot[0] + dx, spot[1] + dy, surface)
            break
    actions.TakeStairsAction(e.player, -1).perform()
    assert hunter.parent is None and gw.arrivals, "he is on the stairs, not yet down"
    gw.current_time += 3
    gw.release_arrivals()
    assert hunter.parent is e.game_map and e.game_map.z == -1
    assert max(abs(hunter.x - e.player.x), abs(hunter.y - e.player.y)) <= 3


def test_followers_are_placed_when_the_player_moves_on_or_saves(new_engine):
    e = new_engine
    gw = e.game_world
    surface = e.game_map
    spot = surface.downstairs_location
    e.player.place(*spot)
    hunter = Selenite(name="Zub")
    hunter.place(spot[0] + 1, spot[1], surface) if surface.is_walkable(spot[0] + 1, spot[1]) else hunter.place(spot[0], spot[1] + 1, surface)
    actions.TakeStairsAction(e.player, -1).perform()
    gw.release_arrivals(everyone=True)
    assert not gw.arrivals and hunter.parent is not None


def test_peaceful_creature_on_stairs_eventually_uses_them(new_engine, monkeypatch):
    e = new_engine
    surface = e.game_map
    rabbit = Animal()
    rabbit.place(*surface.downstairs_location, surface)
    monkeypatch.setattr("random.random", lambda: 0.0)
    assert behavior.use_stairs(rabbit)
    assert rabbit.parent is None or rabbit.game_map.z == -1  # stored with its chunk on the cave layer
