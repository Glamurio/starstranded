"""The UI session: the window, the canvas the screens draw on, and the stack of event handlers.

Replaces the old module of globals. A `Session` is created once by `main` (`Session.create`) and handed to the
handlers that start a game (`setup_game.MainMenu(session)`); every `Engine` keeps a reference (`engine.session`) so
engine handlers, and items that open a placement screen, reach the same stack. Engines built without one (tests,
tools) get a detached session: a stack with no window, where drawing does nothing.
"""
from __future__ import annotations

from typing import Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from display import Display
    from input_handlers import BaseEventHandler
    from ui import Canvas


class Session:
    def __init__(self, display: Optional[Display] = None, canvas: Optional[Canvas] = None) -> None:
        self.display = display
        self.canvas = canvas
        self.handlers: List[BaseEventHandler] = []

    @classmethod
    def create(cls, *, headless: bool = False, window_size=None) -> "Session":
        """Open the window (on SDL's dummy video driver when `headless`), load the font and sprite atlas."""
        import atlas
        import display as display_module
        import layout
        import ui

        atlas.reset_atlas()
        display = display_module.Display(headless=headless, window_size=window_size)
        assert (display_module.COLUMNS, display_module.ROWS) == (layout.SCREEN_WIDTH, layout.SCREEN_HEIGHT)
        return cls(display, ui.Canvas(display.surface, ui.Font.load(), atlas.get_atlas()))

    def close(self) -> None:
        if self.display is not None:
            import pygame
            pygame.display.quit()
            self.display = self.canvas = None

    # ── handler stack ──────────────────────────────────────────────────────────────
    def push(self, handler: BaseEventHandler) -> None:
        self.handlers.append(handler)

    def reset(self, handler: BaseEventHandler) -> None:
        """Make `handler` the only one on the stack."""
        self.handlers = [handler]

    # ── drawing ────────────────────────────────────────────────────────────────────
    def draw(self, handler: BaseEventHandler) -> None:
        """Draw `handler` onto the logical surface without presenting it (no-op when detached)."""
        if self.canvas is None:
            return
        self.canvas.clear()
        handler.on_render(self.canvas)

    def render(self, handler: BaseEventHandler) -> None:
        """Draw `handler` and present the window."""
        if self.canvas is None or self.display is None:
            return
        self.draw(handler)
        self.display.present()

    def start_text_input(self) -> None:
        if self.display is not None:
            self.display.start_text_input()

    def stop_text_input(self) -> None:
        if self.display is not None:
            self.display.stop_text_input()


detached: Callable[[], Session] = Session
"""How an `Engine` without an explicit session gets one (tests replace this with a shared window)."""
