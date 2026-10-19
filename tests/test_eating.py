"""Eating takes a turn, and a food the user cannot digest takes none."""
import pytest

import exceptions
import input_handlers as ih
from components.consumable import Meat, Ration
from test_review_fixes import new_game


def selected(engine, item):
    handler = ih.InventoryActivateHandler(engine, engine.player.inventory)
    engine.session.reset(handler)
    return handler.on_item_selected(item)


def test_eating_a_ration_passes_one_turn():
    engine = new_game()
    player = engine.player
    ration = Ration(player.inventory)
    player.inventory.add(ration)
    player.hunger = 50
    t0 = engine.game_world.current_time
    selected(engine, ration).perform()
    assert player.hunger > 50
    assert engine.game_world.current_time == t0 + 1
    assert ration not in player.inventory.items


def test_food_that_cannot_be_digested_costs_no_time():
    engine = new_game("selenite_people")
    player = engine.player
    meat = Meat("x", player.inventory)
    player.inventory.add(meat)
    t0 = engine.game_world.current_time
    with pytest.raises(exceptions.Impossible):
        selected(engine, meat).perform()
    assert engine.game_world.current_time == t0
    assert meat in player.inventory.items
