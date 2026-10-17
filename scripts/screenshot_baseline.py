#!/usr/bin/env python3
"""Render frames of the (tcod-rendered) game headless and save PNGs.

Usage: python scripts/screenshot_baseline.py [outdir]     (default: docs/baseline)
Needs pygame-ce only for PNG encoding (dev convenience, not a runtime dependency of this script's logic).
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs" / "baseline"
OUT.mkdir(parents=True, exist_ok=True)
os.chdir(SRC)

import numpy as np  # noqa: E402
import pygame  # noqa: E402

import setup_game  # noqa: E402
import input_handlers  # noqa: E402
import g  # noqa: E402
import main as game_main  # noqa: E402
import tcod  # noqa: E402


def shot(handler, name: str) -> None:
    g.render(handler)
    px = g.sdl_renderer.read_pixels()  # (h, w, 4) RGBA
    surf = pygame.image.frombuffer(np.ascontiguousarray(px[:, :, :3]).tobytes(), (px.shape[1], px.shape[0]), "RGB")
    pygame.image.save(surf, str(OUT / f"{name}.png"))
    print("saved", OUT / f"{name}.png")


def main() -> None:
    # Same startup step as main.main(): merge the CP437 text tiles into the sprite tileset.
    text_tileset = tcod.tileset.load_tilesheet("Zesty_curses_24x24.png", 16, 16, tcod.tileset.CHARMAP_CP437)
    game_main.merge_tileset(g.global_tileset, text_tileset, tcod.tileset.CHARMAP_CP437)
    random.seed(7)
    np.random.seed(7)
    shot(setup_game.MainMenu(), "main_menu")
    shot(setup_game.CharacterCreation(), "character_creation")
    engine = setup_game.new_game(setup_game.create_player())
    game = input_handlers.MainGameEventHandler(engine)
    g.handlers = [game]
    shot(game, "in_game")
    g.handlers = [game, input_handlers.InventoryActivateHandler(engine, engine.player.inventory)]
    shot(g.handlers[-1], "inventory")
    g.handlers = [game]
    shot(input_handlers.HistoryViewer(engine), "history_viewer")
    shot(input_handlers.CharacterScreenEventHandler(engine), "character_screen")


if __name__ == "__main__":
    main()
