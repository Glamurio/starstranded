"""Felled trees leave stumps (except fungi and cacti)."""
import pickle

from components.plant import Stump, Tree
from species import PlantCategory, make_plant_species


def _tree(sprite):
    sp = make_plant_species(PlantCategory.TREE)
    import dataclasses
    sp = dataclasses.replace(sp, key=None, sprite=sprite)
    return Tree(sp)


def _stumps(e, x, y):
    return [t for t in e.game_map.get_entities_at_location(x, y) if isinstance(t, Stump)]


def test_deciduous_evergreen_and_palm_leave_a_stump(small_world):
    e = small_world()
    for i, sprite in enumerate([(0, 4), (3, 4), (11, 4)]):
        t = _tree(sprite)
        t.place(3 + i, 3, e.game_map)
        t.die(None)
        s = _stumps(e, 3 + i, 3)
        assert len(s) == 1 and not s[0].blocks_movement


def test_fungi_and_cacti_leave_none(small_world):
    e = small_world()
    for i, sprite in enumerate([(5, 4), (9, 4), (10, 4)]):
        t = _tree(sprite)
        t.place(3 + i, 3, e.game_map)
        t.die(None)
        assert not _stumps(e, 3 + i, 3)


def test_stump_is_walkable_and_not_pickable_and_pickles(small_world):
    e = small_world()
    t = _tree((0, 4))
    t.place(4, 4, e.game_map)
    t.die(None)
    stump = _stumps(e, 4, 4)[0]
    assert e.game_map.engine.can_move(4, 4)
    assert not hasattr(stump, "consume") and stump.get_title() == "Stump"
    e.game_map.remove_entity(stump)
    assert pickle.loads(pickle.dumps(stump)).kind is stump.kind
