"""GameMap is the single owner of entity positions; its indexes must never go stale."""
import random

import pytest

import actions
from components.consumable import Meat
from components.plant import Tree
from components.unit import Animal
from index_helpers import assert_index_consistent
from render_order import RenderOrder


def test_add_move_remove_keep_index_consistent(small_world):
    e = small_world()
    m = e.game_map
    a = Animal(); m.add_entity(a, 3, 3)
    assert m.get_entities_at_location(3, 3) == [a] and m.is_blocked(3, 3)
    a.x = 4  # property assignment routes through the map
    assert m.get_entities_at_location(3, 3) == [] and m.get_entities_at_location(4, 3) == [a]
    assert not m.is_blocked(3, 3) and m.is_blocked(4, 3)
    a.place(5, 6)
    assert (a.x, a.y) == (5, 6) and m.get_unit_at_location(5, 6) is a
    assert_index_consistent(m)
    m.remove_entity(a)
    assert a.parent is None and a not in m.entities and not m.is_blocked(5, 6)
    assert_index_consistent(m)


def test_flag_changes_update_blocked_buckets_and_actors(small_world):
    e = small_world()
    m = e.game_map
    a = Animal(); a.place(2, 2, m)
    chunk = m.chunk_of(a)
    assert a in m.actors and a in chunk.buckets[RenderOrder.UNIT]
    a.hp = 0
    a.die(e.player)
    assert a not in m.actors
    assert a in chunk.buckets[RenderOrder.CORPSE] and not m.is_blocked(2, 2)
    assert_index_consistent(m)


def test_entities_can_be_reattached_between_maps_and_inventories(small_world):
    e1, e2 = small_world(), small_world()
    pot = Meat("x"); pot.place(3, 3, e1.game_map)
    pot.place(4, 4, e2.game_map)
    assert pot not in e1.game_map.entities and pot.parent is e2.game_map
    e2.player.inventory.loot(pot)
    assert pot not in e2.game_map.entities and pot in e2.player.inventory.items
    actions.DropItem(e2.player, pot, (2, 2)).perform()
    assert pot.parent is e2.game_map and (pot.x, pot.y) == (2, 2)
    assert_index_consistent(e1.game_map)
    assert_index_consistent(e2.game_map)


def test_looting_an_item_already_in_own_inventory_does_not_duplicate(small_world):
    e = small_world()
    meat = Meat("x", e.player.inventory); e.player.inventory.add(meat)
    e.player.inventory.loot(meat)
    assert e.player.inventory.items.count(meat) == 1


def test_iteration_order_is_insertion_order(small_world):
    e = small_world()
    m = e.game_map
    added = [Animal() for _ in range(20)]
    for i, a in enumerate(added):
        a.place(i % 10, i // 10 + 3, m)
    assert [u for u in m.units if u is not e.player] == added


def test_random_walk_soak_keeps_index_consistent(small_world):
    e = small_world(width=20, height=15)
    m = e.game_map
    rng = random.Random(4)
    pool = [Animal() for _ in range(15)] + [Meat("x") for _ in range(10)]
    for ent in pool:
        ent.place(rng.randrange(20), rng.randrange(15), m)
    for step in range(600):
        ent = rng.choice(pool)
        roll = rng.random()
        if roll < 0.6 and ent.parent is m:
            ent.move(rng.randrange(20), rng.randrange(15))
        elif roll < 0.75 and ent.parent is m:
            m.remove_entity(ent)
        elif roll < 0.9:
            m.add_entity(ent, rng.randrange(20), rng.randrange(15))
        elif ent.parent is m and isinstance(ent, Animal) and ent.is_alive:
            ent.die(None)
    assert_index_consistent(m)


def test_identity_is_preserved_on_move_and_save_roundtrip(new_engine, tmp_path):
    import setup_game
    e = new_engine
    rabbit = next(u for u in e.game_map.units if u is not e.player)
    uid = rabbit.uid
    rabbit.hunger = 42
    rabbit.place(*next((x, y) for x in range(70) for y in range(40) if e.can_move(x, y)))
    path = str(tmp_path / "s.sav")
    e.save_as(path)
    loaded = setup_game.load_game(path)
    twin = next(u for u in loaded.game_map.units if u.uid == uid)
    assert twin.hunger == 42 and (twin.x, twin.y) == (rabbit.x, rabbit.y)
    assert_index_consistent(loaded.game_map)


def test_generated_floor_index_is_consistent(new_engine):
    assert_index_consistent(new_engine.game_map)
    for _ in range(30):
        actions.WaitAction(new_engine.player).perform()
    assert_index_consistent(new_engine.game_map)


def test_trees_registered_as_plants_and_block(small_world):
    e = small_world()
    t = Tree(); e.game_map.add_entity(t, 4, 4)
    assert t in e.game_map.plants and e.game_map.is_blocked(4, 4)
