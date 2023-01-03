#!/usr/bin/env python3
import traceback

import tcod
import color

import exceptions
import input_handlers

import setup_game
import g
from typing import List

def save_game(handler: input_handlers.BaseEventHandler, filename: str) -> None:
    """If the current event handler has an active Engine then save it."""
    if isinstance(handler, input_handlers.EventHandler):
        handler.engine.save_as(filename)
        print("Game saved.")

def merge_tileset(tileset: tcod.tileset.Tileset, incoming: tcod.tileset.Tileset, charmap: List[int]):
    """Overwrite tiles for `charmap` in `tileset` with those from `incoming`."""
    for i in charmap:
        if i not in incoming:
            continue
        tile = incoming.get_tile(i)
        if not tile.any():
            continue
        tileset.set_tile(i, tile)

def main() -> None:

    text_tileset = tcod.tileset.load_tilesheet(
        "Zesty_curses_24x24.png", 16, 16, tcod.tileset.CHARMAP_CP437
    )

    merge_tileset(g.global_tileset, text_tileset, tcod.tileset.CHARMAP_CP437)
    handler: input_handlers.BaseEventHandler = setup_game.MainMenu()
    
    try:
        while True:

            g.root_console.clear()
            handler.on_render(console=g.root_console)

            g.sdl_renderer.draw_blend_mode = tcod.sdl.render.BlendMode.NONE
            g.sdl_renderer.copy(g.console_render.render(g.root_console))

            # sdl_renderer.draw_blend_mode = tcod.sdl.render.BlendMode.BLEND
            # sdl_renderer.copy(console_render2.render(console2))

            g.sdl_renderer.present()

            try:
                for event in tcod.event.wait():

                    # Manual handing of tile coordinates since context.present is skipped.
                    if isinstance(event, (tcod.event.MouseState, tcod.event.MouseMotion)):
                        event.tile = tcod.event.Point(event.pixel.x // g.global_tileset.tile_width, event.pixel.y // g.global_tileset.tile_height)
                    if isinstance(event, tcod.event.MouseMotion):
                        prev_tile = (
                            (event.pixel[0] - event.pixel_motion[0]) // g.global_tileset.tile_width,
                            (event.pixel[1] - event.pixel_motion[1]) // g.global_tileset.tile_height,
                        )
                        event.tile_motion = tcod.event.Point(event.tile[0] - prev_tile[0], event.tile[1] - prev_tile[1])
                    handler = handler.handle_events(event)
                
            except Exception:  # Handle exceptions in game.
                traceback.print_exc()  # Print error to stderr.
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