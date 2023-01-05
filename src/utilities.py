# Utility functions
from __future__ import annotations

import os
import tcod
import g
import random

import numpy as np # type: ignore
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Tuple

if TYPE_CHECKING:
    pass

def get_data(path: str) -> str:
    """Return the path to a resource in the libtcod data directory,"""
    SCRIPT_DIR = os.path.dirname(__file__)
    DATA_DIR = os.path.join(SCRIPT_DIR, "../libtcod/data")
    assert os.path.exists(DATA_DIR), (
        "Data directory is missing," " did you forget to run `git submodule update --init`?"
    )
    return os.path.join(DATA_DIR, path)

def clamp(n: int, smallest: int, largest: int):
    """Clamps `n` to `smallest` or `largest`"""
    return max(smallest, min(n, largest))

def get_random_color(threshold: int = 30) -> Tuple(int, int, int):
    """Gets random color, excluding colors that exceed `threshold`"""
    return (max((255 * random.random()), threshold), max((255 * random.random()), threshold), max((255 * random.random()), threshold))

def get_shade(color: tuple[float, float, float], factor: float = -0.5):
    """Get shade reduced or increased by `factor`"""
    N = 1 + factor
    shade = (color[0] * N, color[1] * N, color[2] * N)
    return (clamp(shade[0], 0, 255), clamp(shade[1], 0, 255), clamp(shade[2], 0, 255))

def get_gaussian_shade(color: tuple[float, float, float], sigma: float = 20):
    """Get gaussian average of `color` as a shade, with a deviation of `sigma`"""
    shade = (int(random.gauss(color[0], sigma)), int(random.gauss(color[1], sigma)), int(random.gauss(color[2], sigma)))
    return (clamp(shade[0], 0, 255), clamp(shade[1], 0, 255), clamp(shade[2], 0, 255))

def is_mouse_in_rectangle(mouse: tcod.event.MouseState, point: tcod.event.Point, width: int, height: int) -> bool:
    """
    Check if current mouse position is within a rectangle of given `width` and `height` and return True or False.

    `point` indicates the center of the rectangle.
    """
    mouse_pt = mouse.tile

    return (point.x - width // 2) < (mouse_pt.x) and (point.x + width // 2) > (mouse_pt.x) \
        and (point.y - height // 2) < (mouse_pt.y) and (point.y + height // 2) > (mouse_pt.y)

def text_input(buffer: str = "") -> str:
    for event in tcod.event.wait():
        match event:
            case tcod.event.KeyDown(sym=tcod.eventKeySym.KeySym.RETURN):
                return buffer
            case tcod.event.KeyDown(sym=tcod.eventKeySym.BACKSPACE):
                buffer = buffer[:-1]
            case tcod.event.TextInput(text=text):
                buffer += text

def generate_name(origin: str):
    path = Path("./data/namegen").resolve()
    file_names = []
    for file in os.listdir(path):
        file_names.append(file)
        if file.find(".cfg") > 0:
            tcod.namegen_parse(os.path.join(path, file))

    # get the sets list
    name_sets = tcod.namegen_get_sets()
    for name_set in name_sets:
        if not origin.casefold() in name_set.casefold():
            continue

        return tcod.namegen_generate(name_set)
    return tcod.namegen_generate(name_sets[0])

def map_codepoints(class_name: str, char_xy: tuple(int, int), mirror = False, corpse_xy: tuple(int, int) = None) -> Dict:
    """
    Function, which maps class_name to codepoint(s) and coordinates.

    Returns the respective `char_info`

    `char_info['sprite']` returns codepoint for sprite

    `char_info['mirror']` returns codepoint for mirrored sprite

    `char_info['corpse']` returns codepoint for corpse sprite
    """
    if class_name in g.char_dict:
        return g.char_dict[class_name]

    char_info = {}
    for i in range(0xE001, 0xF8FF+1):
        mirror_i = i + 1
        corpse_i = i + 2
        if i in g.mapped_chars:
            continue
        if mirror_i in g.mapped_chars:
            continue
        if corpse_i in g.mapped_chars:
            continue
        
        values = [i]
        char_info["sprite"] = i
        g.global_tileset.remap(i, char_xy[0], char_xy[1])

        if mirror:
            char_info["mirror"] = mirror_i
            inv_tile = np.flip(g.global_tileset.get_tile(i), axis=1)
            g.global_tileset.set_tile(mirror_i, inv_tile)
            values.append(mirror_i)

        if corpse_xy:
            char_info["corpse"] = corpse_i
            g.global_tileset.remap(corpse_i, corpse_xy[0], corpse_xy[1])
            values.append(corpse_i)

        break
    
    g.mapped_chars.extend(values)
    g.char_dict[class_name] = char_info
    
    return char_info