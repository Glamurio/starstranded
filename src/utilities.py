# Utility functions
from __future__ import annotations

import os
import random

import numpy as np # type: ignore
from typing import TYPE_CHECKING, Dict, Optional, Tuple, List

from events import Point

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


def get_random_color(threshold: int = 30, rng: random.Random = random) -> Tuple[int, int, int]:
    """Gets random color, excluding colors that exceed `threshold`"""
    return (int(max((255 * rng.random()), threshold)), int(max((255 * rng.random()), threshold)), int(max((255 * rng.random()), threshold)))


def get_shade(color: tuple[float, float, float], factor: float = -0.5):
    """Get shade reduced or increased by `factor`"""
    N = 1 + factor
    shade = (int(color[0] * N), int(color[1] * N), int(color[2] * N))
    return (clamp(shade[0], 0, 255), clamp(shade[1], 0, 255), clamp(shade[2], 0, 255))


def get_gaussian_shade(color: tuple[float, float, float], sigma: float = 20):
    """Get gaussian average of `color` as a shade, with a deviation of `sigma`"""
    shade = (int(random.gauss(color[0], sigma)), int(random.gauss(color[1], sigma)), int(random.gauss(color[2], sigma)))
    return (clamp(shade[0], 0, 255), clamp(shade[1], 0, 255), clamp(shade[2], 0, 255))


def is_mouse_in_rectangle(mouse, point, width: int, height: int) -> bool:
    """
    Check if current mouse position (an event with a cell `position`) is within a rectangle of given
    `width` and `height` and return True or False.

    `point` indicates the center of the rectangle.
    """
    mouse_pt = Point(int(mouse.position.x), int(mouse.position.y))

    return (point.x - width // 2) < (mouse_pt.x) and (point.x + width // 2) > (mouse_pt.x) \
        and (point.y - height // 2) < (mouse_pt.y) and (point.y + height // 2) > (mouse_pt.y)


# generate_name now lives in namegen.py (pure Python, cached); re-exported for existing callers.
from namegen import generate_name  # noqa: E402,F401
