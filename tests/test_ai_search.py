"""AI food search via the spatial index, and bounded fleeing."""
import random

import pytest

from components.consumable import Meat
from components.plant import Tree
from animals import Animal
from index_helpers import assert_index_consistent


def test_entities_on_ring(small_world):
    e = small_world(width=20, height=20)
    m = e.game_map
    a = Animal(); a.place(10, 10, m)
    placed = {}
    for (x, y) in [(10, 10), (11, 9), (13, 10), (7, 13), (10, 14), (16, 16)]:
        meat = Meat("x"); meat.place(x, y, m); placed[(x, y)] = meat
    def ring(r):
        return {(i.x, i.y) for i in m.entities_on_ring(10, 10, r) if isinstance(i, Meat)}
    assert ring(0) == {(10, 10)} and ring(1) == {(11, 9)} and ring(3) == {(13, 10), (7, 13)}
    assert ring(4) == {(10, 14)} and ring(2) == set()
    # every cell is on exactly one ring
    assert sum(len([i for i in m.entities_on_ring(10, 10, r) if isinstance(i, Meat)]) for r in range(0, 11)) == 6


def test_hungry_rabbit_eats_adjacent_ground_food(small_world):
    e = small_world()
    e.player.place(11, 9)  # out of the rabbit's sight, or it would run away instead of eating
    rabbit = Animal(); rabbit.place(5, 5, e.game_map)
    rabbit.hunger = 50
    from components.consumable import Fruit
    fruit = Fruit(); fruit.place(6, 5, e.game_map)
    rabbit.ai.perform()
    assert fruit in rabbit.inventory.items  # it loots the fruit this turn and eats it on the next
    assert_index_consistent(e.game_map)


def test_hungry_rabbit_forages_adjacent_fruiting_plant(small_world):
    import dataclasses
    from components.consumable import Fruit
    from species import ItemKind, PlantCategory, make_plant_species
    e = small_world()
    fruit_kind = ItemKind(None, "Consumable", species="Testberry", sprite=(18, 21), hunger_amount=10, thirst_amount=10)
    tree = Tree(dataclasses.replace(make_plant_species(PlantCategory.TREE), fruit=fruit_kind))
    tree.place(6, 5, e.game_map)
    berry = Fruit(tree.inventory, fruit_kind); tree.inventory.add(berry)
    e.player.place(11, 9)
    rabbit = Animal(); rabbit.place(5, 5, e.game_map)
    rabbit.hunger = 50
    rabbit.ai.perform()
    assert berry in rabbit.inventory.items


def test_flee_gives_up_instead_of_spinning_forever(small_world):
    e = small_world(width=6, height=6)  # nothing is 10+ tiles away
    rabbit = Animal(); rabbit.place(2, 2, e.game_map)
    threat = Animal(); threat.place(3, 3, e.game_map)
    import exceptions
    try:
        rabbit.ai.flee(threat, distance=10)  # returns (falls back to wandering) instead of hanging
    except exceptions.Impossible:
        pass  # a blocked wander step; the turn loop swallows these
    assert_index_consistent(e.game_map)
