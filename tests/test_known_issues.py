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


def test_setup_game_uses_the_game_exceptions_module():
    """`from asyncio import exceptions` used to shadow the game's own `exceptions` module."""
    assert setup_game.exceptions.__name__ == "exceptions"
    assert issubclass(setup_game.exceptions.Impossible, Exception)


def test_character_creation_builds_a_fresh_player_each_time():
    a, b = setup_game.CharacterCreation(), setup_game.CharacterCreation()
    assert a.player is not b.player
    a.player.set_name("Changed")
    assert b.player.name == "Ardan"
    assert not hasattr(setup_game.CharacterCreation, "PLAYER")


def test_get_names_at_location_lists_entities_on_the_tile(small_world):
    import render_functions
    e = small_world()
    e.game_map.visible[3, 3] = True
    a = Animal(); a.name = "Bun"; a.place(3, 3, e.game_map)
    assert "Bun" in render_functions.get_names_at_location(3, 3, e.game_map)
    assert render_functions.get_names_at_location(99, 99, e.game_map) == ""
