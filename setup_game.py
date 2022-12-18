"""Handle the loading and initialization of game sessions."""
from __future__ import annotations
from asyncio import exceptions

import copy
import lzma
import pickle
import traceback
from typing import Optional

import tcod

import color
from engine import Engine
from entity import Actor
import entity_factories
from world import GameWorld
import input_handlers


# Load the background image and remove the alpha channel.
background_image = tcod.image.load("menu_background.png")[:, :, :3]

def create_player() -> Actor:
    player = copy.deepcopy(entity_factories.player)

    dagger = copy.deepcopy(entity_factories.dagger)
    leather_armor = copy.deepcopy(entity_factories.leather_armor)

    dagger.parent = player.inventory
    leather_armor.parent = player.inventory

    player.inventory.items.append(dagger)
    player.equipment.toggle_equip(dagger, add_message=False)

    player.inventory.items.append(leather_armor)
    player.equipment.toggle_equip(leather_armor, add_message=False)

    return player

def new_game(player: Actor) -> Engine:
    """Return a brand new game session as an Engine instance."""
    map_width = 30
    map_height = 30

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

    def on_render(self, console: tcod.Console) -> None:
        """Render the main menu on a background image."""
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

        menu_width = 24
        for i, text in enumerate(
            ["[N] Play a new game", "[C] Continue last game", "[Q] Quit"]
        ):
            console.print(
                console.width // 2,
                console.height // 2 - 2 + i,
                text.ljust(menu_width),
                fg=color.menu_text,
                bg=color.black,
                alignment=tcod.CENTER,
                bg_blend=tcod.BKGND_ALPHA(64),
            )

    def ev_keydown(
        self, event: tcod.event.KeyDown
    ) -> Optional[input_handlers.BaseEventHandler]:
        if event.sym in (tcod.event.K_q, tcod.event.K_ESCAPE):
            raise SystemExit()
        elif event.sym == tcod.event.K_c:
            try:
                return input_handlers.MainGameEventHandler(load_game("savegame.sav"))
            except FileNotFoundError:
                return input_handlers.PopupMessage(self, "No saved game to load.")
            except Exception as exc:
                traceback.print_exc()  # Print to stderr.
                return input_handlers.PopupMessage(self, f"Failed to load save:\n{exc}")
        elif event.sym == tcod.event.K_n:
            return CharacterCreation()

        return None

class CharacterCreation(input_handlers.BaseEventHandler):
    TITLE = "What is your name?"
    PLAYER = create_player()
    MAX_CHARS = 16
    
    def on_render(self, console: tcod.Console) -> None:

        width = len(self.TITLE) + 4
        x = 20
        y = 40

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=20,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        console.print(
            x=x + 2, y=y + 1, string=f"Name: "
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
            