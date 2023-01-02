"""Global module for all global variables"""

import tcod
import numpy as np # type: ignore
from typing import List

CHARMAP_URIZEN = np.arange(0xE000, 0xF8FF+1)
"""
Custom `Private Use Area` charmap for Urizen
"""

mapped_chars: List[int] = [0xE000]
"""List, which tracks mapped codepoints"""

global_tileset = tcod.tileset.load_tilesheet(
    "urizen_nogrid_white.png", 50, 50, CHARMAP_URIZEN
)
"""Global tileset, referenced when adding additional tiles"""

screen_width = 80
""""""
screen_height = 45
root_console = tcod.Console(screen_width, screen_height, order="F")
logical_size = (root_console.width * global_tileset.tile_width, root_console.height * global_tileset.tile_height)
sdl_window = tcod.sdl.video.new_window(
    width=logical_size[0],
    height=logical_size[1],
    title="Starstranded",
    flags=tcod.lib.SDL_WINDOW_RESIZABLE,
)
sdl_renderer = tcod.sdl.render.new_renderer(sdl_window, target_textures=True)
sdl_renderer.logical_size = logical_size
atlas = tcod.render.SDLTilesetAtlas(sdl_renderer, global_tileset)
console_render = tcod.render.SDLConsoleRender(atlas)