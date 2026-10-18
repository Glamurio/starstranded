"""Settings persistence and the stepped character creation."""
import pytest

import input_handlers as ih
import settings
import setup_game
from events import Key, KeyDown, TextInput
from ui_helpers import SESSION


def press(handler, key):
    return handler.handle_events(KeyDown(key, 0))


def test_settings_roundtrip_and_clamp(tmp_path):
    path = str(tmp_path / "s.json")
    s = settings.Settings(master_volume=99, music_volume=-3, fullscreen=True)
    settings.save(s, path)
    loaded = settings.load(path)
    assert (loaded.master_volume, loaded.music_volume, loaded.fullscreen) == (10, 0, True)


def test_broken_settings_file_gives_defaults(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{not json")
    assert settings.load(str(path)) == settings.Settings()
    assert settings.load(str(tmp_path / "missing.json")) == settings.Settings()


def test_effective_volume():
    s = settings.Settings(master_volume=5, music_volume=10)
    assert s.effective("music") == pytest.approx(0.5)


def test_settings_menu_edits_and_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "s.json"))
    menu = setup_game.SettingsMenu(settings=settings.Settings(master_volume=5))
    press(menu, Key.LEFT)
    assert menu.settings.master_volume == 4
    press(menu, Key.DOWN)
    press(menu, Key.RIGHT)
    assert menu.settings.music_volume == 8
    press(menu, Key.DOWN)
    press(menu, Key.DOWN)
    assert menu.row == 3
    back = press(menu, Key.ESCAPE)
    assert isinstance(back, setup_game.MainMenu)
    assert settings.load().music_volume == 8


def test_main_menu_has_settings_and_exit():
    menu = setup_game.MainMenu()
    assert menu.button_names == ["New Game", "Continue", "Settings", "Sprite editor", "Exit"]
    menu.button_highlight = "Settings"
    assert isinstance(menu.resolve_menu(None), setup_game.SettingsMenu)


def test_creation_builds_the_chosen_character_and_mode():
    creation = setup_game.CharacterCreation()
    creation.player.set_name("Ika")
    press(creation, Key.RETURN)                       # -> race
    press(creation, Key.DOWN)                         # selenite
    press(creation, Key.RETURN)                       # -> background
    for _ in range(3):
        press(creation, Key.DOWN)                     # 4th background
    press(creation, Key.RETURN)                       # -> sponsor
    press(creation, Key.DOWN)
    press(creation, Key.RETURN)                       # -> mode
    press(creation, Key.DOWN)                         # casual
    press(creation, Key.RETURN)                       # -> confirm
    started = press(creation, Key.RETURN)
    assert isinstance(started, ih.MainGameEventHandler)
    engine = started.engine
    assert engine.player.name == "Ika"
    assert engine.player.kind.key == "selenite_people"
    assert engine.game_world.run.mode == "casual"
    assert engine.game_world.run.sponsor == creation.options("sponsor")[1][0]
    assert engine.player.background == creation.options("background")[3][0]


def test_escape_walks_back_one_step():
    creation = setup_game.CharacterCreation()
    press(creation, Key.RETURN)
    assert creation.step == 1
    press(creation, Key.ESCAPE)
    assert creation.step == 0


def test_every_step_renders():
    from ui_helpers import SESSION as S
    creation = setup_game.CharacterCreation()
    for _ in range(5):
        S.draw(creation)
        press(creation, Key.RETURN)
    S.draw(creation)
