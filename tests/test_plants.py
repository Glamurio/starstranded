"""Plant spawning (no deepcopy) and the growth cycle."""
import dataclasses

from components.plant import Tree, Shrub
from components.consumable import Fruit
from crafting import Branch
from species import ItemKind, PlantCategory, make_plant_species

RED_APPLE = ItemKind(None, "Consumable", species="Redapple", sprite=(3, 16), color=(200, 0, 0), shade_sigma=10,
                     hunger_amount=10, thirst_amount=10)


def plant_at(engine, plant, x, y):
    engine.game_map.add_entity(plant, x, y)
    return plant


def make_fruiting_tree(engine, x=5, y=5, fruit=RED_APPLE):
    species = dataclasses.replace(make_plant_species(PlantCategory.TREE), fruit=fruit)
    t = plant_at(engine, Tree(species), x, y)
    t.avg_cycle = 2.0  # deterministic harvest on the 3rd growth tick
    return t


def test_plants_of_one_species_share_the_definition_but_not_state(small_world):
    """No deepcopy: each plant is a fresh instance that references the same immutable species."""
    e = small_world()
    species = make_plant_species(PlantCategory.TREE)
    a = plant_at(e, Tree(species), 3, 3)
    b = plant_at(e, Tree(species), 4, 4)
    assert a is not b and a.kind is b.kind is species
    assert a.inventory is not b.inventory
    assert a in e.game_map.entities and (a.x, a.y) == (3, 3) and a.parent is e.game_map


def test_tree_blocks_its_tile_shrub_does_not(small_world):
    e = small_world()
    plant_at(e, Tree(), 3, 3)
    plant_at(e, Shrub(), 4, 4)
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
    fruit = next(i for i in t.inventory.items if isinstance(i, Fruit))
    assert fruit.kind is RED_APPLE and fruit.get_title() == "Redapple"


def test_plant_without_fruit_never_grows(small_world):
    e = small_world()
    t = make_fruiting_tree(e, fruit=None)
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


def run_queue(e, until):
    for now in range(e.game_world.current_time + 1, until + 1):
        e.game_world.current_time = now
        e.game_map.plant_queue.run(now)


def test_plant_queue_grows_only_when_a_cycle_completes(small_world):
    e = small_world()
    t = make_fruiting_tree(e)
    e.game_map.plant_queue.schedule(t, 0)
    assert t.due == 6  # 3 growth steps, one per 2 turns
    run_queue(e, 5)
    assert t.inventory.items == [] and t.growth == 0  # nothing happens in between
    run_queue(e, 6)
    assert sorted(type(i).__name__ for i in t.inventory.items) == ["Branch", "Fruit"] and t.growth == 0
    assert t.due == 12


def test_plant_queue_matches_per_turn_growth(small_world):
    """Event-driven growth is exactly the old per-turn polling (growth step every 2nd turn)."""
    import random
    from simulation import upkeep
    rng = random.Random(5)
    for trial in range(12):
        e = small_world(width=30, height=30)
        e.game_world.current_time = rng.randrange(0, 9)
        a = make_fruiting_tree(e, 5, 5)
        b = make_fruiting_tree(e, 20, 20)
        a.avg_cycle = b.avg_cycle = rng.uniform(0, 9)
        a.growth = b.growth = rng.randrange(0, int(a.avg_cycle) + 1)  # growth never exceeds avg_cycle
        a.inventory.capacity = b.inventory.capacity = 10_000
        e.game_map.plant_queue.schedule(a, e.game_world.current_time)
        b.due = None  # b is the per-turn reference: its queue entries no longer validate
        start = e.game_world.current_time
        for now in range(start + 1, start + 80):
            e.game_world.current_time = now
            e.game_map.plant_queue.run(now)
            if now % 2 == 0:
                b.handle_growth()
            upkeep(a, now)  # growth is lazy between harvests; bring it up to date to compare
            assert (a.growth, len(a.inventory.items)) == (b.growth, len(b.inventory.items)), (trial, now)


def test_removed_plants_are_dropped_from_the_queue(small_world):
    e = small_world()
    t = make_fruiting_tree(e)
    e.game_map.plant_queue.schedule(t, 0)
    e.game_map.remove_entity(t)
    run_queue(e, 40)
    assert t.inventory.items == []


def test_a_full_plant_keeps_dropping_fruit_while_its_chunk_is_not_watched(small_world):
    e = small_world(width=20, height=20)
    t = make_fruiting_tree(e, 10, 10)
    t.inventory.capacity = 2
    e.game_map.plant_queue.schedule(t, 0)
    run_queue(e, 60)
    assert len([i for i in e.game_map.items if i.parent is e.game_map]) >= 3


def test_current_plant_die_swaps_in_roots_and_blocks_tile(small_world):
    """Flagged in DECISIONS.md: a dead plant leaves an opaque, unwalkable roots tile."""
    e = small_world()
    t = plant_at(e, Tree(), 3, 3)
    t.die(e.player)
    tiles = e.game_map.tiles
    assert not tiles["transparent"][3, 3] and not tiles["walkable"][3, 3]
    assert t.ai is None and not t.blocks_movement
