"""A contact sheet of generated names with their sprites, for naming review (python tools/name_sheet.py [seed] [culture]).

Writes shots/names_<seed>_<n>.png: each cell holds the sprite in the colour it is drawn with and its name beneath. A reviewer
sees only these pictures, with no rules to hand."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(ROOT, "src"))
sys.path.insert(0, os.getcwd())
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import atlas  # noqa: E402
import planet as pl  # noqa: E402
from session import Session  # noqa: E402
from tile_types import sprite_id  # noqa: E402

OUT = os.path.join(ROOT, "shots")
os.makedirs(OUT, exist_ok=True)
SUFFIX = os.environ.get("CREATURES", "")
SCALE, CELL_W, CELL_H, COLS = 3, 150, 112, 6


def cells(planet):
    for s in planet.flora:
        yield s.sprite, s.color, s.name, s.category.name.lower()
        if s.fruit is not None:
            yield s.fruit.sprite, s.fruit.color, s.fruit.species, "fruit of " + s.name
    for f in planet.fauna:
        yield f.sprite, f.color, f.name, "creature"


def main(seed=7, culture="human"):
    Session.create(headless=True)
    sheet_atlas = atlas.get_atlas()
    font = pygame.font.Font(None, 17)
    planet = pl.generate_planet(seed, culture)
    items = list(cells(planet))
    if os.environ.get("CREATURES"):
        items = [i for i in items if i[3] == "creature"]
    per = COLS * 6
    for page in range(0, len(items), per):
        chunk = items[page:page + per]
        rows = (len(chunk) + COLS - 1) // COLS
        surface = pygame.Surface((COLS * CELL_W, rows * CELL_H))
        surface.fill((30, 30, 36))
        for n, (sprite, colour, name, note) in enumerate(chunk):
            x, y = (n % COLS) * CELL_W, (n // COLS) * CELL_H
            picture = pygame.transform.scale(sheet_atlas.get(sprite_id(*sprite), False, tuple(colour)), (24 * SCALE, 24 * SCALE))
            surface.blit(picture, (x + (CELL_W - 24 * SCALE) // 2, y + 4))
            for k, text in enumerate((name, note)):
                label = font.render(text[:26], True, (235, 235, 235) if k == 0 else (140, 140, 150))
                surface.blit(label, (x + (CELL_W - label.get_width()) // 2, y + 80 + k * 14))
        path = os.path.join(OUT, f"names_{seed}_{page // per}{SUFFIX}.png")
        pygame.image.save(surface, path)
        print(path)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 7, sys.argv[2] if len(sys.argv) > 2 else "human")
