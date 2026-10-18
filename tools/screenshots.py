"""Render the game's screens headlessly to PNG files (run from the repository root: python tools/screenshots.py [names...]).

Used to look at the UI without opening a window; the files land in ./shots (ignored by git)."""
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(ROOT, "src"))
sys.path.insert(0, os.getcwd())
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import characters  # noqa: E402
import input_handlers as ih  # noqa: E402
import setup_game  # noqa: E402
from events import Key, KeyDown  # noqa: E402
from session import Session  # noqa: E402

OUT = os.path.join(ROOT, "shots")
os.makedirs(OUT, exist_ok=True)
SESSION = Session.create(headless=True)


def shot(name, handler):
    SESSION.draw(handler)
    pygame.image.save(SESSION.display.surface, os.path.join(OUT, name + ".png"))


def press(handler, key):
    return handler.handle_events(KeyDown(key, 0))


def game():
    random.seed(41)
    engine = setup_game.new_game(characters.create_character("Pascal", "human", "survivalist", sponsor="heavy_industries"), session=SESSION) \
        if "session" in setup_game.new_game.__code__.co_varnames else setup_game.new_game(characters.create_character("Pascal", "human", "survivalist", sponsor="heavy_industries"))
    engine.session = SESSION
    return engine


def crafting_view(engine, main_handler):
    import crafting
    import species as defs
    from items import DEFAULT_WOOD
    p = engine.player
    for _ in range(4):
        p.inventory.add(crafting.Branch(substance=DEFAULT_WOOD, parent=p.inventory))
    handler = press(main_handler, Key.R)
    return handler


def creation():
    cc = setup_game.CharacterCreation(SESSION)
    cc.player.set_name("Pascal")
    cc.step = 1
    return cc


def tooltip(engine, main_handler):
    import world
    from components.unit import Unit
    kind = next(k for k in engine.game_world.planet.fauna if k.hide is not None)
    animal = Unit(kind)
    animal.place(engine.player.x + 3, engine.player.y - 2, engine.game_map)
    animal.hp = animal.max_hp // 2
    engine.update_fov()
    engine.mouse_location = (animal.x, animal.y)
    return main_handler


def main(names):
    engine = game()
    main_handler = ih.MainGameEventHandler(engine)
    SESSION.handlers = [main_handler]
    screens = {
        "game": lambda: main_handler,
        "inventory": lambda: press(main_handler, Key.I),
        "crafting": lambda: crafting_view(engine, main_handler),
        "character": lambda: press(main_handler, Key.C),
        "codex": lambda: press(main_handler, Key.O),
        "help": lambda: press(main_handler, Key.H),
        "navigation": lambda: press(main_handler, Key.M),
        "history": lambda: press(main_handler, Key.V),
        "tooltip": lambda: tooltip(engine, main_handler),
        "pickup": lambda: press(main_handler, Key.G),
        "menu": lambda: setup_game.MainMenu(SESSION),
        "settings": lambda: setup_game.SettingsMenu(SESSION),
        "creation": lambda: creation(),
    }
    for name in names or screens:
        try:
            handler = screens[name]()
            if handler is None:
                print(name, "-> no screen")
                continue
            shot(name, handler)
            print(name, "ok", type(handler).__name__)
        except Exception as exc:  # keep going: a broken screen is what we want to see
            import traceback
            traceback.print_exc()
            print(name, "FAILED", exc)


if __name__ == "__main__":
    main(sys.argv[1:])
