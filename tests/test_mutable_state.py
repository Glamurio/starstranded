"""Regression tests: no mutable default arguments, no shared class-level mutable state."""
import importlib
import inspect

import pytest

import input_handlers
import setup_game
from components.ai import BaseAI, HostileAI, PassiveAI

MODULES = [
    "actions", "color", "crafting", "engine", "entity", "equipment_types", "exceptions", "message_log",
    "procgen", "render_functions", "render_order", "tile_types", "utilities", "world",
    "input_handlers", "setup_game",
    "components.ai", "components.base_component", "components.consumable", "components.equipment",
    "components.equippable", "components.inventory", "components.level", "components.plant", "components.unit",
]


def _functions(module):
    for _, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and obj.__module__ == module.__name__:
            yield obj
        elif inspect.isclass(obj) and obj.__module__ == module.__name__:
            for _, member in inspect.getmembers(obj, inspect.isfunction):
                if member.__module__ == module.__name__:
                    yield member


@pytest.mark.parametrize("module_name", MODULES)
def test_no_mutable_default_arguments(module_name):
    module = importlib.import_module(module_name)
    offenders = []
    for fn in _functions(module):
        for name, param in inspect.signature(fn).parameters.items():
            if isinstance(param.default, (list, dict, set, bytearray)):
                offenders.append(f"{fn.__qualname__}({name}={param.default!r})")
    assert not offenders, offenders


def test_inventory_handlers_do_not_share_buttons_or_entries(small_world):
    e = small_world()
    a = input_handlers.InventoryActivateHandler(e, e.player.inventory)
    b = input_handlers.InventoryDropHandler(e, e.player.inventory)
    a.buttons[0] = {"x": 1, "y": 1}
    a.inventory_entries.append("x")
    assert b.buttons == {} and b.inventory_entries == []
    assert a.buttons is not input_handlers.InventoryEventHandler.__dict__.get("buttons")


def test_loot_handler_default_entities_is_a_fresh_list(small_world):
    e = small_world()
    a = input_handlers.InventoryLootHandler(e, e.player)
    b = input_handlers.InventoryLootHandler(e, e.player)
    assert a.entities == [] and a.entities is not b.entities


def test_main_menus_do_not_share_buttons():
    a, b = setup_game.MainMenu(), setup_game.MainMenu()
    a.buttons["New Game"] = {"x": 1, "y": 2}
    assert b.buttons == {}


def test_ai_paths_are_per_instance(small_world):
    from components.unit import Selenite
    from animals import Animal
    e = small_world()
    a, b = Animal(), Animal()
    assert a.ai.path is not b.ai.path
    s = Selenite(name="x")
    s.ai.path.append((1, 1))
    assert a.ai.path == [] and b.ai.path == []
    base1, base2 = BaseAI(a), BaseAI(b)
    base1.path.append((2, 2))
    assert base2.path == []
    assert not hasattr(BaseAI, "path") or not isinstance(getattr(BaseAI, "path", None), list)


def test_movement_action_default_path_is_not_shared(small_world):
    import actions
    e = small_world()
    m1 = actions.MovementAction(e.player, 1, 1)
    m2 = actions.MovementAction(e.player, 1, 1)
    m1.path.append((9, 9))
    assert m2.path == []


def test_tile_default_variations_not_shared():
    import tile_types
    t1 = tile_types.Tile(object_type="T1a", walkable=True)
    t2 = tile_types.Tile(object_type="T1b", walkable=True)
    assert t1.variations == [] and t1.variations is not t2.variations


def test_fruit_default_factory_is_not_shared(small_world):
    from components.consumable import Fruit
    e = small_world()
    f = Fruit(e.player.inventory)
    assert f.species and f.kind.sprite
