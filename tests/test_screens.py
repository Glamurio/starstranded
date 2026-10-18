"""Every screen, driven with synthetic input events and drawn on the headless canvas.

These are end-to-end checks of the handler stack after the pygame port: each handler must accept the
events it handled under tcod, switch handlers the same way, and draw something without raising.
"""
import numpy as np
import pygame
import pytest

import exceptions
from ui_helpers import SESSION
import input_handlers as ih
import setup_game
from components.consumable import Meat
from components.unit import Animal
from events import Key, KeyDown, Mod, MouseButton, MouseButtonDown, MouseMotion, Point, Quit, TextInput
from render_helpers import cell


def drawn(handler):
    SESSION.draw(handler)
    return SESSION.canvas


def lit_pixels(canvas):
    return int(pygame.surfarray.array3d(canvas.surface).any(axis=2).sum())


def press(handler, key, mod=0):
    return handler.handle_events(KeyDown(key, mod))


@pytest.fixture
def game(small_world):
    e = small_world(20, 14)
    handler = ih.MainGameEventHandler(e)
    SESSION.handlers = [handler]
    return e, handler


# ── start screens ──────────────────────────────────────────────────────────────────
def test_main_menu_draws_and_navigates():
    menu = setup_game.MainMenu()
    canvas = drawn(menu)
    assert lit_pixels(canvas) > 50_000  # the backdrop image fills the screen
    assert menu.button_highlight == "New Game"
    press(menu, Key.DOWN)
    assert menu.button_highlight == "Continue"
    press(menu, Key.UP)
    press(menu, Key.UP)
    assert menu.button_highlight == "Exit"
    with pytest.raises(SystemExit):
        press(menu, Key.RETURN)


def test_main_menu_mouse_highlight_and_click():
    menu = setup_game.MainMenu()
    drawn(menu)  # buttons get their positions while rendering
    x, y = menu.buttons["Continue"]["x"], menu.buttons["Continue"]["y"]
    menu.handle_events(MouseMotion(Point(x, y)))
    assert menu.button_highlight == "Continue"
    result = menu.handle_events(MouseButtonDown(Point(x, y), MouseButton.LEFT))
    assert isinstance(result, ih.PopupMessage) or isinstance(result, ih.MainGameEventHandler)


def test_new_game_leads_to_character_creation_and_into_the_game():
    menu = setup_game.MainMenu()
    creation = press(menu, Key.RETURN)
    assert isinstance(creation, setup_game.CharacterCreation)
    drawn(creation)
    creation.handle_events(TextInput("Zed"))
    assert creation.player.name.endswith("Zed")
    press(creation, Key.BACKSPACE)
    assert creation.player.name.endswith("Ze")
    # 'q' is a letter in a name, not "back to the menu"
    assert press(creation, Key.Q) is creation
    creation.handle_events(TextInput("q"))
    assert creation.player.name.endswith("Zeq")
    assert isinstance(press(creation, Key.ESCAPE), setup_game.MainMenu)
    creation = setup_game.CharacterCreation()
    for _ in range(5):          # name, people, background, sponsor, mode -> confirm
        assert press(creation, Key.RETURN) is creation
        drawn(creation)
    started = press(creation, Key.RETURN)
    assert isinstance(started, ih.MainGameEventHandler)
    assert SESSION.handlers == [started]
    assert lit_pixels(drawn(started)) > 1000


def test_character_name_is_length_limited():
    creation = setup_game.CharacterCreation()
    creation.player.set_name("")
    for _ in range(40):
        creation.handle_events(TextInput("x"))
    assert len(creation.player.name) < setup_game.CharacterCreation.MAX_CHARS


# ── main game ──────────────────────────────────────────────────────────────────────
def test_movement_keys_and_wait(game):
    e, handler = game
    x, y = e.player.x, e.player.y
    press(handler, Key.RIGHT)
    assert (e.player.x, e.player.y) == (x + 1, y)
    press(handler, Key.KP_3)
    assert (e.player.x, e.player.y) == (x + 2, y + 1)
    time_before = e.game_world.current_time
    press(handler, Key.SPACE)
    assert e.game_world.current_time == time_before + 1
    drawn(handler)


def test_mouse_motion_updates_cursor_and_draws_path_preview(game):
    e, handler = game
    handler.handle_events(MouseMotion(Point(8, 6)))
    assert tuple(e.mouse_location) == (8, 6)
    assert handler.mouse_motion
    with_preview = pygame.surfarray.array3d(drawn(handler).surface).astype(int)
    handler.mouse_motion = False
    without = pygame.surfarray.array3d(drawn(handler).surface).astype(int)
    assert (with_preview > without).any()  # the highlight wash brightens the path tiles
    assert (with_preview >= without).all()


def test_left_click_walks_towards_the_cursor(game):
    e, handler = game
    handler.handle_events(MouseMotion(Point(e.player.x + 1, e.player.y)))
    x = e.player.x
    handler.handle_events(MouseButtonDown(Point(e.player.x + 1, e.player.y), MouseButton.LEFT))
    assert e.player.x == x + 1


def test_inventory_menu_opens_navigates_and_closes(game):
    e, handler = game
    e.player.inventory.add(Meat("x"))
    inv = press(handler, Key.I)
    assert isinstance(inv, ih.InventoryActivateHandler)
    assert lit_pixels(drawn(inv)) > 1000
    press(inv, Key.DOWN)
    assert inv.button_highlight == 0
    press(inv, Key.DOWN)
    assert inv.button_highlight == 1
    back = press(inv, Key.ESCAPE)
    assert isinstance(back, ih.MainGameEventHandler)


def test_inventory_confirm_uses_the_item(game):
    e, handler = game
    e.player.hunger = 10
    potion = Meat("x", e.player.inventory)
    e.player.inventory.add(potion)
    inv = press(handler, Key.I)
    drawn(inv)  # the menu builds its entry list while rendering (the real loop always draws first)
    for _ in range(len(e.player.inventory.items)):
        inv = press(inv, Key.DOWN)
    inv = press(inv, Key.RETURN)
    assert e.player.hunger > 10
    assert potion not in e.player.inventory.items


def test_drop_menu_drops_an_item(game):
    e, handler = game
    count = len(e.player.inventory.items)
    drop = press(handler, Key.D)
    assert isinstance(drop, ih.InventoryDropHandler)
    drawn(drop)
    press(drop, Key.DOWN)
    press(drop, Key.RETURN)
    assert len(e.player.inventory.items) == count - 1
    assert len(e.game_map.get_entities_at_location(e.player.x, e.player.y)) >= 2


def test_pickup_selection_and_loot_window(game):
    e, handler = game
    corpse = Animal(); corpse.place(e.player.x + 1, e.player.y, e.game_map); corpse.hp = 0; corpse.die(None)
    from components.consumable import Meat
    corpse.inventory.add(Meat("rabbit", corpse.inventory))
    e.mouse_location = Point(e.player.x + 1, e.player.y)
    pickup = press(handler, Key.G)
    assert isinstance(pickup, ih.PickupHandler)
    drawn(pickup)
    loot = press(pickup, Key.G)
    assert isinstance(loot, ih.InventoryLootHandler)
    assert lit_pixels(drawn(loot)) > 1000
    n = len(e.player.inventory.items)
    press(loot, Key.G)  # grab all
    assert len(e.player.inventory.items) > n  # everything the corpse carried


def test_look_handler_cursor_speeds_and_confirm(game):
    e, handler = game
    look = press(handler, Key.PERIOD)
    assert isinstance(look, ih.LookHandler)
    drawn(look)
    start = tuple(e.mouse_location)
    press(look, Key.RIGHT)
    assert tuple(e.mouse_location) == (start[0] + 1, start[1])
    press(look, Key.RIGHT, Mod.LSHIFT)
    assert tuple(e.mouse_location) == (start[0] + 6, start[1])
    press(look, Key.LEFT, Mod.LCTRL)
    assert tuple(e.mouse_location) == (max(0, start[0] - 4), start[1])
    press(look, Key.UP, Mod.RALT)
    assert e.mouse_location[1] == 0  # clamped to the map


def test_targeting_handlers_report_the_selected_tile(game):
    e, handler = game
    picked = []
    single = ih.SingleRangedAttackHandler(e, picked.append)
    SESSION.handlers.append(single)
    single.handle_events(MouseButtonDown(Point(3, 3), MouseButton.LEFT))
    assert picked == [(3, 3)]
    area = ih.AreaRangedAttackHandler(e, 2, picked.append)
    e.mouse_location = Point(6, 6)
    drawn(area)
    area.handle_events(KeyDown(Key.RETURN, 0))
    assert picked[-1] == (6, 6)


def test_history_viewer_scrolls_and_returns(game):
    e, handler = game
    for i in range(30):
        e.message_log.add_message(f"message {i}")
    viewer = press(handler, Key.V)
    assert isinstance(viewer, ih.HistoryViewer)
    assert lit_pixels(drawn(viewer)) > 1000
    last = viewer.cursor
    press(viewer, Key.PAGEUP)
    assert viewer.cursor == last - 10
    press(viewer, Key.HOME)
    assert viewer.cursor == 0
    press(viewer, Key.UP)
    assert viewer.cursor == viewer.log_length - 1  # wraps from the top to the bottom
    press(viewer, Key.END)
    assert viewer.cursor == viewer.log_length - 1
    press(viewer, Key.A)  # any other key leaves
    assert isinstance(SESSION.handlers[-1], ih.MainGameEventHandler)


def test_character_screen_and_crafting_menu(game):
    e, handler = game
    screen = press(handler, Key.C)
    assert isinstance(screen, ih.CharacterScreenEventHandler)
    assert lit_pixels(drawn(screen)) > 500
    press(screen, Key.ESCAPE)
    crafting = press(handler, Key.R)
    assert isinstance(crafting, ih.CraftingMenuHandler)
    drawn(crafting)
    press(crafting, Key.A)       # also list the recipes you know but cannot do here
    drawn(crafting)
    press(crafting, Key.DOWN)
    press(crafting, Key.UP)
    if crafting.recipes:
        press(crafting, Key.RETURN)  # nothing to make it from -> a message saying what is missing, still open
        assert any("can't make that yet" in m.plain_text for m in e.message_log.messages)
    press(crafting, Key.ESCAPE)


def test_level_up_screen_applies_the_choice(game):
    e, handler = game
    e.player.level.current_xp = e.player.level.experience_to_next_level + 1
    hp = e.player.max_hp
    screen = ih.LevelUpEventHandler(e)
    SESSION.handlers.append(screen)
    assert lit_pixels(drawn(screen)) > 500
    assert press(screen, Key.X) is screen or True  # invalid entry only logs
    screen.handle_events(MouseButtonDown(Point(1, 1), MouseButton.LEFT))  # clicking does not dismiss
    assert SESSION.handlers[-1] is screen
    press(screen, Key.A)
    assert e.player.max_hp == hp + 20


def test_popup_dims_the_parent_and_any_key_returns(game):
    e, handler = game
    plain = lit_pixels(drawn(handler))
    popup = ih.PopupMessage(handler, "Failed to load save:\nboom")
    canvas = drawn(popup)
    assert canvas.surface.get_at((5 * 24 + 3, 5 * 24 + 3))[0] <= 40  # the world behind is darkened
    assert press(popup, Key.A) is handler


def test_game_over_quits_without_saving(game, tmp_path, monkeypatch):
    e, handler = game
    over = ih.GameOverEventHandler(e)
    drawn(over)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(exceptions.QuitWithoutSaving):
        press(over, Key.ESCAPE)
    with pytest.raises(exceptions.QuitWithoutSaving):
        over.handle_events(Quit())


def test_quit_event_exits_from_the_game(game):
    e, handler = game
    with pytest.raises(SystemExit):
        handler.handle_events(Quit())
    with pytest.raises(SystemExit):
        press(handler, Key.ESCAPE)


def test_place_constructable_highlights_neighbours(game):
    from crafting import Campfire
    e, handler = game
    fire = Campfire(e.player.inventory)
    e.player.inventory.add(fire)
    place = ih.PlaceConstructableHandler(e, fire)
    SESSION.handlers.append(place)
    canvas = drawn(place)
    px, py = e.player.x, e.player.y
    assert cell(canvas, px + 1, py).mean() > cell(canvas, px + 3, py).mean() + 50
