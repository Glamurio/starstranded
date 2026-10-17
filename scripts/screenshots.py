#!/usr/bin/env python3
"""Render every screen of the game headless (pygame, SDL dummy driver) and save PNGs of the logical screen.

Usage: python scripts/screenshots.py [outdir]        (default: docs/phase3)

The screens are reached the way a player reaches them: through the handlers, fed with synthetic key and
mouse events. The Phase 0 tcod screenshots are kept in docs/baseline for comparison.
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "docs" / "phase3"
OUT.mkdir(parents=True, exist_ok=True)
os.chdir(SRC)

import numpy as np  # noqa: E402

import g  # noqa: E402
import input_handlers as ih  # noqa: E402
import setup_game  # noqa: E402
from events import Key, KeyDown, Mod, MouseButton, MouseButtonDown, MouseMotion, Point, TextInput  # noqa: E402


def shot(handler, name: str) -> None:
    g.draw(handler)
    path = OUT / f"{name}.png"
    g.display.save_screenshot(str(path))
    print("saved", path)


def press(handler, key, mod=0):
    return handler.handle_events(KeyDown(key, mod))


def main() -> None:
    g.init(headless=True)
    random.seed(7)
    np.random.seed(7)

    menu = setup_game.MainMenu()
    g.draw(menu)
    press(menu, Key.DOWN)
    shot(menu, "main_menu")

    creation = setup_game.CharacterCreation()
    creation.player.set_name("")
    for ch in "Ardan":
        creation.handle_events(TextInput(ch))
    shot(creation, "character_creation")

    engine = setup_game.new_game(creation.player)
    game = ih.MainGameEventHandler(engine)
    g.handlers = [game]
    player = engine.player
    # a few turns so the message log has content
    for key in (Key.RIGHT, Key.RIGHT, Key.DOWN, Key.SPACE):
        game = press(game, key)
    engine.message_log.add_message("You hear something rustle in the shrubs.")
    engine.message_log.add_message("A rabbit hops away.")
    game.handle_events(MouseMotion(Point(player.x + 6, player.y + 3)))
    shot(game, "in_game")

    inventory = press(game, Key.I)
    g.draw(inventory)
    press(inventory, Key.DOWN)
    shot(inventory, "inventory")
    press(inventory, Key.ESCAPE)

    # loot window: a rabbit corpse carrying meat, one tile from the player
    from components.consumable import Meat
    from components.unit import Animal
    rabbit = Animal()
    rabbit.place(player.x + 1, player.y, engine.game_map)
    rabbit.hp = 0
    rabbit.die(None)
    rabbit.inventory.add(Meat("rabbit", rabbit.inventory))
    engine.mouse_location = Point(player.x + 1, player.y)
    engine.update_fov()
    pickup = press(game, Key.G)
    g.draw(pickup)
    loot = press(pickup, Key.G)
    g.draw(loot)
    press(loot, Key.DOWN)
    shot(loot, "loot_window")
    g.handlers = [game]

    area = ih.AreaRangedAttackHandler(engine, 2, lambda xy: None)
    g.handlers = [game, area]
    engine.mouse_location = Point(player.x + 4, player.y + 2)
    shot(area, "targeting_area")
    g.handlers = [game]

    look = press(game, Key.PERIOD)
    press(look, Key.RIGHT, Mod.LSHIFT)
    shot(look, "look")
    g.handlers = [game]

    shot(ih.HistoryViewer(engine), "history_viewer")
    shot(ih.CharacterScreenEventHandler(engine), "character_screen")
    shot(ih.CraftingMenuHandler(engine), "crafting")

    player.level.current_xp = player.level.experience_to_next_level + 1
    shot(ih.LevelUpEventHandler(engine), "level_up")

    shot(ih.PopupMessage(game, "Failed to load save:\nVersion mismatch"), "popup")
    player.hp = 0
    shot(ih.GameOverEventHandler(engine), "game_over")


if __name__ == "__main__":
    main()
