"""Text and UI drawing on a grid of 24x24 px cells.

`Font` wraps the CP437 "Zesty curses" sheet (16x16 glyphs of 24x24 px, white on transparent, so glyph
colour is a tint). `Canvas` draws onto a pygame surface using *cell* coordinates, with the handful of
operations the screens need: text (with alignment and background), frames, bars, sprites, cell
highlights and dimming. It deliberately mirrors the small subset of ``tcod.console.Console`` the game
used (``print``, ``draw_frame``, ``draw_rect``), which keeps the screen code readable.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import pygame

import atlas as atlas_module
from atlas import RGB, TILE

CELL = TILE
"""Pixel size of one grid cell (same as a sprite)."""

FONT_COLUMNS = 16
FONT_ROWS = 16

LEFT = 0
CENTER = 1
RIGHT = 2

WHITE: RGB = (255, 255, 255)
BLACK: RGB = (0, 0, 0)

_FRAME = {"tl": 0xDA, "tr": 0xBF, "bl": 0xC0, "br": 0xD9, "h": 0xC4, "v": 0xB3}


def cp437_index(character: str) -> int:
    """Index of `character` in the CP437 sheet ('?' for characters CP437 does not have)."""
    try:
        return character.encode("cp437")[0]
    except (UnicodeEncodeError, IndexError):
        return ord("?")


class Font:
    """CP437 bitmap font with tinted glyphs cached per (index, colour)."""

    def __init__(self, sheet: pygame.Surface):
        if pygame.display.get_surface() is not None:
            sheet = sheet.convert_alpha()
        self.sheet = sheet
        self.cell = sheet.get_width() // FONT_COLUMNS
        self._cache: Dict[Tuple[int, RGB], pygame.Surface] = {}

    @classmethod
    def load(cls, path: str = "Zesty_curses_24x24.png") -> "Font":
        return cls(atlas_module.load_alpha_sheet(path))

    def glyph(self, index: int, fg: RGB = WHITE) -> pygame.Surface:
        key = (index, tuple(fg))
        hit = self._cache.get(key)
        if hit is None:
            if len(self._cache) > 4000:
                self._cache.clear()
            cell = self.cell
            area = pygame.Rect((index % FONT_COLUMNS) * cell, (index // FONT_COLUMNS) * cell, cell, cell)
            hit = self.sheet.subsurface(area).copy()
            if tuple(fg) != WHITE:
                hit.fill((*fg, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self._cache[key] = hit
        return hit


class Canvas:
    """A grid of `columns` x `rows` cells drawn onto `surface`."""

    def __init__(self, surface: pygame.Surface, font: Font, sprites: Optional[atlas_module.SpriteAtlas] = None):
        self.surface = surface
        self.font = font
        self.sprites = sprites or atlas_module.get_atlas()
        self.width = surface.get_width() // CELL
        self.height = surface.get_height() // CELL
        self._overlays: Dict[tuple, pygame.Surface] = {}

    # ── geometry ───────────────────────────────────────────────────────────────────
    @staticmethod
    def cell_rect(x: int, y: int, width: int = 1, height: int = 1) -> pygame.Rect:
        return pygame.Rect(x * CELL, y * CELL, width * CELL, height * CELL)

    # ── primitives ─────────────────────────────────────────────────────────────────
    def clear(self, color: RGB = BLACK) -> None:
        self.surface.fill(color)

    def fill(self, x: int, y: int, width: int, height: int, color: RGB) -> None:
        self.surface.fill(color, self.cell_rect(x, y, width, height))

    draw_rect = fill  # tcod-style alias

    def sprite(self, x: int, y: int, sprite: int, tint: RGB = WHITE, flipped: bool = False) -> None:
        """Blit a sprite into cell (x, y)."""
        self.surface.blit(self.sprites.get(sprite, flipped, tint), (x * CELL, y * CELL))

    def highlight(self, x: int, y: int, color: RGB = WHITE, alpha: int = 110) -> None:
        """Wash cell (x, y) with a translucent colour (the sprite underneath stays visible)."""
        key = (tuple(color), alpha)
        overlay = self._overlays.get(key)
        if overlay is None:
            overlay = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            overlay.fill((*color, alpha))
            self._overlays[key] = overlay
        self.surface.blit(overlay, (x * CELL, y * CELL))

    def dim(self, divisor: int = 8) -> None:
        """Darken everything drawn so far (popups use this to push the screen behind them back)."""
        shade = max(0, 255 - 255 // divisor)
        veil = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, shade))
        self.surface.blit(veil, (0, 0))

    # ── text ───────────────────────────────────────────────────────────────────────
    def print(
        self,
        x: int,
        y: int,
        text: str,
        fg: RGB = WHITE,
        bg: Optional[RGB] = None,
        alignment: int = LEFT,
    ) -> None:
        """Print `text` starting at cell (x, y); '\\n' starts a new line.

        With `alignment=CENTER` x is the middle of each line, with `RIGHT` its last column.
        """
        for row, line in enumerate(text.split("\n")):
            self._print_line(x, y + row, line, fg, bg, alignment)

    def _print_line(self, x: int, y: int, line: str, fg: RGB, bg: Optional[RGB], alignment: int) -> None:
        if alignment == CENTER:
            x -= len(line) // 2
        elif alignment == RIGHT:
            x -= len(line) - 1
        if y < 0 or y >= self.height or not line:
            return
        if bg is not None:
            self.fill(x, y, len(line), 1, bg)
        blit = self.surface.blit
        glyph = self.font.glyph
        pixel_y = y * CELL
        for i, character in enumerate(line):
            column = x + i
            if character == " " or column < 0 or column >= self.width:
                continue
            blit(glyph(cp437_index(character), fg), (column * CELL, pixel_y))

    def text_width(self, text: str) -> int:
        return max((len(line) for line in text.split("\n")), default=0)

    # ── composites ─────────────────────────────────────────────────────────────────
    def draw_frame(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        title: Optional[str] = None,
        clear: bool = True,
        fg: RGB = WHITE,
        bg: RGB = BLACK,
    ) -> None:
        """A single-line box (`width` x `height` cells) with an optional inverted title on the top edge."""
        if clear:
            self.fill(x, y, width, height, bg)
        put = lambda cx, cy, code: self.surface.blit(self.font.glyph(code, fg), (cx * CELL, cy * CELL))  # noqa: E731
        for cx in range(x + 1, x + width - 1):
            put(cx, y, _FRAME["h"])
            put(cx, y + height - 1, _FRAME["h"])
        for cy in range(y + 1, y + height - 1):
            put(x, cy, _FRAME["v"])
            put(x + width - 1, cy, _FRAME["v"])
        put(x, y, _FRAME["tl"])
        put(x + width - 1, y, _FRAME["tr"])
        put(x, y + height - 1, _FRAME["bl"])
        put(x + width - 1, y + height - 1, _FRAME["br"])
        if title:
            title = title[: max(0, width - 2)]
            self._print_line(x + width // 2, y, title, bg, fg, CENTER)

    def draw_bar(
        self,
        x: int,
        y: int,
        total_width: int,
        current: int,
        maximum: int,
        bg_full: RGB,
        bg_empty: RGB,
        fg: RGB,
        label: str,
    ) -> None:
        """A one-row bar filled in proportion to `current / maximum`, with `label: cur/max` over it."""
        filled = int(float(current) / maximum * total_width) if maximum else 0
        self.fill(x, y, total_width, 1, bg_empty)
        if filled > 0:
            self.fill(x, y, min(filled, total_width), 1, bg_full)
        self.print(x + 1, y, f"{label}: {current}/{maximum}", fg=fg)

    def blit_image(self, image: pygame.Surface, *, cover: bool = True) -> None:
        """Draw `image` over the whole canvas, scaled up to cover it (cropping the overflow evenly)."""
        target_w, target_h = self.surface.get_size()
        image_w, image_h = image.get_size()
        scale = max(target_w / image_w, target_h / image_h) if cover else min(target_w / image_w, target_h / image_h)
        size = (round(image_w * scale), round(image_h * scale))
        scaled = pygame.transform.scale(image, size)
        self.surface.blit(scaled, ((target_w - size[0]) // 2, (target_h - size[1]) // 2))
