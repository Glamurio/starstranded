"""Sprite atlas: the Urizen tilesheet loaded once, with cached tinted / mirrored variants.

The sheet is a 125x50 grid of 24x24 px sprites (``urizen_white.png``, made by ``scripts/build_tileset.py`` from the official
Urizen sheet plus the project's own sprites). It is a white RGBA image whose alpha is the sprite, so loading just keeps the
alpha. Tinting is then a single multiply, which is how every sprite gets its colour.

Sprites are addressed by *sprite id* = ``row * COLUMNS + column`` (see ``sprite_id``); definitions
keep their ``(column, row)`` pairs and convert once at import time.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np  # type: ignore
import pygame

RGB = Tuple[int, int, int]

COLUMNS = 125
ROWS = 50
TILE = 24
"""Pixel size of one sprite (and of one cell of the game's grid)."""

NO_SPRITE = -1
"""Sprite id meaning "draw nothing" (used for unexplored tiles)."""

WHITE: RGB = (255, 255, 255)

# Variants are cached by key; the cache is cleared wholesale when it grows past this many entries
# (every tree has its own gaussian tint, so the number of distinct keys is not bounded by the content).
MAX_CACHED_VARIANTS = 6000


def sprite_id(column: int, row: int) -> int:
    """Id of the sprite at `(column, row)` of the sheet."""
    assert 0 <= column < COLUMNS and 0 <= row < ROWS, (column, row)
    return row * COLUMNS + column


def sprite_position(sprite: int) -> Tuple[int, int]:
    """Inverse of `sprite_id`: `(column, row)`."""
    return sprite % COLUMNS, sprite // COLUMNS


def load_mask_sheet(path: str, *, threshold: int = 384) -> pygame.Surface:
    """Load `path` as a white RGBA surface whose alpha is 255 where the source pixel is bright.

    `threshold` is compared against r+g+b (so 384 = mid-grey).
    """
    source = pygame.image.load(path)
    rgb = pygame.surfarray.array3d(source).astype(np.int32)
    return _mask_to_surface(rgb.sum(axis=2) >= threshold)


def load_alpha_sheet(path: str) -> pygame.Surface:
    """Load `path` (an image with alpha) as a white RGBA surface keeping only its alpha channel."""
    source = pygame.image.load(path)
    if source.get_flags() & pygame.SRCALPHA:
        mask = pygame.surfarray.array_alpha(source) > 127
    else:
        mask = pygame.surfarray.array3d(source).astype(np.int32).sum(axis=2) >= 384
    return _mask_to_surface(mask)


def _mask_to_surface(mask: np.ndarray) -> pygame.Surface:
    surface = pygame.Surface(mask.shape, pygame.SRCALPHA, 32)
    surface.fill((255, 255, 255, 0))
    pygame.surfarray.pixels_alpha(surface)[:] = mask.astype(np.uint8) * 255
    return surface


BONE = (228, 220, 196, 255)
BONE_SHADE = (150, 142, 124, 255)


def draw_bones(surface: pygame.Surface) -> None:
    """A little skull and two crossed bones (24x24 tile), drawn pixel by pixel over `surface`."""
    skull = ["..XXXX..", ".XXXXXX.", "XXXXXXXX", "X.XXXX.X", "XXXXXXXX", ".XXXXXX.", "..X..X.."]
    for dy, row in enumerate(skull):
        for dx, ch in enumerate(row):
            if ch == "X":
                eye = (dy, dx) in ((3, 1), (3, 6))
                surface.set_at((3 + dx, 14 + dy), BONE_SHADE if eye else BONE)
    for i in range(9):                                  # two crossed long bones
        for x, y in ((12 + i, 6 + i), (12 + i, 14 - i)):
            if 0 <= x < 24 and 0 <= y < 24:
                surface.set_at((x, y), BONE)
    for x, y in ((11, 5), (11, 15), (21, 15), (21, 5)):
        surface.set_at((x, y), BONE)


def draw_puddle(surface: pygame.Surface, variant: int) -> None:
    """A white blob (alpha = the puddle, grey = darker towards the middle) built from a few overlapping discs, 24x24 px.
    `variant` seeds its shape so neighbouring puddles differ; tinting it gives the fluid's colour."""
    import random
    rng = random.Random(variant)
    cx, cy = 12 + rng.randint(-1, 1), 13 + rng.randint(-1, 1)
    discs = [(cx, cy, rng.randint(5, 7))]
    for _ in range(rng.randint(3, 5)):
        discs.append((cx + rng.randint(-6, 6), cy + rng.randint(-5, 5), rng.randint(2, 4)))
    for x in range(24):
        for y in range(24):
            depth = max((r - ((x - dx) ** 2 + (y - dy) ** 2) ** 0.5 for dx, dy, r in discs), default=-1)
            if depth >= 0:
                shade = 255 if depth < 1.5 else 205
                surface.set_at((x, y), (shade, shade, shade, 235 if depth >= 1.5 else 200))
    for _ in range(rng.randint(2, 4)):              # a few spatters
        x, y = rng.randint(1, 22), rng.randint(1, 22)
        surface.set_at((x, y), (230, 230, 230, 220))


def draw_lily_pad(surface: pygame.Surface, variant: int) -> None:
    """A round pad with a wedge cut out (white, grey veins) and, on some variants, a pale flower in the middle."""
    import random
    rng = random.Random(variant)
    cx, cy, radius = 12 + rng.randint(-2, 2), 12 + rng.randint(-2, 2), rng.randint(6, 8)
    notch = rng.uniform(0, 6.28)
    import math
    for x in range(24):
        for y in range(24):
            dx, dy = x - cx, y - cy
            distance = (dx * dx + dy * dy) ** 0.5
            if distance > radius:
                continue
            angle = math.atan2(dy, dx)
            if distance > 1.5 and abs((angle - notch + math.pi) % (2 * math.pi) - math.pi) < 0.28:
                continue                                           # the wedge
            vein = abs(((angle - notch) * 3.2 / math.pi) % 1.0 - 0.5) < 0.05 and distance > 2
            shade = 190 if vein else 235
            surface.set_at((x, y), (shade, shade, shade, 255))
    if variant % 3 == 0:                                         # a bloom
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            surface.set_at((cx + dx, cy + dy), (255, 255, 255, 255))


class SpriteAtlas:
    """Holds the sheet once and hands out cached sprite surfaces.

    `get(sprite, flipped, tint)` returns a TILE x TILE surface with per-pixel alpha;
    `get_on(sprite, flipped, tint, bg)` returns the same sprite composited over an opaque `bg` colour
    (what terrain tiles use, so one blit draws background and sprite together).
    Returned surfaces are shared: callers must not draw on them.
    """

    def __init__(self, sheet: pygame.Surface):
        if pygame.display.get_surface() is not None:
            sheet = sheet.convert_alpha()
        self.sheet = sheet
        self.columns = sheet.get_width() // TILE
        self.rows = sheet.get_height() // TILE
        self._cache: Dict[tuple, pygame.Surface] = {}

    @classmethod
    def load(cls, path: str) -> "SpriteAtlas":
        return cls(load_alpha_sheet(path))

    def rect(self, sprite: int) -> pygame.Rect:
        column, row = sprite % COLUMNS, sprite // COLUMNS
        return pygame.Rect(column * TILE, row * TILE, TILE, TILE)

    def get(self, sprite: int, flipped: bool = False, tint: RGB = WHITE) -> pygame.Surface:
        key = (sprite, bool(flipped), tuple(tint))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        self._make_room()
        surface = self.sheet.subsurface(self.rect(sprite)).copy()
        if flipped:
            surface = pygame.transform.flip(surface, True, False)
        if tuple(tint) != WHITE:
            surface.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._cache[key] = surface
        return surface

    def get_remains(self, sprite: int, flipped: bool = False, tint: RGB = WHITE) -> pygame.Surface:
        """What is left of a creature: its own sprite lying on its side (rotated a quarter turn, darkened) with bones on top."""
        key = (sprite, bool(flipped), tuple(tint), "remains")
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        self._make_room()
        body = pygame.transform.rotate(self.get(sprite, flipped, tuple(int(c * 0.7) for c in tint)), 90)
        draw_bones(body)
        self._cache[key] = body
        return body

    def get_decal(self, pattern: str, variant: int, tint: RGB) -> pygame.Surface:
        """A procedural ground picture of colour `tint`: a "puddle" (blood, oil...) or a "lilypad"; `variant` (0-7) picks its shape."""
        key = (pattern, variant % 8, tuple(tint))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        self._make_room()
        surface = pygame.Surface((TILE, TILE), pygame.SRCALPHA, 32)
        (draw_lily_pad if pattern == "lilypad" else draw_puddle)(surface, variant % 8)
        surface.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._cache[key] = surface
        return surface

    def get_on(self, sprite: int, flipped: bool, tint: RGB, bg: RGB) -> pygame.Surface:
        """The sprite over an opaque background; `sprite == NO_SPRITE` gives just the background."""
        key = (sprite, bool(flipped), tuple(tint), tuple(bg), "bg")
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        self._make_room()
        surface = pygame.Surface((TILE, TILE))
        surface.fill(bg)
        if sprite != NO_SPRITE:
            surface.blit(self.get(sprite, flipped, tint), (0, 0))
        if pygame.display.get_surface() is not None:
            surface = surface.convert()
        self._cache[key] = surface
        return surface

    def _make_room(self) -> None:
        if len(self._cache) >= MAX_CACHED_VARIANTS:
            self._cache.clear()

    @property
    def cached_variants(self) -> int:
        return len(self._cache)


_atlas: Optional[SpriteAtlas] = None


def get_atlas() -> SpriteAtlas:
    """The process-wide atlas, loaded on first use (relative to the working directory, like all assets)."""
    global _atlas
    if _atlas is None:
        _atlas = SpriteAtlas.load("urizen_white.png")
    return _atlas


def reset_atlas() -> None:
    global _atlas
    _atlas = None
