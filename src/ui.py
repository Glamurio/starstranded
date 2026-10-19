"""Text and UI drawing on a grid of 24x24 px cells.

`Font` wraps the CP437 "Zesty curses" sheet (16x16 glyphs of 24x24 px, white on transparent, so glyph
colour is a tint). `Canvas` draws onto a pygame surface using *cell* coordinates, with the handful of
operations the screens need: text (with alignment and background), frames, bars, sprites, cell
highlights and dimming. It deliberately mirrors the small subset of ``tcod.console.Console`` the game
used (``print``, ``draw_frame``, ``draw_rect``), which keeps the screen code readable.
"""
from __future__ import annotations

from dataclasses import dataclass
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

class Theme:
    """The window look. The colours below are the *active* palette; `Theme.apply(name)` swaps in one of `PALETTES`
    (chosen in Settings). The default, "Ion", is a cold sci-fi look: near-black navy glass, electric-cyan borders and
    hot-orange accents."""
    BG = (8, 12, 24)
    PANEL = (14, 22, 40)
    BORDER = (60, 200, 235)
    BORDER_DIM = (28, 84, 120)
    ORNAMENT = (255, 140, 50)
    TEXT = (200, 224, 240)
    DIM = (110, 140, 168)
    TITLE = (120, 235, 255)
    KEY = (255, 170, 70)
    HILITE = (22, 72, 110)
    HILITE_TEXT = (255, 255, 255)
    GOOD = (90, 225, 150)
    BAD = (255, 90, 100)
    WARN = (255, 195, 70)
    HP = (225, 70, 80)
    HUNGER = (240, 160, 50)
    THIRST = (70, 165, 255)
    BAR_EMPTY = (26, 36, 56)

    NAME = "ion"

    @classmethod
    def apply(cls, name: str) -> str:
        """Make palette `name` the active one (unknown names fall back to the default); returns the name used."""
        palette = PALETTES.get(name) or PALETTES[DEFAULT_THEME]
        for key, value in palette.colors.items():
            setattr(cls, key, value)
        cls.NAME = name if name in PALETTES else DEFAULT_THEME
        return cls.NAME


@dataclass(frozen=True)
class Palette:
    label: str
    colors: dict


def _palette(label, **colors):
    return Palette(label, dict(colors))


PALETTES = {
    "ion": _palette("Ion (cyan)", BG=(8, 12, 24), PANEL=(14, 22, 40), BORDER=(60, 200, 235), BORDER_DIM=(28, 84, 120),
                    ORNAMENT=(255, 140, 50), TEXT=(200, 224, 240), DIM=(110, 140, 168), TITLE=(120, 235, 255), KEY=(255, 170, 70),
                    HILITE=(22, 72, 110), HILITE_TEXT=(255, 255, 255), GOOD=(90, 225, 150), BAD=(255, 90, 100), WARN=(255, 195, 70),
                    HP=(225, 70, 80), HUNGER=(240, 160, 50), THIRST=(70, 165, 255), BAR_EMPTY=(26, 36, 56)),
    "phosphor": _palette("Phosphor (green)", BG=(4, 14, 8), PANEL=(8, 26, 14), BORDER=(80, 230, 120), BORDER_DIM=(30, 100, 52),
                         ORNAMENT=(200, 255, 120), TEXT=(170, 235, 190), DIM=(90, 150, 104), TITLE=(190, 255, 170), KEY=(240, 255, 120),
                         HILITE=(24, 90, 44), HILITE_TEXT=(255, 255, 255), GOOD=(120, 240, 130), BAD=(255, 100, 90), WARN=(240, 220, 90),
                         HP=(220, 80, 70), HUNGER=(220, 170, 60), THIRST=(70, 190, 230), BAR_EMPTY=(14, 38, 22)),
    "amber": _palette("Amber (terminal)", BG=(18, 10, 4), PANEL=(32, 18, 6), BORDER=(255, 176, 60), BORDER_DIM=(120, 76, 24),
                      ORNAMENT=(255, 220, 140), TEXT=(240, 205, 150), DIM=(160, 120, 70), TITLE=(255, 210, 110), KEY=(255, 240, 170),
                      HILITE=(100, 58, 14), HILITE_TEXT=(255, 255, 255), GOOD=(170, 230, 110), BAD=(255, 100, 80), WARN=(255, 220, 90),
                      HP=(230, 80, 60), HUNGER=(240, 170, 50), THIRST=(90, 170, 230), BAR_EMPTY=(46, 28, 10)),
    "hull": _palette("Hull (steel)", BG=(16, 18, 22), PANEL=(26, 30, 36), BORDER=(190, 200, 215), BORDER_DIM=(84, 92, 106),
                     ORNAMENT=(255, 120, 40), TEXT=(214, 220, 228), DIM=(130, 140, 154), TITLE=(255, 255, 255), KEY=(255, 150, 60),
                     HILITE=(60, 70, 88), HILITE_TEXT=(255, 255, 255), GOOD=(110, 220, 140), BAD=(255, 90, 80), WARN=(255, 190, 70),
                     HP=(225, 75, 75), HUNGER=(235, 160, 55), THIRST=(80, 165, 245), BAR_EMPTY=(36, 40, 48)),
    "violet": _palette("Violet (neon)", BG=(14, 8, 26), PANEL=(24, 14, 44), BORDER=(190, 120, 255), BORDER_DIM=(86, 54, 130),
                       ORNAMENT=(80, 235, 220), TEXT=(226, 210, 244), DIM=(144, 124, 172), TITLE=(255, 170, 240), KEY=(120, 245, 225),
                       HILITE=(70, 40, 116), HILITE_TEXT=(255, 255, 255), GOOD=(110, 235, 160), BAD=(255, 90, 120), WARN=(255, 205, 90),
                       HP=(235, 70, 110), HUNGER=(245, 165, 60), THIRST=(90, 170, 255), BAR_EMPTY=(36, 24, 62)),
    "classic": _palette("Classic (teal and gold)", BG=(11, 36, 38), PANEL=(17, 52, 54), BORDER=(170, 205, 195), BORDER_DIM=(70, 112, 108),
                        ORNAMENT=(232, 205, 120), TEXT=(205, 222, 212), DIM=(120, 150, 145), TITLE=(245, 225, 150), KEY=(255, 210, 100),
                        HILITE=(44, 112, 104), HILITE_TEXT=(255, 255, 255), GOOD=(110, 215, 120), BAD=(235, 100, 90), WARN=(240, 190, 80),
                        HP=(210, 70, 70), HUNGER=(230, 150, 50), THIRST=(70, 150, 235), BAR_EMPTY=(22, 62, 64)),
}
DEFAULT_THEME = "ion"
THEME_ORDER = tuple(PALETTES)


_FRAME = {"tl": 0xDA, "tr": 0xBF, "bl": 0xC0, "br": 0xD9, "h": 0xC4, "v": 0xB3}


def cp437_index(character: str) -> int:
    """Index of `character` in the CP437 sheet ('?' for characters CP437 does not have)."""
    try:
        return character.encode("cp437")[0]
    except (UnicodeEncodeError, IndexError):
        return ord("?")


TEXT_FONT = "data/fonts/DejaVuSansMono.ttf"
TEXT_SIZE = 20
CHAR_W = 12
"""Text is set in DejaVu Sans Mono 20 px: 12 px per character, 24 px per line, so two characters fit in a 24 px cell."""


class Font:
    """Text: a monospaced TrueType font (clean, readable, two characters per cell) with rendered strings cached per
    (text, colour). The old CP437 sheet is kept only for single glyphs (badges)."""

    def __init__(self, sheet: pygame.Surface, ttf: Optional[pygame.font.Font] = None):
        if pygame.display.get_surface() is not None:
            sheet = sheet.convert_alpha()
        self.sheet = sheet
        self.cell = sheet.get_width() // FONT_COLUMNS
        self._cache: Dict[Tuple[int, RGB], pygame.Surface] = {}
        self.ttf = ttf
        self.ttf_italic = None
        if ttf is not None:
            try:
                self.ttf_italic = pygame.font.Font(TEXT_FONT, TEXT_SIZE)
                self.ttf_italic.set_italic(True)   # a slanted face for what is only a gloss (the English name of a name)
            except (OSError, pygame.error):
                self.ttf_italic = None
        self._text: Dict[Tuple[str, RGB], pygame.Surface] = {}

    @classmethod
    def load(cls, path: str = "Zesty_curses_24x24.png") -> "Font":
        pygame.font.init()
        try:
            ttf = pygame.font.Font(TEXT_FONT, TEXT_SIZE)
        except (OSError, pygame.error):   # missing font file: fall back to pygame's bundled font so the game still runs
            ttf = pygame.font.Font(None, TEXT_SIZE + 4)
        return cls(atlas_module.load_alpha_sheet(path), ttf)

    def big(self, text: str, fg: RGB = WHITE, size: int = 56) -> pygame.Surface:
        """Large title text (rendered once per string)."""
        key = (text, tuple(fg), size)
        hit = self._text.get(key)
        if hit is None:
            try:
                face = pygame.font.Font(TEXT_FONT, size)
            except (OSError, pygame.error):
                face = pygame.font.Font(None, size + 8)
            face.set_bold(True)
            hit = self._text[key] = face.render(text, True, fg)
        return hit

    def width(self, text: str) -> int:
        """Pixel width of `text` on one line."""
        return self.ttf.size(text)[0] if self.ttf is not None else len(text) * CHAR_W

    def text(self, text: str, fg: RGB = WHITE, italic: bool = False) -> pygame.Surface:
        key = (text, tuple(fg), italic)
        hit = self._text.get(key)
        if hit is None:
            if len(self._text) > 3000:
                self._text.clear()
            face = self.ttf_italic if (italic and self.ttf_italic is not None) else self.ttf
            hit = face.render(text, True, fg)
            self._text[key] = hit
        return hit

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
        self.tab_rects: list = []
        self.hint_hits: list = []
        self.font = font
        self.sprites = sprites or atlas_module.get_atlas()
        self.width = surface.get_width() // CELL
        self.height = surface.get_height() // CELL
        self._overlays: Dict[tuple, pygame.Surface] = {}
        self._badges: Dict[tuple, pygame.Surface] = {}

    # ── geometry ───────────────────────────────────────────────────────────────────
    @staticmethod
    def cell_rect(x: int, y: int, width: int = 1, height: int = 1) -> pygame.Rect:
        return pygame.Rect(x * CELL, y * CELL, width * CELL, height * CELL)

    # ── primitives ─────────────────────────────────────────────────────────────────
    def clear(self, color: RGB = BLACK) -> None:
        self.tab_rects = []
        self.hint_hits = []
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

    def badge(self, x: int, y: int, text: str = "+") -> None:
        """A small marker in the top-right corner of cell (x, y) (used for "more objects lie here")."""
        size = CELL // 2
        key = (text, size)
        marker = self._badges.get(key)
        if marker is None:
            marker = pygame.Surface((size, size), pygame.SRCALPHA)
            marker.fill((0, 0, 0, 230))
            glyph = pygame.transform.scale(self.font.glyph(cp437_index(text[0]), WHITE), (size, size))
            marker.blit(glyph, (0, 0))
            self._badges[key] = marker
        self.surface.blit(marker, (x * CELL + CELL - size, y * CELL))

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
        italic: bool = False,
    ) -> None:
        """Print `text` starting at cell (x, y); '\\n' starts a new line.

        With `alignment=CENTER` x is the middle of each line, with `RIGHT` its last column.
        """
        for row, line in enumerate(text.split("\n")):
            self._print_line(x, y + row, line, fg, bg, alignment, italic)

    def _print_line(self, x: int, y: int, line: str, fg: RGB, bg: Optional[RGB], alignment: int, italic: bool = False) -> None:
        """One line of text; `x` and `y` are cells, the text itself is set in pixels (12 px per character)."""
        if y < 0 or y >= self.height or not line:
            return
        width = self.font.width(line)
        px = x * CELL
        if alignment == CENTER:
            px -= width // 2
        elif alignment == RIGHT:
            px = (x + 1) * CELL - width
        if bg is not None:
            self.surface.fill(bg, pygame.Rect(px, y * CELL, width, CELL))
        if line.strip():
            surface = self.font.text(line, fg, italic)
            self.surface.blit(surface, (px, y * CELL + (CELL - surface.get_height()) // 2))

    def print_big(self, x: int, y: int, text: str, fg: RGB = WHITE, size: int = 56) -> int:
        """Large text centred on cell column `x` with its top at row `y`; returns the rows it covers."""
        surface = self.font.big(text, fg, size)
        self.surface.blit(surface, (x * CELL - surface.get_width() // 2, y * CELL))
        return -(-surface.get_height() // CELL)

    def text_width(self, text: str) -> int:
        """Width in cells (rounded up) of the widest line."""
        return max((-(-self.font.width(line) // CELL) for line in text.split("\n")), default=0)

    @staticmethod
    def chars(cells: int) -> int:
        """How many characters of text fit in `cells` cells."""
        return cells * CELL // CHAR_W

    def wrap(self, text: str, cells: int) -> list:
        """`text` broken into lines that fit `cells` cells (existing line breaks are kept)."""
        import textwrap
        out: list = []
        for paragraph in text.split("\n"):
            out.extend(textwrap.wrap(paragraph, self.chars(cells)) or [""])
        return out

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
        """A window frame (`width` x `height` cells): dark teal glass, a double border with gold corner ornaments and the
        title set in a notch on the top edge. `fg` and `bg` are accepted for the old call style and ignored."""
        rect = self.cell_rect(x, y, width, height)
        if clear:
            self.surface.fill(Theme.BG, rect)
        outer = rect.inflate(-10, -10)
        inner = rect.inflate(-18, -18)
        pygame.draw.rect(self.surface, Theme.BORDER, outer, 2)
        pygame.draw.rect(self.surface, Theme.BORDER_DIM, inner, 1)
        for cx, cy in (outer.topleft, outer.topright, outer.bottomleft, outer.bottomright):
            pygame.draw.rect(self.surface, Theme.BG, pygame.Rect(cx - 6, cy - 6, 12, 12))
            pygame.draw.rect(self.surface, Theme.ORNAMENT, pygame.Rect(cx - 5, cy - 5, 10, 10), 2)
            pygame.draw.rect(self.surface, Theme.ORNAMENT, pygame.Rect(cx - 2, cy - 2, 4, 4))
        if title:
            # the title sits ON the top border: the line breaks only as wide as the text, with a diamond at each end
            title = title[: max(0, self.chars(width) - 8)].strip()
            label = self.font.text(title, Theme.TITLE)
            lw, lh = label.get_size()
            cx, cy = rect.centerx, outer.top
            notch = pygame.Rect(cx - lw // 2 - 22, cy - lh // 2 - 1, lw + 44, lh + 2)
            pygame.draw.rect(self.surface, Theme.BG, notch)
            self.surface.blit(label, (cx - lw // 2, cy - lh // 2))
            for side in (notch.left + 9, notch.right - 9):
                pygame.draw.polygon(self.surface, Theme.ORNAMENT, [(side - 4, cy), (side, cy - 4), (side + 4, cy), (side, cy + 4)])

    def draw_outline(self, x: int, y: int, width: int, height: int, color: RGB, thickness: int = 2) -> None:
        """A plain coloured rectangle on the edges of the cell rectangle (map overlays such as the blast area)."""
        pygame.draw.rect(self.surface, color, self.cell_rect(x, y, width, height), thickness)

    def rule(self, x: int, y: int, width: int) -> None:
        """An engraved divider across `width` cells of row `y`: a thin line with a small ornament at each end."""
        py = y * CELL + CELL // 2
        left, right = x * CELL + 14, (x + width) * CELL - 14
        pygame.draw.line(self.surface, Theme.BORDER_DIM, (left, py), (right, py), 1)
        pygame.draw.line(self.surface, Theme.BORDER_DIM, (left, py + 3), (right, py + 3), 1)
        for px in (left, right):
            pygame.draw.polygon(self.surface, Theme.ORNAMENT, [(px - 4, py + 1), (px, py - 3), (px + 4, py + 1), (px, py + 5)])

    def segments(self, x: int, y: int, width: int, lit: int, color: RGB, count: int = 10) -> None:
        """A bar of `count` separate blocks across `width` cells of row `y`, the first `lit` filled with `color`."""
        gap = 4
        total = width * CELL
        size = (total - gap * (count - 1)) // count
        top = y * CELL + 4
        for i in range(count):
            rect = pygame.Rect(x * CELL + i * (size + gap), top, size, CELL - 8)
            self.surface.fill(color if i < lit else Theme.BAR_EMPTY, rect)
            pygame.draw.rect(self.surface, Theme.BORDER_DIM if i >= lit else color, rect, 1)

    def hints(self, x: int, y: int, hints, width: Optional[int] = None) -> None:
        """A row of `[key] action` hints starting at cell (x, y); with `width` (cells) it is centred in that width."""
        parts = [(f"[{key}]", f" {what}") for key, what in hints]
        labels = [key for key, _ in hints]
        total = sum(self.font.width(k + w) + 2 * CHAR_W for k, w in parts) - 2 * CHAR_W
        px = x * CELL + ((width * CELL - total) // 2 if width else 0)
        row = pygame.Rect(0, y * CELL, 0, CELL)
        for (key, what), label in zip(parts, labels):
            start = px
            for text, fg in ((key, Theme.KEY), (what, Theme.TEXT)):
                surface = self.font.text(text, fg)
                self.surface.blit(surface, (px, row.y + (CELL - surface.get_height()) // 2))
                px += surface.get_width()
            self.hint_hits.append((pygame.Rect(start, row.y, px - start, CELL), label))   # clicking a hint presses its key
            px += 2 * CHAR_W

    def window(self, x: int, y: int, width: int, height: int, title: str = "", hints=None, tabs=None, active: int = 0) -> Tuple[int, int, int, int]:
        """Draw a framed window with an optional tab row (below the top edge) and `[key] action` hint bar (on the bottom
        row). Returns the inner area `(x, y, width, height)` in cells for the caller's content."""
        frame = self.cell_rect(x, y, width, height)
        self.tab_rects = [r for r in self.tab_rects if not frame.colliderect(r)]    # whatever this window covers is not clickable
        self.hint_hits = [h for h in self.hint_hits if not frame.colliderect(h[0])]
        self.draw_frame(x, y, width, height, title=title)
        top = y + 1
        if tabs:
            self.tab_row(x + 1, top, width - 2, tabs, active)
            top += 2
        bottom = y + height - 1
        if hints:
            self.fill_theme(x + 1, bottom - 1, width - 2, 1)
            self.hints(x + 1, bottom - 1, hints, width - 2)
            bottom -= 2
        return x + 2, top, width - 4, bottom - top

    def fill_theme(self, x: int, y: int, width: int, height: int, color: Optional[RGB] = None) -> None:
        self.fill(x, y, width, height, color or Theme.BG)

    def tab_row(self, x: int, y: int, width: int, tabs, active: int) -> None:
        """Tabs along the top of a window: `tabs` is a list of `(key, name)` (only the name is drawn); the active one is lit.
        A rule runs under the row."""
        px = x * CELL + CHAR_W
        self.tab_rects = []
        for i, (_, name) in enumerate(tabs):
            label = f" {name} "
            w = self.font.width(label) + 8
            rect = pygame.Rect(px, y * CELL + 2, w, CELL - 2)
            if i == active:
                self.surface.fill(Theme.HILITE, rect)
                pygame.draw.rect(self.surface, Theme.BORDER, rect, 1)
            surface = self.font.text(label, Theme.HILITE_TEXT if i == active else Theme.TEXT)
            self.surface.blit(surface, (px + 4, rect.y + (rect.height - surface.get_height()) // 2))
            self.tab_rects.append(rect)
            px += w + CHAR_W
        pygame.draw.line(self.surface, Theme.BORDER_DIM, (x * CELL + 6, (y + 1) * CELL + 6), ((x + width) * CELL - 6, (y + 1) * CELL + 6), 1)

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
