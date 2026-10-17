#!/usr/bin/env python3
from __future__ import annotations

import traceback

import g
import color

import exceptions

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import input_handlers

FPS = 60

def save_game(handler: input_handlers.BaseEventHandler, filename: str) -> None:
    """If the current event handler has an active Engine then save it."""
    import input_handlers
    if isinstance(handler, input_handlers.EventHandler):
        handler.engine.save_as(filename)
        print("Game saved.")

def run(handler: input_handlers.BaseEventHandler, display) -> None:
    """The main loop: handle input, redraw only when something happened, cap at `FPS`.

    Exceptions raised while handling an event are printed and shown in the message log. Quitting
    (SystemExit) and any other unexpected exception save the game first, then propagate.
    """
    import pygame
    import input_handlers

    clock = pygame.time.Clock()
    dirty = True
    try:
        while True:
            if dirty:
                g.render(handler)
                dirty = False

            try:
                for event in display.poll():
                    dirty = True
                    handler = handler.handle_events(event)
            except Exception:  # Handle exceptions in game.
                traceback.print_exc()  # Print error to stderr.
                dirty = True
                # Then print the error to the message log.
                if isinstance(handler, input_handlers.EventHandler):
                    handler.engine.message_log.add_message(
                        traceback.format_exc(), color.error
                    )

            clock.tick(FPS)
    except exceptions.QuitWithoutSaving:
        raise
    except SystemExit:  # Save and quit.
        save_game(handler, "savegame")
        raise
    except BaseException:  # Save on any other unexpected exception.
        save_game(handler, "savegame")
        raise

def main() -> None:
    import setup_game

    display = g.init()
    run(setup_game.MainMenu(), display)


if __name__ == "__main__":
    main()
