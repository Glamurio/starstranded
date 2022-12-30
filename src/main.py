#!/usr/bin/env python3
import traceback

import tcod
import color

import exceptions
import input_handlers

import setup_game
import numpy as np # type: ignore


CHARMAP_URIZEN = np.arange(0xE000, 0xF8FF+1)
"""
Custom `Private Use Area` charmap for Urizen
"""

def save_game(handler: input_handlers.BaseEventHandler, filename: str) -> None:
    """If the current event handler has an active Engine then save it."""
    if isinstance(handler, input_handlers.EventHandler):
        handler.engine.save_as(filename)
        print("Game saved.")

def main() -> None:
    screen_width = 80
    screen_height = 45

    # tileset = tcod.tileset.load_tilesheet(
    #     "dejavu10x10_gs_tc.png", 32, 8, tcod.tileset.CHARMAP_TCOD
    # )
    # tileset = tcod.tileset.load_tilesheet(
    #     "urizen_nogrid.png", 50, 50, CHARMAP_URIZEN
    # )
    tileset = tcod.tileset.load_tilesheet(
        "Zesty_curses_24x24.png", 16, 16, tcod.tileset.CHARMAP_CP437
    )

    handler: input_handlers.BaseEventHandler = setup_game.MainMenu()

    # root_console = tcod.Console(screen_width, screen_height)
    # sdl_window = tcod.sdl.video.new_window(
    #     root_console.width * tileset.tile_width,
    #     root_console.height * tileset.tile_height,
    #     flags=tcod.lib.SDL_WINDOW_RESIZABLE,
    # )
    # sdl_renderer = tcod.sdl.render.new_renderer(sdl_window, target_textures=True)
    # atlas = tcod.render.SDLTilesetAtlas(sdl_renderer, tileset)
    # console_render = tcod.render.SDLConsoleRender(atlas)
    
    with tcod.context.new(
        columns=screen_width,
        rows=screen_height,
        tileset=tileset,
        title="Starstranded",
        vsync=True,
    ) as context:
        root_console = tcod.Console(screen_width, screen_height, order="F")
        try:
            while True:
                root_console.clear()
                handler.on_render(console=root_console)
                # sdl_renderer.copy(console_render.render(root_console))
                # sdl_renderer.present()
                
                context.present(root_console)

                try:
                    for event in tcod.event.wait():
                        context.convert_event(event)
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