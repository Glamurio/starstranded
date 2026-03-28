#!/usr/bin/env python3
from __future__ import annotations

import traceback

import g
from tcod import libtcodpy
import color
import copy

import exceptions

from typing import List, TYPE_CHECKING, TypeVar


if TYPE_CHECKING:
    import input_handlers

def save_game(handler: input_handlers.BaseEventHandler, filename: str) -> None:
    """If the current event handler has an active Engine then save it."""
    import input_handlers
    if isinstance(handler, input_handlers.EventHandler):
        handler.engine.save_as(filename)
        print("Game saved.")

def merge_tileset(tileset: libtcodpy.tcod.tileset.Tileset, incoming: libtcodpy.tcod.tileset.Tileset, charmap: List[int]):
    """Overwrite tiles for `charmap` in `tileset` with those from `incoming`."""
    for i in charmap:
        if i not in incoming:
            continue
        tile = incoming[i]
        if not tile.any():
            continue
        tileset[i] = tile

def convert_coords(event: libtcodpy.tcod.event.Event) -> libtcodpy.tcod.event.Event:
    """Return an event with mouse coordinates converted into tile coordinates."""
    event_tile = copy.copy(event)
    if isinstance(event_tile, (libtcodpy.tcod.event.MouseState, libtcodpy.tcod.event.MouseMotion, libtcodpy.tcod.event.MouseButtonDown)):
        event_tile.position = libtcodpy.tcod.event.Point(
            int(event.position.x) // g.global_tileset.tile_width,
            int(event.position.y) // g.global_tileset.tile_height,
        )
    if isinstance(event, libtcodpy.tcod.event.MouseMotion):
        prev_tile = (
            (int(event.position[0]) - int(event.motion[0])) // g.global_tileset.tile_width,
            (int(event.position[1]) - int(event.motion[1])) // g.global_tileset.tile_height,
        )
        event_tile.motion = libtcodpy.tcod.event.Point(
            int(event_tile.position[0] - prev_tile[0]),
            int(event_tile.position[1] - prev_tile[1]),
        )
    return event_tile

def main() -> None:
    import setup_game
    
    text_tileset = libtcodpy.tcod.tileset.load_tilesheet(
        "Zesty_curses_24x24.png", 16, 16, libtcodpy.tcod.tileset.CHARMAP_CP437
    )

    merge_tileset(g.global_tileset, text_tileset, libtcodpy.tcod.tileset.CHARMAP_CP437)
    handler: input_handlers.BaseEventHandler = setup_game.MainMenu()

    try:
        while True:
            g.render(handler)

            try:
                for event in libtcodpy.tcod.event.get():

                    # Manual handing of tile coordinates since context.present is skipped.
                    if isinstance(event, (
                            libtcodpy.tcod.event.MouseState,
                            libtcodpy.tcod.event.MouseMotion,
                            libtcodpy.tcod.event.MouseButtonDown
                        )):
                        event = convert_coords(event)
                    handler = handler.handle_events(event)
                
            except Exception:  # Handle exceptions in game.
                traceback.print_exc()  # Print error to stderr.
                import input_handlers
                # Then print the error to the message log.
                if isinstance(handler, input_handlers.EventHandler):
                    handler.engine.message_log.add_message(
                        traceback.format_exc(), color.error
                    )
    except exceptions.QuitWithoutSaving:
        raise
    except SystemExit:  # Save and quit.
        save_game(handler, "savegame.sav")
        raise
    except BaseException:  # Save on any other unexpected exception.
        save_game(handler, "savegame.sav")
        raise


if __name__ == "__main__":
    main()