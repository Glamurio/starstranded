"""Global module for all global variables"""
from __future__ import annotations

import tcod
import numpy as np # type: ignore
from typing import List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from input_handlers import BaseEventHandler

CHARMAP_URIZEN = np.arange(0xE000, 0xF8FF+1)
"""
Custom `Private Use Area` charmap for Urizen
"""

mapped_chars: List[int] = [0xE000]
"""List, which tracks mapped codepoints"""

char_dict: Dict[Dict] = {None: mapped_chars[0]}
"""
Used to reference which codepoints belong to which char

Keys are `class`, values are `int`
"""

global_tileset_size = (50, 50)
global_tileset = tcod.tileset.load_tilesheet(
    "urizen_nogrid_white.png", global_tileset_size[0], global_tileset_size[1], CHARMAP_URIZEN
)
"""Global tileset, referenced when adding additional tiles"""

text_tileset_site = (16, 16)
text_tileset = tcod.tileset.load_tilesheet(
    "Zesty_curses_24x24.png", text_tileset_site[0], text_tileset_site[1], tcod.tileset.CHARMAP_CP437
)

screen_width = 80
screen_height = 45
screen_width_offset = 10
screen_height_offset = 5

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

def render(handler: BaseEventHandler) -> None:
    """
    Global render function
    
    Expects a `handler: BaseEventHandler` to render.
    """
    root_console.clear()
    handler.on_render(console=root_console)

    sdl_renderer.draw_blend_mode = tcod.sdl.render.BlendMode.NONE
    sdl_renderer.copy(console_render.render(root_console))

    # sdl_renderer.draw_blend_mode = tcod.sdl.render.BlendMode.BLEND
    # sdl_renderer.copy(console_render2.render(console2))

    sdl_renderer.present()