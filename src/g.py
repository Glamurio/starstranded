"""Global module for all global variables"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from display import Display
    from input_handlers import BaseEventHandler
    from ui import Canvas

screen_width = 80
screen_height = 45
screen_width_offset = 10
screen_height_offset = 5
"""Cells of the logical screen; the map takes the screen minus these offsets (side panel / bottom panel)."""

handlers: List[BaseEventHandler] = []

display: Optional[Display] = None
canvas: Optional[Canvas] = None


def init(*, headless: bool = False, window_size=None) -> Display:
    """Create the window (hidden from nothing, but on the dummy video driver when `headless`), font, sprite atlas
    and the canvas the screens draw on. Safe to call again: the previous window is closed first."""
    global display, canvas
    import pygame

    import atlas
    import display as display_module
    import ui

    if display is not None:
        pygame.display.quit()
    atlas.reset_atlas()
    display = display_module.Display(headless=headless, window_size=window_size)
    assert (display_module.COLUMNS, display_module.ROWS) == (screen_width, screen_height)
    canvas = ui.Canvas(display.surface, ui.Font.load(), atlas.get_atlas())
    return display


def draw(handler: BaseEventHandler) -> None:
    """Draw `handler` onto the logical surface without presenting it."""
    assert canvas is not None, "g.init() must be called before drawing"
    canvas.clear()
    handler.on_render(canvas)


def render(handler: BaseEventHandler) -> None:
    """
    Global render function

    Expects a `handler: BaseEventHandler` to render, draws it and presents the window.
    """
    if canvas is None or display is None:
        return
    draw(handler)
    display.present()


def start_text_input() -> None:
    """Ask for text input events (name entry); a no-op when there is no window."""
    if display is not None:
        display.start_text_input()


def stop_text_input() -> None:
    if display is not None:
        display.stop_text_input()
