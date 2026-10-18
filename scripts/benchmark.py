#!/usr/bin/env python3
"""Headless benchmark for StarStranded.

    python scripts/benchmark.py [--json out.json] [--quick] [--src PATH]

Uses SDL's dummy video driver (no window needed). Everything except `floor_generation` runs on a **fixed scenario**:
the landscape in `scripts/bench_data/scenario_landscape.npy`, a fixed player position, 60 fruiting trees and N units at
positions drawn from fixed seeds. That makes runs comparable across code versions (`--src` points at another checkout's
`src/`, e.g. an older commit extracted with `git archive`; a small adapter covers the pre-Phase-2 API).

Sections (milliseconds unless noted):
  floor_generation   GameWorld.generate_floor() from a seeded RNG (terrain + vegetation + monsters/items)
  spawn_trees_x500   creating and placing 500 trees of one kind on an empty map
  turn_*             one full turn = player WaitAction + every AI, with N extra units
                     (passive = idle rabbits, hungry = rabbits seeking food, hostile = Selenites chasing)
  pathfinding        mean of 300 fixed queries (random unit -> random tile) on the scenario with 100 rabbits
  fov                Engine.update_fov
  render_*           one frame of the in-game view: tcod era = console / texture / present (vsync-capped);
                     Phase 3+ = map only / map + UI / full draw / draw + scale + present
  save_load          Engine.save_as + load_game, plus file size in KiB
  chunked.*          Phase 5: chunk generation / unload / reload, a turn with the NEAR ring populated, a border
                     crossing and the save directory (see bench_chunked). `floor_generation` is 9 chunks since Phase 5.
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

HERE = Path(__file__).resolve().parent
_ap = argparse.ArgumentParser()
_ap.add_argument("--json", help="write results to this JSON file")
_ap.add_argument("--quick", action="store_true", help="fewer repetitions")
_ap.add_argument("--src", default=str(HERE.parent / "src"), help="game source directory to benchmark")
ARGS = _ap.parse_args()
SRC = Path(ARGS.src).resolve()
sys.path.insert(0, str(SRC))
os.chdir(SRC)

import numpy as np  # noqa: E402

import setup_game  # noqa: E402  (import first: resolves circular import order)
import actions  # noqa: E402
import input_handlers  # noqa: E402
import tile_types  # noqa: E402
from world import GameMap  # noqa: E402

NEW_API = hasattr(GameMap, "add_entity")  # Phase 2+: spatial index, species definitions
PYGAME_API = "sprite" in (tile_types.graphic_dt.names or ())  # Phase 3+: pygame-ce rendering, sprite-id tiles
CHUNKED = (SRC / "chunks.py").exists()  # Phase 5+: chunked world
# The scenario terrain exists in both tile layouts (codepoints for the tcod-era code, sprite ids for Phase 3+).
LANDSCAPE = np.load(HERE / "bench_data" / ("scenario_landscape.npy" if PYGAME_API else "scenario_landscape_tcod.npy"))


# ── adapter over the pre-/post-Phase-2 APIs ─────────────────────────────────────────────
def make_map(engine, landscape):
    if NEW_API:
        return GameMap(engine, landscape, entities=[engine.player])
    w, h = landscape.shape
    return GameMap(engine.game_world, landscape, engine, w, h, entities=[engine.player])


def put(game_map, entity, x, y):
    if NEW_API:
        game_map.add_entity(entity, x, y)
    else:
        entity.place(x, y, game_map)


def fruiting_tree_factory():
    from components.plant import Tree
    if NEW_API:
        import dataclasses
        from species import PlantCategory, make_fruit_kind, make_plant_species
        kind = dataclasses.replace(make_plant_species(PlantCategory.TREE), fruit=make_fruit_kind())
        return lambda game_map, x, y: game_map.add_entity(Tree(kind), x, y)
    from components.consumable import Fruit
    proto = Tree()
    proto.fruit = Fruit
    proto.fruit_factory = {"color": (200, 40, 40), "position": (3, 16), "species": "Benchapple"}
    return lambda game_map, x, y: proto.spawn(game_map, x, y)


def path(engine, origin, x, y):
    return engine.get_path_to(origin if NEW_API else origin.ai, x, y)


# ── helpers ────────────────────────────────────────────────────────────────────
def summarize(samples) -> dict:
    return {
        "median": round(statistics.median(samples), 3),
        "mean": round(statistics.fmean(samples), 3),
        "min": round(min(samples), 3),
        "max": round(max(samples), 3),
        "n": len(samples),
    }


def timed(fn, repeat: int) -> dict:
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return summarize(samples)


def seeded_engine(seed: int = 7):
    random.seed(seed)
    np.random.seed(seed)
    return setup_game.new_game(setup_game.create_player())


def scenario(units: int = 0, kind: str = "passive", trees: int = 60):
    """Fixed map + fixed spawn positions. Returns the engine."""
    engine = seeded_engine()
    game_map = make_map(engine, LANDSCAPE.copy())
    engine.game_map = game_map
    free = [(x, y) for x in range(game_map.width) for y in range(game_map.height) if LANDSCAPE["walkable"][x, y]]
    rng = random.Random(11)
    spots = rng.sample(free, trees + units + 1)
    engine.player.place(*spots[0], game_map) if not NEW_API else engine.player.place(*spots[0])
    plant = fruiting_tree_factory()
    for x, y in spots[1 : trees + 1]:
        plant(game_map, x, y)
    from components.unit import Animal, Selenite
    for i, (x, y) in enumerate(spots[trees + 1 :]):
        unit = Selenite(name=f"S{i}") if kind == "hostile" else Animal()
        put(game_map, unit, x, y)
        if kind == "hungry":
            unit.hunger = unit.thirst = 40  # <= 90: PassiveAI.seek_food runs every turn
    engine.update_fov()
    random.seed(99)  # AI randomness starts from the same state in every version
    np.random.seed(99)
    return engine


# ── benchmarks ─────────────────────────────────────────────────────────────────
def bench_floor_generation(repeat: int) -> dict:
    engine = seeded_engine()
    return timed(engine.game_world.generate_floor, repeat)


def bench_spawn_trees(repeat: int) -> dict:
    from components.plant import Tree
    import tile_types
    engine = seeded_engine()
    w, h = LANDSCAPE.shape
    if NEW_API:
        from species import PlantCategory, make_plant_species
        kind = make_plant_species(PlantCategory.TREE)
        create = lambda m, x, y: m.add_entity(Tree(kind), x, y)  # noqa: E731
    else:
        proto = Tree()
        create = lambda m, x, y: proto.spawn(m, x, y)  # noqa: E731
    samples = []
    for _ in range(repeat):
        landscape = np.full((w, h), tile_types.floor.get_array(), dtype=tile_types.tile_dt, order="F")
        blank = make_map(engine, landscape)
        spots = [divmod(i, h) for i in random.sample(range(w * h), 500)]
        t0 = time.perf_counter()
        for x, y in spots:
            create(blank, x, y)
        samples.append((time.perf_counter() - t0) * 1000)
    return summarize(samples)


def bench_turn(kind: str, n: int, turns: int) -> dict:
    engine = scenario(units=n, kind=kind)
    player = engine.player
    out = timed(lambda: actions.WaitAction(player).perform(), turns)
    out["entities_total"] = len(engine.game_map.entities)
    return out


def bench_pathfinding(repeat: int) -> dict:
    engine = scenario(units=100)
    game_map = engine.game_map
    game_map.explored[:] = True
    origins = [u for u in game_map.entities if getattr(u, "ai", None) and hasattr(u, "is_alive")]
    rng = random.Random(5)
    queries = [(rng.choice(origins), rng.randrange(game_map.width), rng.randrange(game_map.height)) for _ in range(300)]

    def run():
        for origin, x, y in queries:
            path(engine, origin, x, y)

    result = timed(run, repeat)
    for key in ("median", "mean", "min", "max"):
        result[key] = round(result[key] / len(queries), 4)  # per query
    return result


def bench_fov(repeat: int) -> dict:
    engine = scenario()
    return timed(engine.update_fov, repeat)


def bench_render(repeat: int) -> dict:
    if PYGAME_API:
        return bench_render_pygame(repeat)
    import g  # the old (tcod) API this branch benchmarks lives in the old checkout
    engine = scenario(units=50)
    handler = input_handlers.MainGameEventHandler(engine)
    g.handlers = [handler]

    def console_only():
        g.root_console.clear()
        handler.on_render(g.root_console)

    def to_texture():
        console_only()
        g.sdl_renderer.copy(g.console_render.render(g.root_console))

    return {
        "engine_render": timed(console_only, repeat),
        "frame_no_present": timed(to_texture, repeat),
        "frame_with_present": timed(lambda: g.render(handler), max(3, repeat // 5)),
    }


def bench_render_pygame(repeat: int) -> dict:
    """Phase 3+ rendering. `map_render` is the terrain + entity blits alone, `engine_render` adds the UI panels,
    `frame_no_present` is a full draw of the screen into the logical surface, `frame_with_present` also scales
    it to the (dummy-driver) window and flips."""
    import session as session_module
    ui = session_module.Session.create(headless=True)
    session_module.detached = lambda: ui  # the engine below shares this window
    engine = scenario(units=50)
    handler = input_handlers.MainGameEventHandler(engine)
    ui.handlers = [handler]
    ui.draw(handler)  # warm the sprite caches: steady-state frames are what matters

    def map_only():
        ui.canvas.clear()
        engine.game_map.render(ui.canvas)

    return {
        "map_render": timed(map_only, repeat),
        "engine_render": timed(lambda: (ui.canvas.clear(), engine.render(ui.canvas)), repeat),
        "frame_no_present": timed(lambda: ui.draw(handler), repeat),
        "frame_with_present": timed(lambda: ui.render(handler), repeat),
    }


def _size_kib(path: str) -> float:
    if os.path.isdir(path):
        return round(sum(os.path.getsize(os.path.join(d, f)) for d, _, files in os.walk(path) for f in files) / 1024, 1)
    return round(os.path.getsize(path) / 1024, 1)


def bench_save_load(repeat: int) -> dict:
    engine = scenario(units=50)
    with tempfile.TemporaryDirectory() as d:
        save_path = os.path.join(d, "bench.sav")
        res = {
            "save": timed(lambda: engine.save_as(save_path), repeat),
            "load": timed(lambda: setup_game.load_game(save_path), repeat),
        }
        res["size_kib"] = _size_kib(save_path)
    return res


# ── Phase 5: chunked world ────────────────────────────────────────────────────────
def bench_chunked(repeat: int, turns: int) -> dict:
    """Seeded floor 1 (3x3 chunks around the start). Sections:
      chunk_generate        one new chunk: terrain + plants + spawns (load of a never-visited chunk)
      chunk_unload/reload   serialise a chunk to bytes / restore it (with catch-up)
      turn_near_ring_0/200  one turn (WaitAction) with the natural spawns / +200 rabbits spread over the 8 NEAR chunks;
                            .near_tick = only the turns on which NEAR chunks are simulated (every 2nd)
      border_crossing       a player step into the next chunk (loads 3 new chunks, unloads beyond unload_radius)
      save_load             the save directory after the crossings (manifest + chunk files)
    """
    import actions
    from chunks import CHUNK_H, CHUNK_W, chebyshev, keys_around
    from components.unit import Animal

    res: dict = {}
    engine = seeded_engine()
    world = engine.game_map
    keys = [(20 + i, 20) for i in range(repeat)]
    samples = []
    for key in keys:
        t0 = time.perf_counter()
        world.load_chunk(key)
        samples.append((time.perf_counter() - t0) * 1000)
    res["chunk_generate"] = summarize(samples)
    res["entities_per_chunk"] = round(sum(len(world.chunks[k].entities) for k in keys) / len(keys), 1)
    unload, reload = [], []
    for key in keys:
        t0 = time.perf_counter()
        world.unload_chunk(key)
        unload.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        world.load_chunk(key)
        reload.append((time.perf_counter() - t0) * 1000)
        world.unload_chunk(key)
    res["chunk_unload"] = summarize(unload)
    res["chunk_reload"] = summarize(reload)
    res["chunk_kib"] = round(sum(len(world.stored[k]) for k in keys) / len(keys) / 1024, 1)
    for key in keys:
        world.stored.pop(key)

    def turn_bench(engine, label):
        all_turns, near_ticks = [], []
        for _ in range(turns):
            t0 = time.perf_counter()
            actions.WaitAction(engine.player).perform()
            ms = (time.perf_counter() - t0) * 1000
            all_turns.append(ms)
            if engine.game_world.current_time % engine.config.near_interval == 0:
                near_ticks.append(ms)
        res[label] = summarize(all_turns)
        res[label + ".near_tick"] = summarize(near_ticks)

    random.seed(99)
    np.random.seed(99)
    turn_bench(engine, "turn_near_ring_0")
    engine = seeded_engine()
    world = engine.game_map
    rng = random.Random(5)
    near = [k for k in world.chunks if chebyshev(k, world.center_key()) == 1]
    for key in near:
        chunk = world.chunks[key]
        placed = 0
        while placed < 25:
            x, y = chunk.x0 + rng.randrange(CHUNK_W), chunk.y0 + rng.randrange(CHUNK_H)
            if engine.can_move(x, y):
                world.add_entity(Animal(), x, y)
                placed += 1
    random.seed(99)
    np.random.seed(99)
    turn_bench(engine, "turn_near_ring_200")

    crossing = []
    player = engine.player
    for _ in range(max(3, repeat // 2)):
        key = world.center_key()
        x = (key[0] + 1) * CHUNK_W  # first column of the next chunk east
        spot = next(((x, y) for y in range(key[1] * CHUNK_H, (key[1] + 1) * CHUNK_H)
                     if world.is_walkable(x, y) and not world.is_blocked(x, y)), None)
        if spot is None:
            break
        player.place(spot[0] - 1, spot[1])  # stand just west of the border (teleport inside loaded chunks)
        t0 = time.perf_counter()
        player.move(*spot)
        crossing.append((time.perf_counter() - t0) * 1000)
    res["border_crossing"] = summarize(crossing)
    with tempfile.TemporaryDirectory() as d:
        save_path = os.path.join(d, "world")
        res["save"] = timed(lambda: engine.save_as(save_path), max(3, repeat // 3))
        res["load"] = timed(lambda: setup_game.load_game(save_path), max(3, repeat // 3))
        res["save_kib"] = _size_kib(save_path)
        res["chunks_saved"] = len(world.chunks) + len(world.stored)
    return res


def main() -> None:
    q = 0.25 if ARGS.quick else 1.0

    def r(n: int) -> int:
        return max(3, int(n * q))

    results: dict = {"api": "phase5" if CHUNKED else "phase3+" if PYGAME_API else ("phase2" if NEW_API else "pre-phase2")}
    results["floor_generation"] = bench_floor_generation(r(20))
    results["spawn_trees_x500"] = bench_spawn_trees(r(5))
    for kind in ("passive", "hungry", "hostile"):
        for n in (10, 50, 200):
            # 15 turns only: passive rabbits turn hungry after ~20 turns and would change regime.
            results[f"turn_{kind}_{n}"] = bench_turn(kind, n, 15 if not ARGS.quick else 8)
    results["pathfinding"] = bench_pathfinding(r(5))
    results["fov"] = bench_fov(r(100))
    results["render"] = bench_render(r(100))
    results["save_load"] = bench_save_load(r(10))
    if CHUNKED:
        results["chunked"] = bench_chunked(r(12), 16 if not ARGS.quick else 8)

    print(f"[{results['api']}] src={SRC}")
    print(f"{'benchmark':<28}{'median':>10}{'mean':>10}{'min':>10}{'max':>10}  n")

    def row(name, d):
        print(f"{name:<28}{d['median']:>10.3f}{d['mean']:>10.3f}{d['min']:>10.3f}{d['max']:>10.3f}  {d['n']}")

    for name, d in results.items():
        if not isinstance(d, dict):
            continue
        if "median" in d:
            row(name, d)
        else:
            for sub, dd in d.items():
                if isinstance(dd, dict):
                    row(f"{name}.{sub}", dd)
                else:
                    print(f"{name}.{sub:<20}{dd:>10}")
    if ARGS.json:
        Path(ARGS.json).write_text(json.dumps(results, indent=2))
        print(f"\nwrote {ARGS.json}")


if __name__ == "__main__":
    main()
