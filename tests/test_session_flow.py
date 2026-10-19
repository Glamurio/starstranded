"""Leaving a game for the menu and coming back, and the pause menu's settings screen."""
import random

import characters
import input_handlers as ih
import screens
import setup_game
from events import Key, KeyDown
from ui_helpers import SESSION


def test_continue_after_save_and_quit_stays_in_the_game(tmp_path, monkeypatch):
    random.seed(4)
    monkeypatch.setattr(setup_game, "SAVE_PATH", str(tmp_path / "save"))
    engine = setup_game.new_game(characters.create_character("T", "human", "survivalist", sponsor="heavy_industries"), SESSION)
    SESSION.reset(ih.MainGameEventHandler(engine))
    engine.save_as(setup_game.SAVE_PATH)
    menu = setup_game.MainMenu(SESSION)
    SESSION.reset(menu)                                  # what "Save & Quit to Main Menu" leaves behind
    menu.button_highlight = "Continue"
    handler = menu.resolve_menu(None)
    assert isinstance(handler, ih.MainGameEventHandler)
    assert SESSION.handlers == [handler]                 # the menu is gone from the stack
    for key in (Key.PERIOD, Key.ESCAPE, Key.ESCAPE):     # look, cancel it, open the pause menu, close it
        handler = handler.handle_events(KeyDown(key))
        assert not isinstance(handler, setup_game.MainMenu)


def test_pause_menu_opens_settings_over_the_game_and_esc_returns(new_engine, tmp_path, monkeypatch):
    import settings
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "s.json"))
    SESSION.handlers = [ih.MainGameEventHandler(new_engine)]
    pause = screens.PauseMenu(new_engine)
    SESSION.handlers.append(pause)
    state = pause._choose(1)
    assert isinstance(state, screens.InGameSettings)
    SESSION.handlers.append(state)
    state.on_render(SESSION.canvas)
    before = state.inner.settings.music_volume
    state.inner.row = 1
    state.handle_events(KeyDown(Key.LEFT))
    assert state.inner.settings.music_volume == max(0, before - 1)
    result = state.handle_events(KeyDown(Key.ESCAPE))
    assert isinstance(result, screens.PauseMenu)
    assert settings.load().music_volume == state.inner.settings.music_volume
