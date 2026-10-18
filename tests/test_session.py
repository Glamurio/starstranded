"""The UI session replaced the module of globals."""
import os

import pytest

import session as session_module
from session import Session
import input_handlers
import setup_game
from ui_helpers import SESSION


def test_g_module_is_gone():
    assert not os.path.exists(os.path.join(os.path.dirname(session_module.__file__), "g.py"))
    with pytest.raises(ImportError):
        __import__("g")


def test_a_detached_session_is_a_stack_without_a_window():
    s = Session()
    handler = object()
    s.push(handler)
    assert s.handlers == [handler]
    s.draw(handler)  # nothing to draw on: must not touch the handler
    s.render(handler)
    s.start_text_input()
    s.stop_text_input()
    s.reset("other")
    assert s.handlers == ["other"]


def test_engines_share_their_session_with_their_handlers(small_world):
    e = small_world()
    assert e.session is SESSION
    mine = Session()
    other = setup_game.new_game(setup_game.create_player(), mine)
    assert other.session is mine
    handler = input_handlers.MainGameEventHandler(other)
    assert handler.session is mine
    handler.reset_to_handler(handler)
    assert mine.handlers == [handler] and SESSION.handlers == []


def test_menu_flow_carries_the_session():
    mine = Session()
    menu = setup_game.MainMenu(mine)
    menu.button_highlight = "New Game"
    creation = menu.resolve_menu(None)
    assert creation.session is mine
