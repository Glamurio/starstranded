"""Pins CURRENT behavior of bugs found while reading the code (Phase 0).

Every test here is named ``test_current_*`` and passes on the untouched code. When Phase 1 fixes
an issue, the corresponding test is inverted/renamed in the same commit as the fix.
"""
import pytest

import actions
import input_handlers
import setup_game
from components.consumable import HealthPotion
from components.unit import Animal


def test_current_level_up_crashes(small_world):
    """Level.increase_* read/write max_hp, hp, base_power on the *Level component*, not the unit."""
    e = small_world()
    with pytest.raises(AttributeError):
        e.player.level.increase_max_hp()
    with pytest.raises(AttributeError):
        e.player.level.increase_power()
    with pytest.raises(AttributeError):
        e.player.level.increase_defense()


def test_current_inventory_render_crashes_with_a_health_potion(small_world):
    """InventoryEventHandler.on_render does chr(entity.char); HealthPotion.char is the str '!'."""
    import g

    e = small_world()
    e.player.inventory.add(HealthPotion())
    handler = input_handlers.InventoryActivateHandler(e, e.player.inventory)
    g.handlers = [input_handlers.MainGameEventHandler(e), handler]
    g.root_console.clear()
    with pytest.raises(TypeError):
        handler.on_render(g.root_console)


def test_current_get_unit_at_location_may_return_a_corpse(small_world):
    """`units` includes dead units; a corpse and a living unit on one tile are indistinguishable."""
    e = small_world()
    corpse = Animal(); corpse.place(5, 5, e.game_map)
    corpse.hp = 0
    corpse.die(e.player)
    alive = Animal(); alive.place(5, 5, e.game_map)
    assert e.game_map.get_unit_at_location(5, 5) in {corpse, alive}  # which one is set-order luck


def test_setup_game_uses_the_game_exceptions_module():
    """`from asyncio import exceptions` used to shadow the game's own `exceptions` module."""
    assert setup_game.exceptions.__name__ == "exceptions"
    assert issubclass(setup_game.exceptions.Impossible, Exception)


def test_current_character_creation_player_is_created_at_import_and_shared():
    assert setup_game.CharacterCreation.PLAYER is setup_game.CharacterCreation().PLAYER


def test_current_get_names_at_location_scans_all_entities(small_world):
    import render_functions
    e = small_world()
    e.game_map.visible[3, 3] = True
    a = Animal(); a.name = "Bun"; a.place(3, 3, e.game_map)
    assert "Bun" in render_functions.get_names_at_location(3, 3, e.game_map)
    assert render_functions.get_names_at_location(99, 99, e.game_map) == ""
