#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import traceback

# Assets, data/namegen and the savegame folder are resolved relative to src/, so work from there
# no matter where the game was started from.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    import pygame  # noqa: F401  (pygame-ce provides the `pygame` module)
except ModuleNotFoundError:
    sys.exit(
        "StarStranded needs pygame-ce (not the plain 'pygame' package).\n"
        "Install the dependencies with:  py -m pip install -r requirements.txt\n"
        "If plain pygame is installed, remove it first:  py -m pip uninstall pygame"
    )

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

def run(handler: input_handlers.BaseEventHandler, session) -> None:
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
                session.render(handler)
                dirty = False

            try:
                for event in session.display.poll():
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

    from session import Session

    session = Session.create()
    run(setup_game.MainMenu(session), session)


if __name__ == "__main__":
    main()
