"""Render the real game view at a chosen kind of place (python tools/world_shots.py [seed] spec ...), into ./shots/w_<spec>.png.

A spec is `biome:<key>`, `landmark:<key>` or `water` (the nearest such open ground to the start is found from the terrain
noise, the player is teleported there in God Mode and the viewport is drawn exactly as in play). Used for before/after pictures
and blind reviews."""
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(ROOT, "src"))
sys.path.insert(0, os.getcwd())
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402

import biomes  # noqa: E402
import characters  # noqa: E402
import debug  # noqa: E402
import input_handlers as ih  # noqa: E402
import landmarks  # noqa: E402
import setup_game  # noqa: E402
import worldgen  # noqa: E402
from session import Session  # noqa: E402

OUT = os.path.join(ROOT, "shots")
os.makedirs(OUT, exist_ok=True)


def find_spot(noise, spec, radius=700):
    """The open-ground tile nearest the origin that satisfies `spec` (searching a coarse grid, then refining)."""
    kind, _, key = spec.partition(":")
    if kind == "at":                    # at:X,Y
        x, y = key.split(",")
        return int(x), int(y)
    best = None
    for y0 in range(-radius, radius, 100):
        for x0 in range(-radius, radius, 100):
            kinds = worldgen.base_terrain(noise, x0, y0, 100, 100)
            env = worldgen.environment_for(noise, x0, y0, 100, 100, kinds)
            if kind == "biome":
                ok = (env["biome"] == biomes.BIOME_IDS.index(key)) & (kinds == 1)
            elif kind == "landmark":
                ok = (env["landmark"] == landmarks.LANDMARK_INDEX[key]) & (env["landmark_strength"] > 0.7) & (kinds == 1)
            else:   # water: open ground that touches a lake
                wet = kinds == 0
                near = np.zeros_like(wet)
                near[1:-1, 1:-1] = wet[2:, 1:-1] | wet[:-2, 1:-1] | wet[1:-1, 2:] | wet[1:-1, :-2]
                ok = near & (kinds == 1)
            xs, ys = np.nonzero(ok[10:-10, 10:-10])
            if len(xs) < 40:
                continue
            k = len(xs) // 2
            cx, cy = x0 + 10 + int(xs[k]), y0 + 10 + int(ys[k])
            d = abs(cx) + abs(cy)
            if best is None or d < best[0]:
                best = (d, cx, cy)
    return None if best is None else best[1:]


def main(args):
    seed = 41
    if args and args[0].isdigit():
        seed, args = int(args[0]), args[1:]
    random.seed(seed)
    if os.environ.get("NO_BLEND"):
        import world
        world.BLEND_BORDERS = False
    session = Session.create(headless=True)
    engine = setup_game.new_game(characters.create_character("Pascal", "human", "survivalist", sponsor="heavy_industries"), session=session)
    engine.session = session
    debug.enable(True)
    debug.toggle_god(engine) if not debug.is_god(engine) else None
    handler = ih.MainGameEventHandler(engine)
    session.handlers = [handler]
    noise = engine.game_world.world_at(0).source.noise
    for spec in args:
        spot = find_spot(noise, spec)
        if spot is None:
            print(spec, "-> not found")
            continue
        debug.teleport(engine, *spot)
        engine.mouse_location = (spot[0] + 4, spot[1])
        session.draw(handler)
        name = "w_" + spec.replace(":", "_").replace(",", "_") + os.environ.get("SHOT_SUFFIX", "")
        pygame.image.save(session.display.surface, os.path.join(OUT, f"{name}.png"))
        print(spec, "->", spot, name)


if __name__ == "__main__":
    main(sys.argv[1:])
