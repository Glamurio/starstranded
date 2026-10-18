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
    import screens
    if isinstance(handler, (input_handlers.GameOverEventHandler, screens.EndingHandler)):
        return   # a finished run is never saved (a crash on the death screen must not bring the dead back)
    if isinstance(handler, input_handlers.EventHandler):
        handler.engine.save_as(filename)
        print("Game saved.")

def recover(handler, session):
    """After an unexpected error: a handler that is safe to keep playing with (the game itself, or the main menu)."""
    import input_handlers
    import setup_game
    engine = getattr(handler, "engine", None)
    if engine is not None:
        try:
            if engine.player.is_alive:
                safe = input_handlers.MainGameEventHandler(engine)
                session.reset(safe)
                return safe
        except Exception:
            traceback.print_exc()
    safe = setup_game.MainMenu(session)
    session.reset(safe)
    return safe


def expand_click(handler, session, event):
    """Clicks on window tabs and `[key] action` hints, and the mouse wheel, become the key presses they stand for."""
    import input_handlers
    import widgets
    if isinstance(handler, (input_handlers.MainGameEventHandler, input_handlers.SelectIndexHandler)) and getattr(event, "type", "") == "mousewheel":
        return []   # the map has no use for the wheel
    if getattr(event, "type", "") not in ("mousebuttondown", "mousewheel"):
        return [event]
    return widgets.expand_click(handler, getattr(session, "canvas", None), event)


def process(handler, event, session):
    """Feed one event to `handler` and return the handler to use next. Errors never escape: an `Impossible` is a message,
    anything else is logged (stderr and the message log) and the game falls back to a safe screen."""
    import input_handlers
    try:
        for event in expand_click(handler, session, event):
            handler = handler.handle_events(event)
        return handler
    except (exceptions.QuitWithoutSaving, SystemExit):
        raise
    except exceptions.Impossible as exc:
        engine = getattr(handler, "engine", None)
        if engine is not None:
            engine.message_log.add_message(exc.args[0] if exc.args else "You cannot do that.", color.impossible)
        return handler
    except Exception as exc:
        traceback.print_exc()
        engine = getattr(handler, "engine", None)
        if engine is not None:
            engine.message_log.add_message(f"Something went wrong ({type(exc).__name__}: {exc}); carrying on.", color.error)
        return recover(handler, session)


def render(handler, session):
    """Draw `handler`; if drawing fails, log it and fall back to a screen that can be drawn. Returns the handler in use."""
    try:
        session.render(handler)
        return handler
    except Exception:
        traceback.print_exc()
        handler = recover(handler, session)
        try:
            session.render(handler)
        except Exception:
            traceback.print_exc()
        return handler


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
                handler = render(handler, session)
                dirty = False

            for event in session.display.poll():
                dirty = True
                handler = process(handler, event, session)

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
    import settings
    settings.apply(settings.load(), session)
    run(setup_game.MainMenu(session), session)


if __name__ == "__main__":
    main()
