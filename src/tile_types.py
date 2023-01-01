from typing import Tuple

import numpy as np  # type: ignore
import color

# Tile graphics structured type compatible with Console.rgb.
graphic_dt = np.dtype(
    [
        ("ch", np.int32),  # Unicode codepoint.
        ("fg", "3B"),  # 3 unsigned bytes, for RGB colors.
        ("bg", "3B"),
    ]
)

# Tile struct used for statically defined tile data.
tile_dt = np.dtype(
    [
        ("walkable", np.bool),   # type: ignore # True if this tile can be walked over.
        ("transparent", np.bool),   # type: ignore # True if this tile doesn't block FOV.
        ("dark", graphic_dt),  # Graphics for when this tile is not in FOV.
        ("light", graphic_dt),  # Graphics for when the tile is in FOV.
    ]
)

class Tile(object):
    def __init__(
        self,
        *,
        walkable: int = False,
        transparent: int = False,
        dark: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
        light: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
        dtype: np.dtype = tile_dt,
    ):

        self.walkable = walkable
        self.transparent = transparent
        self.dark = dark
        self.light = light
        self.dtype = dtype

    def get_array(self) -> np.ndarray:
        """Helper function for returning individual tile types"""
        return np.array((self.walkable, self.transparent, self.dark, self.light), dtype=self.dtype)

# SHROUD represents unexplored, unseen tiles
SHROUD = np.array((ord(" "), (255, 255, 255), (0, 0, 0)), dtype=graphic_dt)

floor = Tile(
    walkable=True,
    transparent=True,
    dark=(ord(" "), (255, 255, 255), (50, 50, 150)),
    light=(ord(" "), (255, 255, 255), (200, 180, 50)),
    dtype=tile_dt
)
water = Tile(
    walkable=False,
    transparent=True,
    dark=(ord(" "), (255, 255, 255), color.dark_blue),
    light=(ord(" "), (255, 255, 255), color.blue),
    dtype=tile_dt
)
wall = Tile(
    walkable=False,
    transparent=False,
    dark=(ord(" "), (255, 255, 255), (0, 0, 100)),
    light=(ord(" "), (255, 255, 255), (130, 110, 50)),
    dtype=tile_dt
)
down_stairs = Tile(
    walkable=True,
    transparent=True,
    dark=(ord(">"), (0, 0, 100), (50, 50, 150)),
    light=(ord(">"), (255, 255, 255), (200, 180, 50)),
    dtype=tile_dt
)