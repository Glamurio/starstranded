from typing import Tuple, List, Optional

import numpy as np  # type: ignore
import color
import random

import spriteconfig
from atlas import NO_SPRITE, sprite_id
from utilities import get_random_color, get_shade

# Water/wall colours are rolled once per process. A private RNG keeps that import-time roll from shifting the
# global `random` stream (which would make world generation depend on *when* this module is first imported).
_palette_rng = random.Random()

# Tile graphics: what one cell looks like. `sprite` is an atlas id (NO_SPRITE draws nothing), `flip` mirrors it
# horizontally, `fg` is the colour the white sprite is tinted with and `bg` the opaque colour behind it.
graphic_dt = np.dtype(
    [
        ("sprite", np.int32),
        ("flip", np.bool_),
        ("fg", "3B"),  # 3 unsigned bytes, for RGB colors.
        ("bg", "3B"),
    ]
)

# Tile struct used for statically defined tile data.
tile_dt = np.dtype(
    [
        ("walkable", bool),   # type: ignore # True if this tile can be walked over.
        ("transparent", bool),   # type: ignore # True if this tile doesn't block FOV.
        ("dark", graphic_dt),  # Graphics for when this tile was explored but is not in FOV.
        ("light", graphic_dt),  # Graphics for when the tile is in FOV.
        ("open", bool),  # type: ignore # True if there is no floor here: the layer below is visible through it.
        ("stairs", np.int8),  # +1: stairs up, -1: stairs down, 0: none.
        ("liquid", np.int8),  # 0: none, else the kind of liquid (see liquids.LiquidKind).
        ("depth", np.int8),  # liquid depth: 0 none, 1 shallow (can be waded), 2 and 3 deeper (cannot).
    ]
)

class Tile(object):
    """
    A kind of terrain. `sprite` is its `(column, row)` on the sprite sheet, `variations` lists extra
    `(column, row, name)` sprites (edge pieces) that `variation_ids` maps to atlas ids.

    `dark_bg` and `dark_fg` are appearance when explored but not in LoS.

    `light_bg` and `light_fg` are appearance when in LoS.
    """
    def __init__(
        self,
        *,
        walkable: int = False,
        transparent: int = False,
        object_type: str = "Name",
        variations: Optional[List[Tuple[int, int, str]]] = None,
        sprite: Tuple[int, int] = (124, 49),
        dark_bg: Tuple[int, Tuple[int, int, int]] = (255, 255, 255),
        dark_fg: Tuple[int, Tuple[int, int, int]] = (255, 255, 255),
        light_bg: Tuple[int, Tuple[int, int, int]] = (255, 255, 255),
        light_fg: Tuple[int, Tuple[int, int, int]] = (255, 255, 255),
        open: bool = False,
        stairs: int = 0,
        liquid: int = 0,
        depth: int = 0,
        dtype: np.dtype = tile_dt,
    ):
        
        self.object_type = object_type
        self.walkable = walkable
        self.transparent = transparent
        self.sprite_pos = sprite
        self.sprite = sprite_id(*sprite)

        self.variations = variations if variations is not None else []
        self.variation_ids = {name: sprite_id(column, row) for column, row, name in self.variations}

        self.dark_bg = dark_bg
        self.dark_fg = dark_fg
        self.dark = (self.sprite, False, dark_fg, dark_bg)

        self.light_bg = light_bg
        self.light_fg = light_fg
        self.light = (self.sprite, False, light_fg, light_bg)

        self.open = open
        self.stairs = stairs
        self.liquid = liquid
        self.depth = depth
        self.dtype = dtype

    def set_sprite(self, pos: Tuple[int, int], variation: Optional[str] = None) -> None:
        """Draw this tile (or one of its named variations) with another sheet cell; used by the sprite config and editor."""
        if variation is not None:
            self.variations = [(pos[0], pos[1], n) if n == variation else (c, r, n) for c, r, n in self.variations]
            self.variation_ids = {n: sprite_id(c, r) for c, r, n in self.variations}
            return
        self.sprite_pos = pos
        self.sprite = sprite_id(*pos)
        self.dark = (self.sprite, False, self.dark_fg, self.dark_bg)
        self.light = (self.sprite, False, self.light_fg, self.light_bg)

    def get_array(self) -> np.ndarray:
        """Helper function for returning individual tile types"""
        return np.array((self.walkable, self.transparent, self.dark, self.light, self.open, self.stairs,
                         self.liquid, self.depth), dtype=self.dtype)

# SHROUD represents unexplored, unseen tiles
SHROUD = np.array((NO_SPRITE, False, (255, 255, 255), (0, 0, 0)), dtype=graphic_dt)

# VOID is what lies outside a bounded map (and fills the unused part of its chunk): nothing to walk on or see through.
VOID = np.array((False, False, SHROUD.tolist(), SHROUD.tolist(), False, 0, 0, 0), dtype=tile_dt)

floor = Tile(
    object_type="Floor",
    walkable=True,
    transparent=True,
    sprite=(0, 5),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    dark_fg=color.gray,
    dtype=tile_dt
)
water_color = get_random_color(rng=_palette_rng)
water_variations = [
    (0, 41, "north_west"),
    (1, 41, "north"),
    (2, 41, "north_east"),
    (3, 41, "west"),
    (4, 41, "center"),
    (5, 41, "east"),
    (6, 41, "south_west"),
    (7, 41, "south"),
    (8, 41, "south_east"),
    (104, 1, "center_solo"),
    (105, 1, "east_west"),
    (106, 1, "north_south"),
    (107, 1, "north_solo"),
    (108, 1, "east_solo"),
    (109, 1, "south_solo"),
    (110, 1, "west_solo")
]
water = Tile(
    object_type="Liquid",
    variations=water_variations,
    walkable=False,
    transparent=True,
    sprite=(9, 41),
    dark_fg=get_shade(water_color),
    light_fg=water_color,
    light_bg=color.nigh_black,
    dark_bg=color.black,
    dtype=tile_dt
)
wall_color = get_random_color(rng=_palette_rng)
wall_variations = [
    (109, 0, "north_west"),
    (1, 2, "north"),
    (110, 0, "north_east"),
    (1, 2, "west"),
    (1, 2, "center"),
    (1, 2, "east"),
    (112, 0, "south_west"),
    (1, 2, "south"),
    (111, 0, "south_east"),
    (114, 0, "center_solo"),
]
wall = Tile(
    object_type="Wall",
    variations=wall_variations,
    walkable=False,
    transparent=False,
    sprite=(0, 2),
    dark_fg=get_shade(wall_color),
    light_fg=wall_color,
    light_bg=color.nigh_black,
    dark_bg=color.black,
    dtype=tile_dt
)
down_stairs = Tile(  # walkable: stand on it and press > (or L) to descend
    object_type="Downstairs",
    walkable=True,
    transparent=True,
    sprite=(23, 1),
    dark_fg=(50, 50, 150),
    light_fg=(200, 180, 50),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    stairs=-1,
    dtype=tile_dt
)
up_stairs = Tile(  # walkable: stand on it and press < (or L) to climb
    object_type="Upstairs",
    walkable=True,
    transparent=True,
    sprite=(24, 1),
    dark_fg=(50, 50, 150),
    light_fg=(220, 200, 90),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    stairs=1,
    dtype=tile_dt
)
open_air = Tile(  # no floor: you look down on the layer below (drawn by the world renderer); cannot be walked on
    object_type="Open air",
    walkable=False,
    transparent=True,
    sprite=(2, 5),
    dark_fg=(30, 40, 70),
    light_fg=(60, 80, 130),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    open=True,
    dtype=tile_dt
)
built_floor = Tile(  # a floor the player laid
    object_type="Wooden floor",
    walkable=True,
    transparent=True,
    sprite=(3, 5),
    dark_fg=(60, 40, 25),
    light_fg=(150, 105, 60),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    dtype=tile_dt
)
bridge = Tile(  # planks over water: walkable, nothing grows or flows on it
    object_type="Bridge",
    walkable=True,
    transparent=True,
    sprite=(2, 4),
    dark_fg=(70, 48, 28),
    light_fg=(170, 120, 70),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    dtype=tile_dt
)
path = Tile(  # trodden earth: the way between places, and the banks of a bridge
    object_type="Path",
    walkable=True,
    transparent=True,
    sprite=(2, 5),
    dark_fg=(62, 50, 36),
    light_fg=(150, 125, 90),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    dtype=tile_dt
)


def is_laid(tiles: np.ndarray) -> np.ndarray:
    """Mask of the tiles that are a bridge or a path (told by their sprite: the tile array has no room for a kind)."""
    return np.isin(tiles["light"]["sprite"], (bridge.sprite, path.sprite))


cave_floor = Tile(
    object_type="Cave floor",
    walkable=True,
    transparent=True,
    sprite=(0, 5),
    dark_fg=(45, 40, 50),
    light_fg=(110, 100, 120),
    dark_bg=color.black,
    light_bg=color.nigh_black,
    dtype=tile_dt
)


def _apply_sprite_config() -> None:
    """Record every tile's default sprites and apply the overrides from data/sprites.json."""
    for name, tile in list(globals().items()):
        if not isinstance(tile, Tile):
            continue
        tile.set_sprite(spriteconfig.get(f"tile.{name}", tile.sprite_pos))
        for column, row, variation in list(tile.variations):
            tile.set_sprite(spriteconfig.get(f"tile.{name}.{variation}", (column, row)), variation)


_apply_sprite_config()
