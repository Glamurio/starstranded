"""The window: a fixed logical surface presented scaled and letterboxed.

All drawing happens on `Display.surface` (80x45 cells of 24 px = 1920x1080). `present()` scales it to
the window by the largest integer factor that fits (nearest-neighbour, so pixel art stays crisp), or
smoothly when the window is smaller than the logical size, centres it, and fills the bars black.
`to_cell()` converts mouse pixels back into grid cells through the same transform.
"""
from __future__ import annotations

import os
from typing import Iterator, Optional, Tuple

import pygame

import events
from atlas import TILE

COLUMNS = 80
ROWS = 45
LOGICAL_SIZE = (COLUMNS * TILE, ROWS * TILE)


def fit(window_size: Tuple[int, int], logical_size: Tuple[int, int] = LOGICAL_SIZE) -> Tuple[Tuple[int, int], Tuple[int, int], float]:
    """`(size, offset, scale)` of the logical surface inside a window of `window_size`.

    Integer scale when the window is at least as big as the logical surface, fractional below that.
    """
    window_w, window_h = window_size
    logical_w, logical_h = logical_size
    scale = min(window_w / logical_w, window_h / logical_h)
    if scale >= 1:
        scale = float(int(scale))
    scale = max(scale, 1 / max(logical_w, logical_h))
    size = (max(1, round(logical_w * scale)), max(1, round(logical_h * scale)))
    offset = ((window_w - size[0]) // 2, (window_h - size[1]) // 2)
    return size, offset, scale


class Display:
    def __init__(self, *, title: str = "Starstranded", headless: bool = False, window_size: Optional[Tuple[int, int]] = None):
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")      # (tabbing out of the game must not minimise it)
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption(title)
        self.window = pygame.display.set_mode(window_size or self._initial_window_size(), pygame.RESIZABLE)
        self.borderless = False
        self.surface = pygame.Surface(LOGICAL_SIZE).convert()
        self.cursor_cell: Optional[events.Point] = None
        self.frames_presented = 0

    def set_borderless(self, on: bool) -> None:
        """A borderless window over the whole desktop (or back to the ordinary resizable window)."""
        try:
            if on:
                size = pygame.display.get_desktop_sizes()[0]
                self.window = pygame.display.set_mode(size, pygame.NOFRAME)
            else:
                self.window = pygame.display.set_mode(self._initial_window_size(), pygame.RESIZABLE)
            self.borderless = on
        except pygame.error:     # e.g. the headless driver: the window stays as it is
            pass

    @staticmethod
    def _initial_window_size() -> Tuple[int, int]:
        """The logical size, shrunk (keeping the aspect ratio) to fit 90 % of the desktop."""
        try:
            desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
        except Exception:
            return LOGICAL_SIZE
        scale = min(1.0, 0.9 * desktop_w / LOGICAL_SIZE[0], 0.9 * desktop_h / LOGICAL_SIZE[1])
        return (round(LOGICAL_SIZE[0] * scale), round(LOGICAL_SIZE[1] * scale))

    # ── presenting ─────────────────────────────────────────────────────────────────
    @property
    def window_size(self) -> Tuple[int, int]:
        return pygame.display.get_surface().get_size()

    def layout(self) -> Tuple[Tuple[int, int], Tuple[int, int], float]:
        return fit(self.window_size)

    def present(self) -> None:
        window = pygame.display.get_surface()
        size, offset, scale = fit(window.get_size())
        window.fill((0, 0, 0))
        if size == LOGICAL_SIZE:
            window.blit(self.surface, offset)
        elif scale >= 1:
            window.blit(pygame.transform.scale(self.surface, size), offset)
        else:
            window.blit(pygame.transform.smoothscale(self.surface, size), offset)
        pygame.display.flip()
        self.frames_presented += 1

    # ── coordinates ────────────────────────────────────────────────────────────────
    def to_logical(self, pixel: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Window pixel -> logical pixel, or None when it lies in the letterbox bars."""
        size, offset, scale = self.layout()
        x = pixel[0] - offset[0]
        y = pixel[1] - offset[1]
        if not (0 <= x < size[0] and 0 <= y < size[1]):
            return None
        return min(LOGICAL_SIZE[0] - 1, int(x / scale)), min(LOGICAL_SIZE[1] - 1, int(y / scale))

    def to_cell(self, pixel: Tuple[int, int]) -> Optional[events.Point]:
        logical = self.to_logical(pixel)
        if logical is None:
            return None
        return events.Point(logical[0] // TILE, logical[1] // TILE)

    # ── events ─────────────────────────────────────────────────────────────────────
    def poll(self) -> Iterator[events.Event]:
        """Pending input as internal events (ignored pygame events are dropped)."""
        for raw in pygame.event.get():
            event = events.translate(raw, self.to_cell, self.cursor_cell)
            if event is None:
                continue
            if isinstance(event, (events.MouseMotion, events.MouseButtonDown)):
                self.cursor_cell = event.position
            yield event

    # ── text input / screenshots ───────────────────────────────────────────────────
    @staticmethod
    def start_text_input() -> None:
        pygame.key.start_text_input()

    @staticmethod
    def stop_text_input() -> None:
        pygame.key.stop_text_input()

    def save_screenshot(self, path: str) -> None:
        """Write the logical surface (not the scaled window) as a PNG."""
        pygame.image.save(self.surface, path)
