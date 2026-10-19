#!/usr/bin/env python3
"""Render every screen of the game headless (pygame, SDL dummy driver) and save PNGs of the logical screen.

Usage: python scripts/screenshots.py [outdir]        (default: docs/phase3)

The screens are reached the way a player reaches them: through the handlers, fed with synthetic key and
mouse events. The last part renders the Phase 4 sprite stacks as zoomed crops (`layering_*.png`). The Phase 0 tcod screenshots are kept in docs/baseline for comparison.
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

import session as session_module  # noqa: E402
import input_handlers as ih  # noqa: E402
import setup_game  # noqa: E402
from events import Key, KeyDown, Mod, MouseButton, MouseButtonDown, MouseMotion, Point, TextInput  # noqa: E402


UI = session_module.Session.create(headless=True)
session_module.detached = lambda: UI  # every engine below draws on this window


def shot(handler, name: str) -> None:
    UI.draw(handler)
    path = OUT / f"{name}.png"
    UI.display.save_screenshot(str(path))
    print("saved", path)


def press(handler, key, mod=0):
    return handler.handle_events(KeyDown(key, mod))


def shot_zoom(handler, name: str, center, radius: int = 5, scale: int = 5) -> None:
    """Draw the whole screen, then save a `scale`x enlarged crop of the cells around `center` (the stack tests)."""
    import pygame
    from atlas import TILE

    UI.draw(handler)
    cx, cy = center
    area = pygame.Rect((cx - radius) * TILE, (cy - radius) * TILE, (2 * radius + 1) * TILE, (2 * radius + 1) * TILE)
    crop = UI.display.surface.subsurface(area.clip(UI.display.surface.get_rect())).copy()
    big = pygame.transform.scale(crop, (crop.get_width() * scale, crop.get_height() * scale))
    path = OUT / f"{name}.png"
    pygame.image.save(big, str(path))
    print("saved", path)


def flat_world(width: int = 24, height: int = 14):
    """An all-floor map with the player at (3, 3): a clean stage for the layering shots."""
    import tile_types
    from engine import Engine
    from world import GameMap, GameWorld

    player = setup_game.create_player()
    engine = Engine(player=player)
    engine.game_world = GameWorld(engine=engine, map_width=width, map_height=height, max_rooms=1, room_min_size=1, room_max_size=2)
    landscape = np.full((width, height), fill_value=tile_types.floor.get_array(), order="F", dtype=tile_types.tile_dt)
    engine.game_map = GameMap(engine, landscape, entities=[player])
    player.place(3, 3, engine.game_map)
    engine.update_fov()
    return engine


def layering_shots() -> None:
    """Phase 4: sprite stacks. A corpse and an item under the player and under an animal; a pile with the clutter
    safeguard on and off."""
    from components.consumable import Meat
    from components.plant import Shrub, Tree
    from components.unit import Selenite as Animal   # the rabbit is gone; Selenites stand in
    from config import GameConfig

    def corpse(engine, x, y):
        animal = Animal()
        animal.place(x, y, engine.game_map)
        animal.hp = 0
        animal.die(None)
        return animal

    engine = flat_world()
    game = ih.MainGameEventHandler(engine)
    UI.handlers = [game]
    gm = engine.game_map
    player = engine.player
    corpse(engine, player.x, player.y)
    Meat("rabbit").place(player.x, player.y, gm)
    # an animal on its own corpse + item
    corpse(engine, 8, 3)
    Meat("rabbit").place(8, 3, gm)
    Animal().place(8, 3, gm)
    # shrub + animal, and a tree for reference
    Shrub().place(12, 3, gm)
    Animal().place(12, 3, gm)
    Tree().place(15, 3, gm)
    # a pile: 2 corpses, 5 items (+ a unit on top in the second one)
    for x in (4, 10):
        for _ in range(2):
            corpse(engine, x, 8)
        for _ in range(5):
            Meat("rabbit").place(x, 8, gm)
    Animal().place(10, 8, gm)
    engine.update_fov()
    engine.mouse_location = Point(player.x, player.y)
    shot_zoom(game, "layering_player_on_corpse_and_item", (player.x + 3, 3), radius=6)
    engine.mouse_location = Point(8, 3)
    shot(game, "layering_names_top_first")
    engine.mouse_location = Point(4, 8)
    shot_zoom(game, "layering_pile_safeguard_on", (7, 8), radius=5)
    engine.config = GameConfig(clutter_safeguard=False)
    shot_zoom(game, "layering_pile_safeguard_off", (7, 8), radius=5)


def main() -> None:
    random.seed(7)
    np.random.seed(7)

    menu = setup_game.MainMenu(UI)
    UI.draw(menu)
    press(menu, Key.DOWN)
    shot(menu, "main_menu")

    creation = setup_game.CharacterCreation(UI)
    creation.player.set_name("")
    for ch in "Ardan":
        creation.handle_events(TextInput(ch))
    shot(creation, "character_creation")

    engine = setup_game.new_game(creation.player)
    game = ih.MainGameEventHandler(engine)
    UI.handlers = [game]
    player = engine.player
    # a few turns so the message log has content
    for key in (Key.RIGHT, Key.RIGHT, Key.DOWN, Key.SPACE):
        game = press(game, key)
    engine.message_log.add_message("You hear something rustle in the shrubs.")
    engine.message_log.add_message("A rabbit hops away.")
    game.handle_events(MouseMotion(Point(player.x + 6, player.y + 3)))
    shot(game, "in_game")

    inventory = press(game, Key.I)
    UI.draw(inventory)
    press(inventory, Key.DOWN)
    shot(inventory, "inventory")
    press(inventory, Key.ESCAPE)

    # loot window: a Selenite corpse carrying meat, one tile from the player
    from components.consumable import Meat
    from components.unit import Selenite
    rabbit = Selenite()
    rabbit.place(player.x + 1, player.y, engine.game_map)
    rabbit.hp = 0
    rabbit.die(None)
    rabbit.inventory.add(Meat("rabbit", rabbit.inventory))
    engine.mouse_location = Point(player.x + 1, player.y)
    engine.update_fov()
    pickup = press(game, Key.G)
    UI.draw(pickup)
    loot = press(pickup, Key.G)
    UI.draw(loot)
    press(loot, Key.DOWN)
    shot(loot, "loot_window")
    UI.handlers = [game]

    area = ih.AreaRangedAttackHandler(engine, 2, lambda xy: None)
    UI.handlers = [game, area]
    engine.mouse_location = Point(player.x + 4, player.y + 2)
    shot(area, "targeting_area")
    UI.handlers = [game]

    look = press(game, Key.PERIOD)
    press(look, Key.RIGHT, Mod.LSHIFT)
    shot(look, "look")
    UI.handlers = [game]

    shot(ih.HistoryViewer(engine), "history_viewer")
    shot(ih.CharacterScreenEventHandler(engine), "character_screen")
    shot(ih.CraftingMenuHandler(engine), "crafting")

    player.level.current_xp = player.level.experience_to_next_level + 1
    shot(ih.LevelUpEventHandler(engine), "level_up")

    shot(ih.PopupMessage(game, "Failed to load save:\nVersion mismatch"), "popup")
    player.hp = 0
    shot(ih.GameOverEventHandler(engine), "game_over")

    layering_shots()


if __name__ == "__main__":
    main()
