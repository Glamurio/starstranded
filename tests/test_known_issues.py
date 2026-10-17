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


def test_current_character_creation_player_is_created_at_import_and_shared():
    assert setup_game.CharacterCreation.PLAYER is setup_game.CharacterCreation().PLAYER


def test_current_get_names_at_location_scans_all_entities(small_world):
    import render_functions
    e = small_world()
    e.game_map.visible[3, 3] = True
    a = Animal(); a.name = "Bun"; a.place(3, 3, e.game_map)
    assert "Bun" in render_functions.get_names_at_location(3, 3, e.game_map)
    assert render_functions.get_names_at_location(99, 99, e.game_map) == ""
