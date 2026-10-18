#!/usr/bin/env python3
"""Merge the official Urizen sheet with the project's own sprites into the game's sprite sheet.

Inputs  (tilesets/):  urizen_source.png      the official sheet: 12 px sprites on a 13 px grid, four sections of 25 columns
                                             separated by magenta columns (the grid lines are transparent)
                      legacy/urizen_nogrid_white.png   the sheet the game used before: 50x50 sprites of 24 px (2x the art)
Outputs:              src/urizen_white.png   white sprites on transparency, 24 px cells, no grid, no separators:
                                             columns 0-99 are the official sprites in the official order, columns 100-124 hold the
                                             sprites that only the legacy sheet had (cactus, mushrooms, Selenites, wall edges, ...)
                      tilesets/legacy_map.json   legacy (column, row) -> new (column, row), for every legacy cell
                      docs/tileset/sheet_preview.png   the sheet with a coordinate ruler, to pick slots from

A legacy sprite that appears pixel for pixel in the official sheet points there; any other one is copied from the legacy sheet
as it was (at full 24 px resolution) into the custom block, so the game draws exactly what it drew before.

Usage: python scripts/build_tileset.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np  # noqa: E402
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tilesets" / "urizen_source.png"
LEGACY = ROOT / "tilesets" / "legacy" / "urizen_nogrid_white.png"
OUT_SHEET = ROOT / "src" / "urizen_white.png"
OUT_MAP = ROOT / "tilesets" / "legacy_map.json"
OUT_PREVIEW = ROOT / "docs" / "tileset" / "sheet_preview.png"

SRC_PITCH, SRC_ART, SCALE = 13, 12, 2
TILE = SRC_ART * SCALE
SECTION = 25
NOISE = 7
"""Source pixels darker than this (r+g+b) are the black background, not sprite."""
CUSTOM_FIRST_COLUMN = 100
COLUMNS, ROWS = 125, 50


def load_rgba(path: Path) -> np.ndarray:
    surface = pygame.image.load(str(path))
    rgb = pygame.surfarray.array3d(surface).transpose(1, 0, 2).astype(np.int32)
    alpha = (pygame.surfarray.array_alpha(surface).T if surface.get_flags() & pygame.SRCALPHA
             else np.full(rgb.shape[:2], 255)).astype(np.int32)
    return np.dstack([rgb, alpha])


def source_masks(path: Path = SOURCE) -> dict:
    """`{(column, row): 12x12 bool mask}` of the official sprites, columns counted without the separators."""
    image = load_rgba(path)
    grid_columns = (image.shape[1] - 1) // SRC_PITCH
    rows = (image.shape[0] - 1) // SRC_PITCH
    masks, column = {}, 0
    for grid_column in range(grid_columns):
        x0 = 1 + SRC_PITCH * grid_column
        top = image[1:1 + SRC_ART, x0:x0 + SRC_ART]
        if (top[..., 0] == 255).all() and (top[..., 1] == 0).all() and (top[..., 2] == 255).all():
            continue  # a separator column
        for row in range(rows):
            y0 = 1 + SRC_PITCH * row
            cell = image[y0:y0 + SRC_ART, x0:x0 + SRC_ART]
            masks[(column, row)] = (cell[..., :3].sum(axis=2) >= NOISE) & (cell[..., 3] >= 128)
        column += 1
    return masks


def legacy_masks(path: Path = LEGACY) -> dict:
    image = load_rgba(path)
    bright = image[..., :3].sum(axis=2) >= 384
    return {(c, r): bright[TILE * r:TILE * (r + 1), TILE * c:TILE * (c + 1)] for r in range(50) for c in range(50)}


def merge():
    official = source_masks()
    legacy = legacy_masks()
    index = {}
    for key in sorted(official, key=lambda k: (k[1], k[0])):
        mask = official[key]
        if mask.any():
            index.setdefault(np.kron(mask, np.ones((SCALE, SCALE), bool)).tobytes(), key)

    sheet = np.zeros((ROWS * TILE, COLUMNS * TILE), bool)
    for (c, r), mask in official.items():
        sheet[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = np.kron(mask, np.ones((SCALE, SCALE), bool))

    mapping, custom = {}, []
    for (c, r) in sorted(legacy, key=lambda k: (k[1], k[0])):
        mask = legacy[(c, r)]
        if not mask.any():
            continue
        hit = index.get(mask.tobytes())
        if hit is not None:
            mapping[(c, r)] = hit
        else:
            slot = (CUSTOM_FIRST_COLUMN + len(custom) % SECTION, len(custom) // SECTION)
            custom.append(((c, r), slot))
            mapping[(c, r)] = slot
            sheet[slot[1] * TILE:(slot[1] + 1) * TILE, slot[0] * TILE:(slot[0] + 1) * TILE] = mask
    blank = (COLUMNS - 1, ROWS - 1)
    assert not sheet[blank[1] * TILE:, blank[0] * TILE:].any()
    for key in legacy:
        mapping.setdefault(key, blank)
    return sheet, mapping, custom


def write_sheet(sheet: np.ndarray) -> None:
    surface = pygame.Surface((sheet.shape[1], sheet.shape[0]), pygame.SRCALPHA, 32)
    surface.fill((255, 255, 255, 0))
    pygame.surfarray.pixels_alpha(surface)[:] = sheet.T.astype(np.uint8) * 255
    pygame.image.save(surface, str(OUT_SHEET))


def write_preview(sheet: np.ndarray, custom) -> None:
    pygame.font.init()
    font = pygame.font.Font(None, 15)
    margin = 18
    surface = pygame.Surface((COLUMNS * TILE + margin, ROWS * TILE + margin))
    surface.fill((24, 24, 28))
    cells = pygame.Surface((COLUMNS * TILE, ROWS * TILE), pygame.SRCALPHA)
    cells.fill((0, 0, 0, 0))
    pygame.surfarray.pixels_alpha(cells)[:] = sheet.T.astype(np.uint8) * 255
    pygame.surfarray.pixels3d(cells)[:] = 255
    for x in range(0, COLUMNS * TILE, TILE):
        pygame.draw.line(surface, (44, 44, 52), (margin + x, margin), (margin + x, margin + ROWS * TILE))
    for y in range(0, ROWS * TILE, TILE):
        pygame.draw.line(surface, (44, 44, 52), (margin, margin + y), (margin + COLUMNS * TILE, margin + y))
    for boundary in (SECTION, 2 * SECTION, 3 * SECTION, 4 * SECTION):
        pygame.draw.line(surface, (200, 0, 200), (margin + boundary * TILE, margin), (margin + boundary * TILE, margin + ROWS * TILE), 2)
    surface.blit(cells, (margin, margin))
    for c in range(0, COLUMNS, 5):
        surface.blit(font.render(str(c), True, (255, 220, 120)), (margin + c * TILE + 2, 2))
    for r in range(0, ROWS, 5):
        surface.blit(font.render(str(r), True, (255, 220, 120)), (1, margin + r * TILE + 2))
    OUT_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(OUT_PREVIEW))


def main() -> None:
    sheet, mapping, custom = merge()
    write_sheet(sheet)
    write_preview(sheet, custom)
    data = {"columns": COLUMNS, "rows": ROWS, "custom": [{"legacy": list(k), "new": list(v)} for k, v in custom],
            "map": {f"{c},{r}": list(v) for (c, r), v in sorted(mapping.items(), key=lambda kv: (kv[0][1], kv[0][0]))}}
    OUT_MAP.write_text(json.dumps(data, indent=1))
    same = sum(1 for k, v in mapping.items() if v != (COLUMNS - 1, ROWS - 1) and (v[0] < CUSTOM_FIRST_COLUMN))
    print(f"{OUT_SHEET.name}: {sheet.shape[1]}x{sheet.shape[0]} px; {same} legacy sprites found in the official sheet, "
          f"{len(custom)} copied into the custom block")


if __name__ == "__main__":
    main()
