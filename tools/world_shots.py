"""Render the real game view at a chosen kind of place (python tools/world_shots.py [seed] spec ...), into ./shots/w_<spec>.png.

A spec is `biome:<key>`, `family:<key>`, `at:X,Y` or `water` (the nearest such open ground to the start is found from the terrain
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
import setup_game  # noqa: E402
import worldgen  # noqa: E402
from session import Session  # noqa: E402

OUT = os.path.join(ROOT, "shots")
os.makedirs(OUT, exist_ok=True)


def find_spot(noise, spec, radius=3000):
    """An open-ground tile of a place that satisfies `spec` (`biome:KEY`, `family:KEY`, `water`, `at:X,Y`), the nearest region to the start:
    the regions are looked up on a coarse grid, the nearest hit is then refined to a tile in the middle of its open ground."""
    import regions
    kind, _, key = spec.partition(":")
    if kind == "at":                    # at:X,Y
        x, y = key.split(",")
        return int(x), int(y)
    wanted = None
    if kind == "biome":
        wanted = {biomes.BIOME_IDS.index(key)}
    elif kind == "family":
        wanted = {i for i, k in enumerate(biomes.BIOME_IDS) if biomes.BIOMES[k].family == key}
    candidates = []
    step = 60
    for y0 in range(-radius, radius, step):
        for x0 in range(-radius, radius, step):
            if wanted is not None:
                index = biomes.BIOME_IDS.index(regions.biome_at(noise, x0, y0))
                if index not in wanted:
                    continue
            candidates.append((abs(x0) + abs(y0), x0, y0))
    if wanted is None:
        candidates = [(abs(x0) + abs(y0), x0, y0) for y0 in range(-1200, 1200, 100) for x0 in range(-1200, 1200, 100)]
    for _, x0, y0 in sorted(candidates):
        x0, y0 = x0 - 50, y0 - 50
        kinds = worldgen.base_terrain(noise, x0, y0, 100, 100)
        env = worldgen.environment_for(noise, x0, y0, 100, 100, kinds)
        if wanted is not None:
            ok = np.isin(env["biome"], list(wanted)) & (env["edge"] < 0.05) & (kinds == 1)
        else:   # water: open ground that touches a lake
            wet = kinds == 0
            near = np.zeros_like(wet)
            near[1:-1, 1:-1] = wet[2:, 1:-1] | wet[:-2, 1:-1] | wet[1:-1, 2:] | wet[1:-1, :-2]
            ok = near & (kinds == 1)
        xs, ys = np.nonzero(ok[10:-10, 10:-10])
        if len(xs) < 200:
            continue
        k = len(xs) // 2
        return x0 + 10 + int(xs[k]), y0 + 10 + int(ys[k])
    return None


def find_settlement(engine, kind):
    """The centre of the nearest farm (spec `farm`) or town (`town:x`) to the start."""
    import settlements
    from chunks import CHUNK_H, CHUNK_W
    source = engine.game_world.world_at(0).source
    kind = kind or "farm"
    keys = sorted(((x, y) for x in range(-12, 13) for y in range(-12, 13)), key=lambda k: abs(k[0]) + abs(k[1]))
    for key in keys:
        if settlements.kind_of(source.floor_seed, key) == ("farm" if kind == "farm" else "town") and settlements.layout(source.floor_seed, key):
            return key[0] * CHUNK_W + CHUNK_W // 2, key[1] * CHUNK_H + CHUNK_H // 2
    return None


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
        spot = find_settlement(engine, spec[5:]) if spec.startswith("town:") or spec.startswith("farm") else find_spot(noise, spec)
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
