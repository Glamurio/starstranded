"""Creatures hunt across distance and chunks, round obstacles, and use stairs."""
import actions
import behavior
import exceptions
import tile_types
from components.unit import Animal, Selenite


def _wall(e, x, y):
    e.game_map.set_tile(x, y, tile_types.wall.get_array() if hasattr(tile_types, "wall") else tile_types.floor.get_array())


def test_hostile_far_away_tracks_the_player_down(small_world):
    e = small_world(width=70, height=20)
    e.player.place(66, 5)
    e.update_fov()
    hunter = Selenite(name="Zub")
    hunter.place(22, 5, e.game_map)
    hunter.hunger = hunter.max_hunger
    for _ in range(60):
        try:
            behavior.act(hunter, hunter.ai, cheap=True)
        except exceptions.Impossible:
            pass
    assert hunter.x > 22 + 20, "the hunter should be closing in from 44 tiles away"


def test_hostile_beyond_sight_ignores_the_player(small_world):
    e = small_world(width=70, height=20)
    e.player.place(68, 5)
    hunter = Selenite(name="Zub")
    hunter.place(2, 5, e.game_map)
    hunter.hunger = hunter.max_hunger
    assert not behavior._hunt_player(hunter, hunter.ai, True, behavior.HOSTILE_SIGHT)


def test_greedy_hunter_gets_round_a_wall_by_planning(small_world):
    e = small_world(width=40, height=30)
    e.player.place(30, 10)
    for y in range(0, 24):
        e.game_map.set_tile(20, y, tile_types.wall.get_array())
    e.update_fov()
    hunter = Selenite(name="Zub")
    hunter.place(10, 10, e.game_map)
    hunter.hunger = hunter.max_hunger
    for _ in range(80):
        if hunter.x > 20:
            break
        try:
            behavior.act(hunter, hunter.ai, cheap=True)
        except exceptions.Impossible:
            pass
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
