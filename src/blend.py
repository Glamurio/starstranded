"""Soft biome borders for the renderer: the ground colours of neighbouring tiles are eased into each other near a border,
while the tile-to-tile speckle (the small differences within 3x3 tiles) is kept and the sprites are never touched.
Works on the colour arrays of the visible window only, so it costs nothing in the world data and crosses chunk borders."""
from typing import Tuple

import numpy as np

RADIUS = 3          # the ease reaches this many tiles from a border
LIMIT = 150         # tiles whose backgrounds differ by more than this (summed over r, g, b) are different things (a floor, a road), not a border
SAME = 45           # tiles within this of each other are the same ground: their small differences are the speckle to keep
STEP = 4            # the change is rounded to this, so a border adds few distinct tile graphics to the cache


def soften(bg: np.ndarray, fg: np.ndarray, ground: np.ndarray, radius: int = RADIUS) -> Tuple[np.ndarray, np.ndarray]:
    """`(bg, fg)` with the ground colours of `ground` tiles (bool (w, h)) eased across biome borders.
    `bg` / `fg` are (w, h, 3) ints; a tile becomes the wide average of its neighbours plus its own difference from the average of its like neighbours; tiles outside `ground` come back unchanged."""
    w, h = ground.shape
    if not ground.any():
        return bg, fg
    bgf, fgf = bg.astype(np.float32), fg.astype(np.float32)
    pad = ((radius, radius), (radius, radius), (0, 0))
    bgp, fgp = np.pad(bgf, pad, mode="edge"), np.pad(fgf, pad, mode="edge")
    gp = np.pad(ground, ((radius, radius), (radius, radius)))
    sums = {r: [np.zeros((w, h, 3), np.float32), np.zeros((w, h, 3), np.float32), np.zeros((w, h), np.float32)] for r in (1, radius)}
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            sl = (slice(radius + dx, radius + dx + w), slice(radius + dy, radius + dy + h))
            gap = np.abs(bgp[sl] - bgf).sum(axis=-1)
            both = gp[sl] & ground
            for r, (bg_sum, fg_sum, count) in sums.items():
                if abs(dx) <= r and abs(dy) <= r:
                    near = both & (gap <= (SAME if r == 1 else LIMIT))
                    bg_sum += np.where(near[..., None], bgp[sl], 0.0)
                    fg_sum += np.where(near[..., None], fgp[sl], 0.0)
                    count += near
    small_bg, small_fg, small_n = sums[1]
    big_bg, big_fg, big_n = sums[radius]
    n_small, n_big = np.maximum(small_n, 1)[..., None], np.maximum(big_n, 1)[..., None]
    shift_bg = big_bg / n_big - small_bg / n_small
    shift_fg = big_fg / n_big - small_fg / n_small
    move = ground[..., None]
    shift_bg = np.where(move, np.round(shift_bg / STEP) * STEP, 0)
    shift_fg = np.where(move, np.round(shift_fg / STEP) * STEP, 0)
    return (np.clip(bgf + shift_bg, 0, 255).astype(bg.dtype), np.clip(fgf + shift_fg, 0, 255).astype(fg.dtype))
