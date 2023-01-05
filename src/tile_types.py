from typing import Tuple

import numpy as np  # type: ignore
import color
from utilities import map_codepoints, get_random_color, get_shade

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
    """
    Tile sprite is controlled via `sprite_pos` on `global_tilesheet`

    `dark_bg` and `dark_fg` are appearance when not on LoS.

    `light_bg` and `light_fg` are appearance when in LoS.
    """
    def __init__(
        self,
        *,
        walkable: int = False,
        transparent: int = False,
        kind: str = "Name",
        sprite_pos: Tuple[int, int] = (0, 0),
        dark_bg: Tuple[int, Tuple[int, int, int]] = (255, 255, 255),
        dark_fg: Tuple[int, Tuple[int, int, int]] = (255, 255, 255),
        light_bg: Tuple[int, Tuple[int, int, int]] = (255, 255, 255),
        light_fg: Tuple[int, Tuple[int, int, int]] = (255, 255, 255),
        dtype: np.dtype = tile_dt,
    ):
        
        self.kind = kind
        self.walkable = walkable
        self.transparent = transparent
        self.sprite_pos = sprite_pos

        char_info = map_codepoints(self.kind, sprite_pos)
        self.codepoint = char_info["sprite"]

        self.dark_bg = dark_bg
        self.dark_fg = dark_fg
        self.dark = (self.codepoint, dark_fg, dark_bg)

        self.light_bg = dark_bg
        self.light_fg = dark_fg
        self.light = (self.codepoint, light_fg, light_bg)

        self.dtype = dtype

    def get_array(self) -> np.ndarray:
        """Helper function for returning individual tile types"""
        return np.array((self.walkable, self.transparent, self.dark, self.light), dtype=self.dtype)

# SHROUD represents unexplored, unseen tiles
SHROUD = np.array((ord(" "), (255, 255, 255), (0, 0, 0)), dtype=graphic_dt)

floor = Tile(
    kind="Floor",
    walkable=True,
    transparent=True,
    sprite_pos=(0, 2),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    dark_fg=color.gray,
    dtype=tile_dt
)
water_color = get_random_color()
water = Tile(
    kind="Water",
    walkable=False,
    transparent=True,
    sprite_pos=(9, 32),
    dark_fg=get_shade(water_color),
    light_fg=water_color,
    light_bg=color.white,
    dark_bg=color.gray,
    dtype=tile_dt
)
roots = Tile(
    kind="Roots",
    walkable=True,
    transparent=True,
    sprite_pos=(9, 2),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    dark_fg=color.dark_brown,
    light_fg=color.brown,
    dtype=tile_dt
)
wall = Tile(
    kind="Wall",
    walkable=False,
    transparent=False,
    sprite_pos=(1, 0),
    dark_fg=color.dark_gray,
    light_fg=color.gray,
    dtype=tile_dt
)
down_stairs = Tile(
    kind="Downstairs",
    walkable=False,
    transparent=False,
    sprite_pos=(11, 0),
    dark_fg=(50, 50, 150),
    light_fg=(200, 180, 50),
    dtype=tile_dt
)