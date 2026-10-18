"""Handle the loading and initialization of game sessions."""
from __future__ import annotations

import exceptions
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

def new_game(player: Unit, session=None) -> Engine:
    """Return a brand new game session as an Engine instance."""
    from world import GameWorld

    engine = Engine(player=player, session=session)
    engine.game_world = GameWorld(engine=engine)  # the game seed is drawn from `random`
    engine.game_world.start()  # the surface: a chunked world around the start in chunk (0, 0)
    
    engine.message_log.add_message(
        f"Hello and welcome, {player.name}, to yet another dungeon!", color.welcome_text
    )

    return engine

SAVE_PATH = "savegame"
"""The save directory (relative to the working directory, i.e. src/)."""


def load_game(path: str = SAVE_PATH, session=None) -> Engine:
    """Load a game saved with `Engine.save_as` (see `savegame.load_game`)."""
    import savegame
    return savegame.load_game(path, session)


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
            return CharacterCreation(self.session)
        elif self.button_highlight == 'Continue':
            # Continue Game
            try:
                return input_handlers.MainGameEventHandler(load_game(SAVE_PATH, self.session))
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
        self.session.start_text_input()

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
            self.session.stop_text_input()
            game_handler = input_handlers.MainGameEventHandler(new_game(self.player, self.session))
            self.session.reset(game_handler)
            return game_handler
        elif event.sym == Key.BACKSPACE:
            name = self.player.name[:-1]
            self.player.set_name(name)
        elif event.sym == Key.ESCAPE:  # (not Q: it is a letter in a name)
            self.session.stop_text_input()
            return MainMenu(self.session)
            