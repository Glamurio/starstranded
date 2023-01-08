"""Handle the loading and initialization of game sessions."""
from __future__ import annotations
from asyncio import exceptions

import g
import lzma
import pickle
import traceback
from typing import TYPE_CHECKING, Optional

import tcod

import color
from engine import Engine

import input_handlers

from utilities import is_mouse_in_rectangle

if TYPE_CHECKING:
    from components.unit import Unit

# Load the background image and remove the alpha channel.
background_image = tcod.image.load("menu_background.png")[:, :, :3]

def create_player() -> Unit:
    from components.unit import Player
    import components.equippable as equip

    player = Player()
    dagger = equip.Dagger(player.inventory)
    leather_armor = equip.LeatherArmor(player.inventory)

    player.inventory.add(dagger)
    player.equipment.toggle_equip(dagger, add_message=False)

    player.inventory.add(leather_armor)
    player.equipment.toggle_equip(leather_armor, add_message=False)

    return player

def new_game(player: Unit) -> Engine:
    """Return a brand new game session as an Engine instance."""
    from world import GameWorld
    
    map_width = 70
    map_height = 40

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
    """Load an Engine instance from a file."""
    with open(filename, "rb") as f:
        engine = pickle.loads(lzma.decompress(f.read()))
    assert isinstance(engine, Engine)
    return engine

class MainMenu(input_handlers.BaseEventHandler):
    """Handle the main menu rendering and input."""

    console_height: int
    console_width: int
    menu_width = 12
    menu_i: int = 0

    buttons = {}
    button_height = 2
    button_names = ["New Game", "Continue", "Quit"]
    button_highlight = button_names[menu_i]

    def resolve_menu(self, event: tcod.event):
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

    def on_render(self, console: tcod.Console) -> None:
        """Render the main menu on a background image."""
        self.console_height = console.height
        self.console_width = console.width
        console.draw_semigraphics(background_image, 0, 0)

        console.print(
            console.width // 2,
            console.height // 2 - 4,
            "Starstranded",
            fg=color.menu_title,
            alignment=tcod.CENTER,
        )
        console.print(
            console.width // 2,
            console.height - 2,
            "By Ryou",
            fg=color.menu_title,
            alignment=tcod.CENTER,
        )

        # Iterate over menu buttons, save their position for highlighting
        for i, text in enumerate(self.button_names):

            button_x = console.width // 2
            button_y = console.height // 2 - 2 + (i*2)

            self.buttons[text]: dict = {
                'x': button_x,
                'y': button_y,
            }
        
            console.print(
                button_x,
                button_y,
                text.center(self.menu_width),
                fg=color.menu_text_inverse if text == self.button_highlight else color.menu_text,
                bg=color.white if text == self.button_highlight else color.black,
                alignment=tcod.CENTER,
                bg_blend=tcod.BKGND_ALPHA(64),
            )

    def ev_keydown(
        self, event: tcod.event.KeyDown
    ) -> Optional[input_handlers.BaseEventHandler]:

        if event.sym == tcod.event.K_UP:
            if not self.button_highlight:
                self.menu_i = 0
            else:
                self.menu_i = self.menu_i-1 if self.menu_i > 0 else len(self.button_names)-1
        elif event.sym == tcod.event.K_DOWN:
            if not self.button_highlight:
                self.menu_i = 0
            else:
                self.menu_i = self.menu_i+1 if not self.menu_i == len(self.button_names)-1 else 0
        self.button_highlight = self.button_names[self.menu_i] if type(self.menu_i) == int else self.button_highlight

        if event.sym in input_handlers.CONFIRM_KEYS:
            return self.resolve_menu(event)

        if event.sym in (tcod.event.K_q, tcod.event.K_ESCAPE):
            raise SystemExit()

        return None

    def ev_mousebuttondown(
        self, event: tcod.event.MouseButtonDown
    ) -> Optional[input_handlers.ActionOrHandler]:
        """Left click confirms a selection."""

        for text in self.button_names:
            button_pt = tcod.event.Point(self.buttons[text]['x'], self.buttons[text]['y'])
            in_rect = is_mouse_in_rectangle(event, button_pt, self.menu_width, self.button_height)

            if in_rect:
                return self.resolve_menu(event)

    def ev_mousemotion(
        self, event: tcod.event.MouseMotion
    ) -> Optional[input_handlers.ActionOrHandler]:
        """Tracks mouse movement"""
        for i, text in enumerate(self.button_names):
            button_pt = tcod.event.Point(self.buttons[text]['x'], self.buttons[text]['y'])
            in_rect = is_mouse_in_rectangle(event, button_pt, self.menu_width, self.button_height)
            if in_rect:
                self.menu_i = i
                self.button_highlight = self.button_names[i]


class CharacterCreation(input_handlers.BaseEventHandler):
    TITLE = "What is your name?"
    PLAYER = create_player()
    MAX_CHARS = 16
    
    def on_render(self, console: tcod.Console) -> None:
        from utilities import generate_name

        width = len(self.TITLE) + 4
        x = console.width // 2 - width // 2
        y = console.height // 2 - 4

        console.draw_frame(
            x,
            y,
            width=width,
            height=5,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        console.print(
            x=x  + 2, y=y + 2, string=f"{self.PLAYER.name}"
        )
        if len(self.PLAYER.name) < self.MAX_CHARS - 1:
            console.print(
                x=x + len(self.PLAYER.name) + 2, y=y + 2, string=f"_"
            )

    def ev_textinput(self, event: tcod.event.TextInput) -> Optional[input_handlers.BaseEventHandler]:
        name = self.PLAYER.name
        name += event.text
        if len(name) < self.MAX_CHARS:
            self.PLAYER.set_name(name)

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[input_handlers.BaseEventHandler]:
        if event.sym == tcod.event.K_RETURN:
            return input_handlers.MainGameEventHandler(new_game(self.PLAYER))
        elif event.sym == tcod.event.K_BACKSPACE:
            name = self.PLAYER.name[:-1]
            self.PLAYER.set_name(name)
        elif event.sym in (tcod.event.K_q, tcod.event.K_ESCAPE):
            return MainMenu()
            