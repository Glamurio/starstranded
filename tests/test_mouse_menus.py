"""Every menu can be driven with the mouse: tabs, `[key] action` hints, list rows, settings, creation, wheel."""
import pytest

import events
import input_handlers as ih
import main
import screens
import setup_game
import widgets
from events import Key, KeyDown, MouseButton, MouseButtonDown, MouseWheel, Point
from ui_helpers import SESSION


def click(handler, x, y, button=MouseButton.LEFT):
    return main.process(handler, MouseButtonDown(Point(x, y), button), SESSION)


def show(handler):
    SESSION.handlers = [handler] if not SESSION.handlers else SESSION.handlers
    SESSION.draw(handler)


def cell_of(rect):
    return rect.centerx // 24, rect.centery // 24


def test_tabs_are_clickable(new_engine):
    handler = ih.CharacterScreenEventHandler(new_engine)
    SESSION.handlers = [ih.MainGameEventHandler(new_engine), handler]
    SESSION.draw(handler)
    recipes_tab = SESSION.canvas.tab_rects[2]
    state = click(handler, *cell_of(recipes_tab))
    assert isinstance(state, ih.CraftingMenuHandler)
    SESSION.draw(state)
    state = click(state, *cell_of(SESSION.canvas.tab_rects[0]))
    assert isinstance(state, ih.InventoryActivateHandler)


def test_hints_are_clickable(new_engine):
    handler = ih.HistoryViewer(new_engine)
    SESSION.handlers = [ih.MainGameEventHandler(new_engine), handler]
    SESSION.draw(handler)
    rect = next(r for r, label in SESSION.canvas.hint_hits if label == "Esc")
    state = click(handler, *cell_of(rect))
    assert isinstance(state, ih.MainGameEventHandler)


def test_a_window_drawn_on_top_hides_the_hints_below(new_engine):
    main_handler = ih.MainGameEventHandler(new_engine)
    panel = ih.HistoryViewer(new_engine)
    popup = ih.PopupMessage(panel, "Hello")
    SESSION.handlers = [main_handler, panel]
    SESSION.draw(popup)
    labels = [label for _, label in SESSION.canvas.hint_hits]
    assert "any key" in labels
    x, y, w, h = 20, 15, 40, 10                          # the middle of the screen, where the popup sits
    import pygame
    middle = pygame.Rect(x * 24, y * 24, w * 24, h * 24)
    assert not any(middle.colliderect(r) for r, _ in SESSION.canvas.hint_hits if _ != "any key")


def test_popup_closes_on_a_click(new_engine):
    panel = ih.HistoryViewer(new_engine)
    popup = ih.PopupMessage(panel, "Hello")
    assert click(popup, 5, 5) is panel


def test_pod_rows_are_clickable(new_engine):
    pod = screens.PodHandler(new_engine)
    SESSION.handlers = [ih.MainGameEventHandler(new_engine), pod]
    pod.tab = 1                                          # the supply shop
    SESSION.draw(pod)
    rect = next(r for r, i in pod.list.hits if i == 2)
    click(pod, *cell_of(rect))
    assert pod.row == 2


def test_settings_rows_and_toggle(tmp_path, monkeypatch):
    import settings
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "s.json"))
    menu = setup_game.SettingsMenu(SESSION)
    SESSION.draw(menu)
    rect, index = menu.row_rects[0]
    before = menu.settings.master_volume
    click(menu, rect.x + rect.w - 2, rect.y)          # right half: louder
    assert menu.row == 0 and menu.settings.master_volume != before
    click(menu, rect.x + 1, rect.y)                   # left half: quieter
    assert menu.settings.master_volume == before


def test_character_creation_options_by_mouse():
    creation = setup_game.CharacterCreation(SESSION)
    creation.player.set_name("Ika")
    creation.step = 1                                  # the people
    SESSION.draw(creation)
    rect = next(r for r, i in creation.view.hits if i == 2)
    click(creation, *cell_of(rect))
    assert creation.choice["race"] == 2
    SESSION.draw(creation)
    click(creation, *cell_of(rect))                    # again: on to the next step
    assert creation.step == 2


def test_wheel_scrolls_lists(new_engine):
    handler = ih.HistoryViewer(new_engine)
    SESSION.handlers = [ih.MainGameEventHandler(new_engine), handler]
    before = handler.cursor
    main.process(handler, MouseWheel(1), SESSION)
    assert handler.cursor < before or before == 0


def test_the_map_ignores_the_wheel(new_engine):
    handler = ih.MainGameEventHandler(new_engine)
    SESSION.handlers = [handler]
    start = (new_engine.player.x, new_engine.player.y)
    main.process(handler, MouseWheel(1), SESSION)
    assert (new_engine.player.x, new_engine.player.y) == start
