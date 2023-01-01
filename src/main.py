#!/usr/bin/env python3
import traceback

import tcod
import color

import exceptions
import input_handlers

import setup_game
import numpy as np # type: ignore

from typing import List


CHARMAP_URIZEN = np.arange(0xE000, 0xF8FF+1)
"""
Custom `Private Use Area` charmap for Urizen
"""

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
    screen_width = 80
    screen_height = 45

    tileset = tcod.tileset.load_tilesheet(
        "urizen_nogrid.png", 50, 50, CHARMAP_URIZEN
    )
    text_tileset = tcod.tileset.load_tilesheet(
        "Zesty_curses_24x24.png", 16, 16, tcod.tileset.CHARMAP_CP437
    )

    merge_tileset(tileset, text_tileset, tcod.tileset.CHARMAP_CP437)


    handler: input_handlers.BaseEventHandler = setup_game.MainMenu()

    root_console = tcod.Console(screen_width, screen_height, order="F")
    logical_size = (root_console.width * tileset.tile_width, root_console.height * tileset.tile_height)
    sdl_window = tcod.sdl.video.new_window(
        width=logical_size[0],
        height=logical_size[1],
        title="Starstranded",
        flags=tcod.lib.SDL_WINDOW_RESIZABLE,
    )
    sdl_renderer = tcod.sdl.render.new_renderer(sdl_window, target_textures=True)
    sdl_renderer.logical_size = logical_size
    atlas = tcod.render.SDLTilesetAtlas(sdl_renderer, tileset)
    console_render = tcod.render.SDLConsoleRender(atlas)
    
    try:
        while True:
            root_console.clear()
            handler.on_render(console=root_console)
            # tileset.remap(0xE001, 0, 9)
            sdl_renderer.draw_blend_mode = tcod.sdl.render.BlendMode.NONE
            sdl_renderer.copy(console_render.render(root_console))

            # sdl_renderer.draw_blend_mode = tcod.sdl.render.BlendMode.BLEND
            # sdl_renderer.copy(console_render2.render(console2))

            sdl_renderer.present()

            try:
                for event in tcod.event.wait():

                    # Manual handing of tile coordinates since context.present is skipped.
                    if isinstance(event, (tcod.event.MouseState, tcod.event.MouseMotion)):
                        event.tile = tcod.event.Point(event.pixel.x // tileset.tile_width, event.pixel.y // tileset.tile_height)
                    if isinstance(event, tcod.event.MouseMotion):
                        prev_tile = (
                            (event.pixel[0] - event.pixel_motion[0]) // tileset.tile_width,
                            (event.pixel[1] - event.pixel_motion[1]) // tileset.tile_height,
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