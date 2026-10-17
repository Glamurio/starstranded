"""Characterization: plant spawning and the growth cycle."""
from components.plant import Tree, Shrub
from components.consumable import Fruit
from crafting import Branch


def make_fruiting_tree(engine, x=5, y=5):
    t = Tree().spawn(engine.game_map, x, y)
    # force deterministic fruiting
    t.fruit = Fruit
    t.fruit_factory = {"color": (200, 0, 0), "position": (3, 16), "species": "Redapple"}
    t.avg_cycle = 2.0
    t.growth = 0
    return t


def test_spawn_returns_a_distinct_clone_registered_with_map(small_world):
    e = small_world()
    proto = Tree()
    a = proto.spawn(e.game_map, 3, 3)
    b = proto.spawn(e.game_map, 4, 4)
    assert a is not proto and a is not b
    assert a in e.game_map.entities and (a.x, a.y) == (3, 3)
    assert a.parent is e.game_map


def test_tree_spawn_blocks_tile_shrub_does_not(small_world):
    e = small_world()
    Tree().spawn(e.game_map, 3, 3)
    Shrub().spawn(e.game_map, 4, 4)
    t = e.game_map.tiles
    assert not t["walkable"][3, 3] and not t["transparent"][3, 3]
    assert t["walkable"][4, 4] and t["transparent"][4, 4]


def test_growth_cycle_produces_branch_and_fruit(small_world):
    e = small_world()
    t = make_fruiting_tree(e)
    t.handle_growth(); t.handle_growth()
    assert t.inventory.items == [] and t.growth == 2
    t.handle_growth()  # growth 3 > 2.0 -> harvest
    kinds = sorted(type(i).__name__ for i in t.inventory.items)
    assert kinds == ["Branch", "Fruit"] and t.growth == 0


def test_plant_without_fruit_never_grows(small_world):
    e = small_world()
    t = make_fruiting_tree(e)
    t.fruit = None
    for _ in range(20):
        t.handle_growth()
    assert t.inventory.items == [] and t.growth == 0


def test_full_inventory_drops_an_item_on_an_adjacent_tile(small_world):
    e = small_world()
    t = make_fruiting_tree(e)
    for _ in range(10):
        t.inventory.add(Branch(t))
    assert t.inventory.is_full()
    for _ in range(3):
        t.handle_growth()
    dropped = [i for i in e.game_map.items if i.parent is e.game_map]
    assert len(dropped) == 1
    assert max(abs(dropped[0].x - t.x), abs(dropped[0].y - t.y)) == 1


def test_plant_ai_grows_only_on_even_minutes(small_world):
    e = small_world()
    t = make_fruiting_tree(e)
    e.game_world.current_time = 1
    t.ai.perform()
    assert t.growth == 0
    e.game_world.current_time = 2
    t.ai.perform()
    assert t.growth == 1


def test_current_plant_die_swaps_in_roots_and_blocks_tile(small_world):
    """Flagged in DECISIONS.md: a dead plant leaves an opaque, unwalkable roots tile."""
    e = small_world()
    t = Tree().spawn(e.game_map, 3, 3)
    t.die(e.player)
    tiles = e.game_map.tiles
    assert not tiles["transparent"][3, 3] and not tiles["walkable"][3, 3]
    assert t.ai is None and not t.blocks_movement
