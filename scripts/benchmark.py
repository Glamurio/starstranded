#!/usr/bin/env python3
"""Headless benchmark for StarStranded.

Run from anywhere:   python scripts/benchmark.py [--json out.json] [--quick]
Uses SDL's dummy video driver, so no window or display is needed.

Sections (all numbers are milliseconds unless noted):
  floor_generation   one full GameWorld.generate_floor() (terrain + vegetation + monsters/items)
  spawn_trees_x500   spawning 500 Trees of one species onto an empty map (was: deepcopy of a prototype)
  turn_*             one full turn = player WaitAction + every AI, with N extra units
                     (passive = idle rabbits, hungry = rabbits seeking food, hostile = Selenites chasing)
  pathfinding        Engine.get_path_to corner to corner
  fov                Engine.update_fov
  render_*           one frame of the in-game view (with_present includes vsync wait)
  save_load          Engine.save_as + load_game, plus file size in KiB
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
os.chdir(SRC)

import numpy as np  # noqa: E402

import setup_game  # noqa: E402  (import first: resolves circular import order)
import actions  # noqa: E402
import input_handlers  # noqa: E402


def timed(fn, repeat: int) -> dict:
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return {
        "median": round(statistics.median(samples), 3),
        "mean": round(statistics.fmean(samples), 3),
        "min": round(min(samples), 3),
        "max": round(max(samples), 3),
        "n": repeat,
    }


def fresh_engine(seed: int = 7):
    random.seed(seed)
    np.random.seed(seed)
    return setup_game.new_game(setup_game.create_player())


def free_tile(engine):
    m = engine.game_map
    while True:
        x, y = random.randrange(m.width), random.randrange(m.height)
        if m.tiles["walkable"][x, y] and not m.get_entities_at_location(x, y, True):
            return x, y


def bench_floor_generation(repeat: int) -> dict:
    engine = fresh_engine()
    return timed(engine.game_world.generate_floor, repeat)


def bench_spawn_trees(repeat: int) -> dict:
    """Time spawning 500 Trees of one species onto a fresh all-floor map (setup is untimed)."""
    import tile_types
    from components.plant import Tree
    from species import PlantCategory, make_plant_species
    from world import GameMap

    engine = fresh_engine()
    w, h = engine.game_map.width, engine.game_map.height
    species = make_plant_species(PlantCategory.TREE)
    samples = []
    for _ in range(repeat):
        landscape = np.full((w, h), tile_types.floor.get_array(), dtype=tile_types.tile_dt, order="F")
        blank = GameMap(engine, landscape)
        spots = [divmod(i, h) for i in random.sample(range(w * h), 500)]
        t0 = time.perf_counter()
        for x, y in spots:
            blank.add_entity(Tree(species), x, y)
        samples.append((time.perf_counter() - t0) * 1000)
    return {
        "median": round(statistics.median(samples), 3), "mean": round(statistics.fmean(samples), 3),
        "min": round(min(samples), 3), "max": round(max(samples), 3), "n": repeat,
    }


def bench_turn(kind: str, n: int, turns: int) -> dict:
    """kind: passive (idle/wandering rabbits), hungry (rabbits seeking food), hostile (selenites chasing)."""
    from components.unit import Animal, Selenite

    engine = fresh_engine()
    cls = Selenite if kind == "hostile" else Animal
    for i in range(n):
        # Pass a name: Selenite() otherwise calls generate_name(), which re-parses every namegen
        # file per call (a Phase 1 bug) and would make *setup* take minutes. Not part of the timing.
        u = Selenite(name=f"S{i}") if cls is Selenite else cls()
        x, y = free_tile(engine)
        u.place(x, y, engine.game_map)
        if kind == "hungry":
            u.hunger = u.thirst = 40  # <= 90 makes PassiveAI.seek_food run every turn
    player = engine.player
    total = len(engine.game_map.entities)

    def one_turn():
        actions.WaitAction(player).perform()

    out = timed(one_turn, turns)
    out["entities_total"] = total
    return out


def bench_pathfinding(repeat: int) -> dict:
    engine = fresh_engine()
    engine.game_map.explored[:] = True
    engine.player.place(0, 0)
    return timed(lambda: engine.get_path_to(engine.player, engine.game_map.width - 1, engine.game_map.height - 1), repeat)


def bench_fov(repeat: int) -> dict:
    engine = fresh_engine()
    return timed(engine.update_fov, repeat)


def bench_render(repeat: int) -> dict:
    """Frame cost. 'engine_render' draws to the console only; 'full_frame' also presents via SDL."""
    import g

    engine = fresh_engine()
    handler = input_handlers.MainGameEventHandler(engine)
    g.handlers = [handler]
    def console_only():
        g.root_console.clear()
        handler.on_render(g.root_console)

    def to_texture():
        # Everything g.render() does except present(), which blocks on vsync (~16.7 ms) and
        # would swamp the CPU cost we want to compare across phases.
        console_only()
        g.sdl_renderer.copy(g.console_render.render(g.root_console))

    return {
        "engine_render": timed(console_only, repeat),
        "frame_no_present": timed(to_texture, repeat),
        "frame_with_present": timed(lambda: g.render(handler), max(3, repeat // 5)),
    }


def bench_save_load(repeat: int) -> dict:
    engine = fresh_engine()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bench.sav")
        res = {
            "save": timed(lambda: engine.save_as(path), repeat),
            "load": timed(lambda: setup_game.load_game(path), repeat),
        }
        res["size_kib"] = round(os.path.getsize(path) / 1024, 1)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write results to this JSON file")
    ap.add_argument("--quick", action="store_true", help="fewer repetitions")
    args = ap.parse_args()
    q = 0.25 if args.quick else 1.0

    def r(n: int) -> int:
        return max(3, int(n * q))

    results: dict = {}
    results["floor_generation"] = bench_floor_generation(r(20))
    results["spawn_trees_x500"] = bench_spawn_trees(r(5))
    for kind in ("passive", "hungry", "hostile"):
        for n in (10, 50, 200):
            # 15 turns only: passive rabbits turn hungry after ~20 turns and would change regime.
            results[f"turn_{kind}_{n}"] = bench_turn(kind, n, 15 if not args.quick else 8)
    results["pathfinding"] = bench_pathfinding(r(100))
    results["fov"] = bench_fov(r(100))
    results["render"] = bench_render(r(100))
    results["save_load"] = bench_save_load(r(10))

    print(f"{'benchmark':<28}{'median':>10}{'mean':>10}{'min':>10}{'max':>10}  n")
    def row(name, d):
        print(f"{name:<28}{d['median']:>10.3f}{d['mean']:>10.3f}{d['min']:>10.3f}{d['max']:>10.3f}  {d['n']}")
    for name, d in results.items():
        if "median" in d:
            row(name, d)
        else:
            for sub, dd in d.items():
                if isinstance(dd, dict):
                    row(f"{name}.{sub}", dd)
                else:
                    print(f"{name}.{sub:<20}{dd:>10}")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
