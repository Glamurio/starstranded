"""AIs keep following a planned path instead of re-planning every turn."""
from components.unit import Selenite
from animals import Animal


def count_paths(engine, monkeypatch):
    calls = []
    original = engine.get_path_to

    def counting(*args, **kwargs):
        calls.append(args[1:3])
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "get_path_to", counting)
    return calls


def test_wander_keeps_its_destination_until_reached(small_world, monkeypatch):
    e = small_world(width=40, height=40)
    rabbit = Animal(); rabbit.place(20, 20, e.game_map)
    calls = count_paths(e, monkeypatch)
    rabbit.ai.wander()
    first = list(rabbit.ai.path)
    assert len(calls) == 1 and first
    if len(first) > 1:
        rabbit.ai.wander()
        assert len(calls) == 1  # still walking to the same spot
        assert rabbit.ai.path == first[1:]


def test_blocked_wander_replans_next_turn(small_world, monkeypatch):
    import exceptions
    e = small_world(width=40, height=40)
    rabbit = Animal(); rabbit.place(20, 20, e.game_map)
    rabbit.ai.path = [(21, 20), (22, 20)]
    blocker = Animal(); blocker.place(21, 20, e.game_map)
    try:
        rabbit.ai.wander()
    except exceptions.Impossible:
        pass
    assert rabbit.ai.path == []


def test_hostile_reuses_path_while_target_stays_put(small_world, monkeypatch):
    e = small_world(width=40, height=40)
    e.player.place(30, 30, e.game_map)
    e.update_fov()
    s = Selenite(name="Zub"); s.place(10, 10, e.game_map)
    e.game_map.explored[:] = True
    calls = count_paths(e, monkeypatch)
    monkeypatch.setattr(e.game_map, "is_visible", lambda x, y: True)
    s.ai.perform(); s.ai.perform(); s.ai.perform()
    assert len(calls) == 1
