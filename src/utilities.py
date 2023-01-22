# Utility functions
from __future__ import annotations

import os
import tcod
import g
import random

import numpy as np # type: ignore
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Tuple, List

if TYPE_CHECKING:
    pass

# SHADES = {
#     "Black": (0, 0, 0),
#     "White": (128, 128, 128),
#     "White": (255, 255, 255),
#     "Blue": (0, 0, 255),
#     "Magenta": (255, 0, 255),
#     "Red": (255, 0, 0),
#     "Orange": (255, 128, 0),
#     "Pink": (255, 128, 128),
#     "Yellow": (255, 255, 0),
#     "Green": (0, 255, 0),
#     "Brown": (165, 42, 42)
# }

SHADES = {
 'Red': 0,
 'Orange': 30,
 'Yellow': 60,
 'Chartreuse': 90,
 'Green': 120,
 'Emerald': 160,
 'Cyan': 180,
 'Azure': 210,
 'Blue': 240,
 'Violet': 270,
 'Magenta': 300,
 'Rose': 330
}

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


def rgb_to_hsl(r, g, b):
    # Normalize the RGB values
    r /= 255.0
    g /= 255.0
    b /= 255.0

    # Find the minimum and maximum RGB values
    min_val = min(r, g, b)
    max_val = max(r, g, b)

    # Calculate the hue
    if max_val == min_val:
        h = 0
    elif max_val == r:
        h = (60 * (g - b) / (max_val - min_val)) % 360
    elif max_val == g:
        h = 60 * (b - r) / (max_val - min_val) + 120
    elif max_val == b:
        h = 60 * (r - g) / (max_val - min_val) + 240

    # Calculate the lightness
    l = (max_val + min_val) / 2

    # Calculate the saturation
    if l == 0 or max_val == min_val:
        s = 0
    elif l <= 0.5:
        s = (max_val - min_val) / (2 * l)
    else:
        s = (max_val - min_val) / (2 - 2 * l)

    return h, s, l


def get_color_group(rgb: Tuple[int, int, int]):
    # Convert the RGB color to HSL
    h, s, l = rgb_to_hsl(rgb[0], rgb[1], rgb[2])

    # Define the known colors in HSL
    known_colors = {
        'Red': 0,
        'Orange': 30,
        'Yellow': 60,
        'Chartreuse': 90,
        'Green': 120,
        'Emerald': 160,
        'Cyan': 180,
        'Azure': 210,
        'Blue': 240,
        'Violet': 270,
        'Magenta': 300,
        'Rose': 330
    }

    # Check the saturation and lightness of the input color
    if l < 0.1:
        return 'Black'
    elif s <= 0.1 and l <= 0.6:
        return 'Gray'
    elif s < 0.1 and l >= 0.8:
        return 'White'
    elif h == 30 and s < 0.5:
        return 'Brown'

    min_colors = {}
    for key, value in known_colors.items():
        # Calculate the absolute difference between the hue values
        hue_diff = abs(h - value)

        # Find the smallest difference between the hue values
        min_colors[hue_diff] = key

    # Return the name of the known color with the minimum difference
    result = min_colors[min(min_colors.keys())]

    # Group closely matched hues
    blues = ['Blue', 'Azure']
    greens = ['Green', 'Emerald']
    yellows = ['Yellow', 'Chartreuse']

    if result in blues:
        return 'Blue'
    if result in greens:
        return 'Green'
    if result in yellows:
        return 'Yellow'

    return min_colors[min(min_colors.keys())]


def get_random_color(threshold: int = 30) -> Tuple(int, int, int):
    """Gets random color, excluding colors that exceed `threshold`"""
    return (int(max((255 * random.random()), threshold)), int(max((255 * random.random()), threshold)), int(max((255 * random.random()), threshold)))


def get_shade(color: tuple[float, float, float], factor: float = -0.5):
    """Get shade reduced or increased by `factor`"""
    N = 1 + factor
    shade = (int(color[0] * N), int(color[1] * N), int(color[2] * N))
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


def map_codepoints(class_name: str, char_xy: tuple(int, int), mirror = False, corpse_xy: tuple(int, int) = None, variations: List[tuple] = []) -> Dict:
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
    MAX_TILES = g.global_tileset_size[0] * g.global_tileset_size[1]
    i = char_xy[1] * g.global_tileset_size[0] + char_xy[0]
    assert i < MAX_TILES
    char_i = i + 0xE000
    mirror_i = i + 0xE000 + MAX_TILES
    corpse_i = i + 0xE000 + MAX_TILES * 2
        
    values = [char_i]
    char_info["sprite"] = char_i

    g.global_tileset.remap(char_i, char_xy[0], char_xy[1])

    if mirror:
        char_info["mirror"] = mirror_i
        inv_tile = np.flip(g.global_tileset.get_tile(char_i), axis=1)
        g.global_tileset.set_tile(mirror_i, inv_tile)
        values.append(mirror_i)

    if corpse_xy:
        char_info["corpse"] = corpse_i
        g.global_tileset.remap(corpse_i, corpse_xy[0], corpse_xy[1])
        values.append(corpse_i)

    for j, variation in enumerate(variations):
        variation_i = 1 + i + int(mirror) + int(bool(corpse_xy)) + j
        char_info[variation[2]] = variation_i
        g.global_tileset.remap(variation_i, variation[0], variation[1])
        values.append(variation_i)
            
    g.mapped_chars.extend(values)
    g.char_dict[class_name] = char_info
    
    return char_info