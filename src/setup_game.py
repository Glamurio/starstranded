"""Handle the loading and initialization of game sessions."""
from __future__ import annotations

import g
import exceptions
import lzma
import pickle
import traceback
from typing import TYPE_CHECKING, Optional

import pygame

import color
import events
from events import Key, Point
from ui import CENTER
from engine import Engine

import input_handlers

from utilities import is_mouse_in_rectangle

if TYPE_CHECKING:
    from ui import Canvas
    from components.unit import Unit

_background_image = None

def background_image() -> pygame.Surface:
    """The main menu's backdrop (loaded once, on first use)."""
    global _background_image
    if _background_image is None:
        _background_image = pygame.image.load("menu_background.png")
    return _background_image

def create_player() -> Unit:
    from components.unit import Player
    import components.equippable as equip

    player = Player()

    dagger = equip.Dagger(player.inventory)
    player.inventory.add(dagger)
    player.equipment.toggle_equip(dagger, add_message=False)

    leather_armor = equip.LeatherArmor(player.inventory)
    player.inventory.add(leather_armor)
    player.equipment.toggle_equip(leather_armor, add_message=False)

    return player

def new_game(player: Unit) -> Engine:
    """Return a brand new game session as an Engine instance."""
    from world import GameWorld
    
    map_width = g.screen_width - g.screen_width_offset
    map_height = g.screen_height - g.screen_height_offset

    room_max_size = 10
    room_min_size = 6
    max_rooms = 30

    try:
        engine = Engine(player=player)
    except:
        raise exceptions.Impossible("No player found.")

    engine.game_world = GameWorld(
        engine=engine,
        max_rooms=max_rooms,
        room_min_size=room_min_size,
        room_max_size=room_max_size,
        map_width=map_width,
        map_height=map_height,
    )

    engine.game_world.generate_floor()
    engine.update_fov()
    
    engine.message_log.add_message(
        f"Hello and welcome, {player.name}, to yet another dungeon!", color.welcome_text
    )

    return engine

def load_game(filename: str) -> Engine:
    """Load an Engine from a save file written by `Engine.save_as`.

    Raises `exceptions.IncompatibleSave` for saves from other versions (old saves are not migrated).
    """
    from engine import SAVE_VERSION
    from entity import bump_uid_counter

    with open(filename, "rb") as f:
        raw = f.read()
    try:
        payload = pickle.loads(lzma.decompress(raw))
    except Exception as exc:  # corrupt file, or classes that no longer exist
        raise exceptions.IncompatibleSave(f"Unreadable save file ({type(exc).__name__}).") from exc
    if not isinstance(payload, dict) or payload.get("version") != SAVE_VERSION:
        found = payload.get("version", "unknown") if isinstance(payload, dict) else 1
        raise exceptions.IncompatibleSave(
            f"Save file version {found} is not supported (this game uses version {SAVE_VERSION})."
        )
    engine = payload["engine"]
    assert isinstance(engine, Engine)
    bump_uid_counter(_max_uid(engine) + 1)  # entities created after loading must not reuse uids
    return engine


def _max_uid(engine: Engine) -> int:
    highest = 0
    stack = list(engine.game_map.entities) + [engine.player]
    while stack:
        entity = stack.pop()
        highest = max(highest, entity.uid)
        inventory = getattr(entity, "inventory", None)
        if inventory is not None:
            stack.extend(inventory.items)
    return highest

class MainMenu(input_handlers.BaseEventHandler):
    """Handle the main menu rendering and input."""

    console_height: int
    console_width: int
    menu_width = 12
    menu_i: int = 0

    buttons: dict
    button_height = 2
    button_names = ["New Game", "Continue", "Quit"]
    button_highlight = button_names[menu_i]

    def on_init(self) -> None:
        self.buttons = {}  # per-instance (was a class-level dict shared by all menus)

    def resolve_menu(self, event: events.Event):
        """Resolves button and click logic"""
        
        if self.button_highlight == 'New Game':
            # New Game
            return CharacterCreation()
        elif self.button_highlight == 'Continue':
            # Continue Game
            try:
                return input_handlers.MainGameEventHandler(load_game("savegame.sav"))
            except FileNotFoundError:
                return input_handlers.PopupMessage(self, "No saved game to load.")
            except Exception as exc:
                traceback.print_exc()  # Print to stderr.
                return input_handlers.PopupMessage(self, f"Failed to load save:\n{exc}")
        elif self.button_highlight == 'Quit':
            # Quit
            raise SystemExit()

    def on_render(self, canvas: Canvas) -> None:
        """Render the main menu on a background image."""
        self.console_height = canvas.height
        self.console_width = canvas.width
        canvas.blit_image(background_image())

        canvas.print(
            canvas.width // 2,
            canvas.height // 2 - 4,
            text="Starstranded",
            fg=color.menu_title,
            alignment=CENTER,
        )
        canvas.print(
            canvas.width // 2,
            canvas.height - 2,
            text="By Ryou",
            fg=color.menu_title,
            alignment=CENTER,
        )

        # Iterate over menu buttons, save their position for highlighting
        for i, text in enumerate(self.button_names):

            button_x = canvas.width // 2
            button_y = canvas.height // 2 - 2 + (i*2)

            self.buttons[text] = {
                'x': button_x,
                'y': button_y,
            }

            canvas.print(
                button_x,
                button_y,
                text=text.center(self.menu_width),
                fg=color.menu_text_inverse if text == self.button_highlight else color.menu_text,
                bg=color.white if text == self.button_highlight else None,
                alignment=CENTER,
            )

    def ev_keydown(
        self, event: events.KeyDown
    ) -> Optional[input_handlers.BaseEventHandler]:

        if event.sym == Key.UP:
            if not self.button_highlight:
                self.menu_i = 0
            else:
                self.menu_i = self.menu_i-1 if self.menu_i > 0 else len(self.button_names)-1
        elif event.sym == Key.DOWN:
            if not self.button_highlight:
                self.menu_i = 0
            else:
                self.menu_i = self.menu_i+1 if not self.menu_i == len(self.button_names)-1 else 0
        self.button_highlight = self.button_names[self.menu_i] if type(self.menu_i) == int else self.button_highlight

        if event.sym in input_handlers.CONFIRM_KEYS:
            return self.resolve_menu(event)

        if event.sym in (Key.Q, Key.ESCAPE):
            raise SystemExit()

        return None

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[input_handlers.ActionOrHandler]:
        """Left click confirms a selection."""

        for text in self.button_names:
            button_pt = Point(self.buttons[text]['x'], self.buttons[text]['y'])
            in_rect = is_mouse_in_rectangle(event, button_pt, self.menu_width, self.button_height)

            if in_rect:
                return self.resolve_menu(event)

    def ev_mousemotion(
        self, event: events.MouseMotion
    ) -> Optional[input_handlers.ActionOrHandler]:
        """Tracks mouse movement"""
        for i, text in enumerate(self.button_names):
            button_pt = Point(self.buttons[text]['x'], self.buttons[text]['y'])
            in_rect = is_mouse_in_rectangle(event, button_pt, self.menu_width, self.button_height)
            if in_rect:
                self.menu_i = i
                self.button_highlight = self.button_names[i]


class CharacterCreation(input_handlers.BaseEventHandler):
    TITLE = "What is your name?"
    MAX_CHARS = 16

    def on_init(self):
        self.player = create_player()  # a fresh player per visit (was one Player built at import and reused)
        g.start_text_input()

    def on_render(self, canvas: Canvas) -> None:
        from utilities import generate_name

        width = len(self.TITLE) + 4
        x = canvas.width // 2 - width // 2
        y = canvas.height // 2 - 4

        canvas.draw_frame(
            x,
            y,
            width=width,
            height=5,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        canvas.print(
            x=x  + 2, y=y + 2, text=f"{self.player.name}"
        )
        if len(self.player.name) < self.MAX_CHARS - 1:
            canvas.print(
                x=x + len(self.player.name) + 2, y=y + 2, text=f"_"
            )

    def ev_textinput(self, event: events.TextInput) -> Optional[input_handlers.BaseEventHandler]:
        name = self.player.name
        name += event.text
        if len(name) < self.MAX_CHARS:
            self.player.set_name(name)

    def ev_keydown(self, event: events.KeyDown) -> Optional[input_handlers.BaseEventHandler]:
        if event.sym == Key.RETURN:
            g.stop_text_input()
            game_handler = input_handlers.MainGameEventHandler(new_game(self.player))
            g.handlers = [game_handler]
            return game_handler
        elif event.sym == Key.BACKSPACE:
            name = self.player.name[:-1]
            self.player.set_name(name)
        elif event.sym == Key.ESCAPE:  # (not Q: it is a letter in a name)
            g.stop_text_input()
            return MainMenu()
            