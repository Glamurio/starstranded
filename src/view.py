"""What the player sees: the stitched view window and the camera.

`ViewWindow` stitches the chunks around the player's chunk (radius `GameConfig.near_radius`, so 3x3 chunks =
210x120 tiles by default) into window-sized arrays: `transparent`, `walkable` and `in_bounds` (tile belongs to a
loaded chunk and to the map), plus `visible`, the FOV result. FOV, campfire light and pathfinding run on these
arrays. The stitched terrain is cached and rebuilt only when the player's chunk changes, a chunk in the window is
loaded/unloaded, or a chunk's `terrain_version` changes (see `World.modify_tile`). `explored` and `blocked` are
not cached here: they are read from the chunks on demand (`World.region`).

`Camera` maps world tiles to cells of the 70x40 map viewport: it is centred on the player and, for bounded maps
(`World.bounds`), clamped so a map no larger than the viewport is drawn at the top-left as before.
"""
from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore

from chunks import CHUNK_H, CHUNK_W, chunk_origin, keys_around

if TYPE_CHECKING:
    from world import World

VIEW_W = 70
VIEW_H = 40
"""Size of the map viewport in cells (the screen minus the side and bottom panels)."""

Rect = Tuple[int, int, int, int]  # x0, y0, width, height (world tiles)


class ViewWindow:
    def __init__(self, world: World):
        self.world = world
        self._key: Optional[tuple] = None
        self.origin: Tuple[int, int] = (0, 0)
        self.size: Tuple[int, int] = (0, 0)
        self.transparent = np.zeros((0, 0), dtype=bool, order="F")
        self.walkable = np.zeros((0, 0), dtype=bool, order="F")
        self.in_bounds = np.zeros((0, 0), dtype=bool, order="F")
        self.visible = np.zeros((0, 0), dtype=bool, order="F")
        self.lit = np.zeros((0, 0), dtype=bool, order="F")
        self.rebuilds = 0

    # ── cache ──────────────────────────────────────────────────────────────────────
    def cache_key(self) -> tuple:
        world = self.world
        center = world.center_key()
        radius = world.config.near_radius
        chunks = world.chunks
        return (center, radius, tuple(
            (key, id(chunk), chunk.terrain_version) if (chunk := chunks.get(key)) is not None else (key, None, None)
            for key in keys_around(center, radius)
        ))

    def ensure(self) -> ViewWindow:
        """Make the stitched arrays current (cheap when nothing changed) and return self."""
        key = self.cache_key()
        if key != self._key:
            self._rebuild(key)
        return self

    def _rebuild(self, key: tuple) -> None:
        (cx, cy), radius, _ = key
        world = self.world
        ox, oy = chunk_origin((cx - radius, cy - radius))
        width, height = (2 * radius + 1) * CHUNK_W, (2 * radius + 1) * CHUNK_H
        transparent = np.zeros((width, height), dtype=bool, order="F")
        walkable = np.zeros((width, height), dtype=bool, order="F")
        in_bounds = np.zeros((width, height), dtype=bool, order="F")
        for chunk_key in keys_around((cx, cy), radius):
            chunk = world.chunks.get(chunk_key)
            if chunk is None:
                continue
            sx, sy = slice(chunk.x0 - ox, chunk.x0 - ox + CHUNK_W), slice(chunk.y0 - oy, chunk.y0 - oy + CHUNK_H)
            transparent[sx, sy] = chunk.tiles["transparent"]
            walkable[sx, sy] = chunk.tiles["walkable"]
            in_bounds[sx, sy] = world.chunk_mask(chunk_key)
        # keep the FOV result for the part that is still inside the window
        visible = np.zeros((width, height), dtype=bool, order="F")
        lit = np.zeros((width, height), dtype=bool, order="F")
        if self.visible.size:
            self._copy_overlap(self.visible, self.origin, visible, (ox, oy))
            self._copy_overlap(self.lit, self.origin, lit, (ox, oy))
        self.origin, self.size = (ox, oy), (width, height)
        self.transparent, self.walkable, self.in_bounds, self.visible = transparent, walkable, in_bounds, visible
        self.lit = lit
        self._key = key
        self.rebuilds += 1

    @staticmethod
    def _copy_overlap(src: np.ndarray, src_origin, dst: np.ndarray, dst_origin) -> None:
        x0 = max(src_origin[0], dst_origin[0])
        y0 = max(src_origin[1], dst_origin[1])
        x1 = min(src_origin[0] + src.shape[0], dst_origin[0] + dst.shape[0])
        y1 = min(src_origin[1] + src.shape[1], dst_origin[1] + dst.shape[1])
        if x0 >= x1 or y0 >= y1:
            return
        dst[x0 - dst_origin[0]:x1 - dst_origin[0], y0 - dst_origin[1]:y1 - dst_origin[1]] = \
            src[x0 - src_origin[0]:x1 - src_origin[0], y0 - src_origin[1]:y1 - src_origin[1]]

    # ── coordinates ────────────────────────────────────────────────────────────────
    @property
    def rect(self) -> Rect:
        return self.origin[0], self.origin[1], self.size[0], self.size[1]

    def contains(self, x: int, y: int) -> bool:
        ox, oy = self.origin
        return ox <= x < ox + self.size[0] and oy <= y < oy + self.size[1]

    def to_window(self, x: int, y: int) -> Tuple[int, int]:
        return x - self.origin[0], y - self.origin[1]

    def is_visible(self, x: int, y: int) -> bool:
        if not self.contains(x, y):
            return False
        return bool(self.visible[x - self.origin[0], y - self.origin[1]])

    def visible_region(self, rect: Rect) -> np.ndarray:
        """`visible` for a world rectangle (False outside the window)."""
        out = np.zeros((rect[2], rect[3]), dtype=bool, order="F")
        self._copy_overlap(self.visible, self.origin, out, rect[:2])
        return out

    def lit_region(self, rect: Rect) -> np.ndarray:
        """`lit` (seen and lit by a light source) for a world rectangle."""
        out = np.zeros((rect[2], rect[3]), dtype=bool, order="F")
        self._copy_overlap(self.lit, self.origin, out, rect[:2])
        return out


class Camera:
    """Top-left world tile of the map viewport."""

    def __init__(self, x0: int, y0: int, width: int = VIEW_W, height: int = VIEW_H):
        self.x0, self.y0 = x0, y0
        self.width, self.height = width, height

    @classmethod
    def follow(cls, world: World, x: int, y: int, width: int = VIEW_W, height: int = VIEW_H) -> Camera:
        """The page (one screenful, aligned to the chunk grid) that holds (x, y): the picture stays still while you walk
        and the next page appears when you step over the edge. For bounded maps the pages start at the map's corner and the
        last one is pulled back so it never shows beyond the map."""
        bounds = world.bounds
        ox, oy = (bounds[0], bounds[1]) if bounds is not None else (0, 0)
        x0 = (x - ox) // width * width + ox
        y0 = (y - oy) // height * height + oy
        if bounds is not None:
            bx, by, bw, bh = bounds
            x0 = bx if bw <= width else max(bx, min(x0, bx + bw - width))
            y0 = by if bh <= height else max(by, min(y0, by + bh - height))
        return cls(x0, y0, width, height)

    @property
    def rect(self) -> Rect:
        return self.x0, self.y0, self.width, self.height

    def to_screen(self, x: int, y: int) -> Tuple[int, int]:
        return x - self.x0, y - self.y0

    def to_world(self, sx: int, sy: int) -> Tuple[int, int]:
        return sx + self.x0, sy + self.y0

    def contains(self, x: int, y: int) -> bool:
        return self.x0 <= x < self.x0 + self.width and self.y0 <= y < self.y0 + self.height

    def on_screen(self, sx: int, sy: int) -> bool:
        return 0 <= sx < self.width and 0 <= sy < self.height
