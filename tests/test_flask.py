"""Leather, the flask, boiling, poison, creatures drinking."""
import numpy as np

import actions
import behavior
import exceptions
import liquids
import tile_types
from components.unit import Animal
from crafting import Flask, Leather, Campfire


def _liquid(kind, depth=1):
    tile = tile_types.water.get_array()
    tile["liquid"], tile["depth"], tile["walkable"] = kind, depth, depth == 1
    return tile


def _flask(e):
    flask = Flask(e.player.inventory)
    e.player.inventory.add(flask)
    return flask


def test_flask_title_never_reveals_the_kind(small_world):
    e = small_world()
    flask = _flask(e)
    flask.liquid, flask.sips = int(liquids.LiquidKind.TOXIC), 3
    assert "toxic" not in flask.get_title().lower() and "acid" not in flask.get_title().lower()


def test_fill_then_drink_raw_impure_poisons(small_world):
    e = small_world()
    e.game_map.set_tile(2, 1, _liquid(1))
    flask = _flask(e)
    actions.UseFlaskAction(e.player, flask).perform()
    assert flask.sips == liquids.FLASK_SIPS and not flask.boiled
    e.player.thirst = 10
    actions.UseFlaskAction(e.player, flask).perform()
    assert e.player.thirst == 10 + liquids.SIP_THIRST - 0 or e.player.thirst >= 10
    assert e.player.poison >= liquids.POISON_RAW - 1


def test_boiled_impure_is_safe_but_toxic_is_not(small_world):
    e = small_world()
    flask = _flask(e)
    camp = Campfire()
    camp.place(2, 1, e.game_map)
    camp.is_lit = camp.is_placed = True
    flask.liquid, flask.sips = int(liquids.LiquidKind.IMPURE), 3
    actions.UseFlaskAction(e.player, flask).perform()
    assert flask.boiled
    actions.UseFlaskAction(e.player, flask).perform()
    assert e.player.poison == 0
    flask.liquid, flask.sips, flask.boiled = int(liquids.LiquidKind.TOXIC), 2, True
    actions.UseFlaskAction(e.player, flask).perform()
    assert e.player.poison >= liquids.POISON_TOXIC - 1


def test_acid_destroys_the_flask(small_world):
    e = small_world()
    e.game_map.set_tile(2, 1, _liquid(3))
    flask = _flask(e)
    actions.UseFlaskAction(e.player, flask).perform()
    assert flask not in e.player.inventory.items


def test_empty_flask_away_from_liquid_is_impossible(small_world):
    e = small_world()
    flask = _flask(e)
    try:
        actions.UseFlaskAction(e.player, flask).perform()
    except exceptions.Impossible:
        return
    raise AssertionError("expected Impossible")


def test_poison_ticks_down(small_world):
    e = small_world()
    e.player.apply_poison(3)
    hp = e.player.hp
    e.player.tick_poison(2)
    assert e.player.hp == hp - 2 and e.player.poison == 1


def test_animals_drink_impure_only(small_world):
    e = small_world()
    e.game_map.set_tile(5, 5, _liquid(3))
    unit = Animal()
    unit.place(4, 5, e.game_map)
    assert behavior.find_liquid(unit, 10) is None
    e.game_map.set_tile(6, 5, _liquid(1))
    assert behavior.find_liquid(unit, 10) == (6, 5)
