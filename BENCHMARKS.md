# Benchmarks

Run: `python scripts/benchmark.py [--json out.json] [--quick] [--src PATH]` (headless, SDL dummy driver). All values are
**milliseconds, median**. The "range" column is min–max of the median across 3 separate runs, i.e. run-to-run noise.

Machine: cloud VM, Intel i7-12700 (2 vCPUs), CPython 3.13.15, tcod 21.2.1, numpy 2.2.6, software SDL renderer.
Seed 7 for `random`/`numpy` (note: tcod noise itself is unseeded, so terrain differs between runs).

## Phase 0 baseline (untouched game code, tcod console rendering)

> Measured on freshly generated, **unseeded** terrain (different every run and every code version). Kept for the record;
> use the fixed-scenario A/B tables below for comparisons.

| benchmark | median ms | range across 3 runs | samples |
|---|---:|---|---:|
| `floor_generation` (full `generate_floor`: terrain + vegetation + monsters/items, ~97 entities) | 7.668 | 7.297–7.671 | 20 |
| `spawn_trees_x500` (500 deepcopy spawns from one prototype) | 12.490 | 12.294–12.696 | 5 |
| `turn_passive_10` (player wait + 10 idle rabbits) | 0.336 | 0.323–0.396 | 15 |
| `turn_passive_50` | 1.059 | 0.998–1.110 | 15 |
| `turn_passive_200` | 5.328 | 4.979–5.386 | 15 |
| `turn_hungry_10` (rabbits all seeking food) | 4.088 | 4.055–4.152 | 15 |
| `turn_hungry_50` | 20.457 | 19.793–22.985 | 15 |
| `turn_hungry_200` | 94.727 | 94.554–96.056 | 15 |
| `turn_hostile_10` (Selenites chasing the player) | 1.298 | 1.271–1.304 | 15 |
| `turn_hostile_50` | 5.738 | 5.347–6.395 | 15 |
| `turn_hostile_200` | 36.779 | 35.927–36.884 | 15 |
| `pathfinding` (`get_path_to`, corner to corner) | 0.206 | 0.202–0.236 | 100 |
| `fov` (`update_fov`, radius 100) | 0.017 | 0.017–0.017 | 100 |
| `render.engine_render` (console only) | 0.224 | 0.222–0.247 | 100 |
| `render.frame_no_present` (console → SDL texture → copy) | 1.123 | 0.989–1.272 | 100 |
| `render.frame_with_present` | ≈16.66 | — | 20 |
| `save_load.save` (pickle + lzma, ~5.2 KiB file) | 9.658 | 9.071–10.036 | 10 |
| `save_load.load` | 0.800 | 0.745–0.832 | 10 |

Reading the numbers:
- `frame_with_present` is a vsync wait (~16.7 ms, one 60 Hz frame), not CPU work; compare `frame_no_present`.
- Turn cost is dominated by pathfinding: each `get_path_to` rebuilds the cost array/graph and scans **all** entities
  (≈0.2 ms per call; a hungry unit may call it more than once per turn). 200 hungry rabbits ≈ 95 ms/turn.
- Total entity count in the 200-unit scenarios is 342 (97 from generation + 200 + the player etc.).
- `fov` is not a measurable cost at 70x40 even with radius 100; the radius work in Phase 2 is about semantics, not speed.
- Passive scenarios are measured over 15 turns because rabbits turn hungry after ~20 turns and change regime.

## Phase 2: fixed-scenario A/B (Phase 1 code vs Phase 2 code)

Both columns were measured with the **same** `scripts/benchmark.py` on the same fixed scenario (saved landscape, fixed
spawn positions, AI RNG reseeded before timing). "Phase 1" is commit `8c03308` extracted with `git archive` and run via
`--src`; the script adapts to the pre-Phase-2 API. Median of 3 runs; "range" is the spread of the 3 run medians.
`pathfinding` is per query (mean of 300 fixed queries). Total entities in the 10/50/200 scenarios: 71/111/261.

| benchmark | Phase 1 ms | range | Phase 2 ms | range | speed-up |
|---|---:|---|---:|---|---:|
| `floor_generation` | 7.426 | 7.418–7.666 | 3.156 | 2.998–3.563 | 2.35x |
| `spawn_trees_x500` | 12.601 | 12.330–12.749 | 3.128 | 3.030–3.188 | 4.03x |
| `turn_passive_10` | 0.198 | 0.182–0.204 | 0.203 | 0.183–0.206 | 0.98x |
| `turn_passive_50` | 0.730 | 0.599–0.811 | 0.417 | 0.347–0.467 | 1.75x |
| `turn_passive_200` | 4.870 | 4.220–5.625 | 1.977 | 1.915–1.993 | 2.46x |
| `turn_hungry_10` | 2.621 | 2.568–2.836 | 1.843 | 1.809–1.883 | 1.42x |
| `turn_hungry_50` | 13.867 | 13.793–13.901 | 9.701 | 9.501–9.969 | 1.43x |
| `turn_hungry_200` | 70.038 | 69.837–70.084 | 43.878 | 42.079–43.973 | 1.60x |
| `turn_hostile_10` | 1.530 | 1.467–1.577 | 1.485 | 1.473–1.703 | 1.03x |
| `turn_hostile_50` | 10.804 | 10.575–10.830 | 10.186 | 9.697–10.528 | 1.06x |
| `turn_hostile_200` | 52.071 | 51.402–53.287 | 46.238 | 45.504–46.555 | 1.13x |
| `pathfinding` | 0.256 | 0.254–0.257 | 0.243 | 0.241–0.244 | 1.05x |
| `fov` | 0.018 | 0.017–0.018 | 0.017 | 0.016–0.017 | 1.06x |
| `render.engine_render` | 0.228 | 0.220–0.239 | 0.233 | 0.227–0.240 | 0.98x |
| `render.frame_no_present` | 1.090 | 1.028–1.382 | 1.144 | 1.078–1.287 | 0.95x |
| `save_load.save` | 8.776 | 8.637–8.844 | 9.521 | 9.414–9.904 | 0.92x |
| `save_load.load` | 0.749 | 0.705–0.787 | 0.785 | 0.784–0.831 | 0.95x |
| `save_load.size_kib` | 5.1 | | 6.3 | | |

What moved and why:
- **Generation 2.35x, spawning 4x:** no `deepcopy` (construct + `add_entity`), vectorised lake dilation and edge variations.
- **Idle/hungry turns 1.4–2.5x:** only actors are iterated; food search is a ring scan over the spatial index instead of a
  distance check against every item and plant per radius; blocking checks and lookups are O(1).
- **Hostile turns ~1.1x:** each visible hostile still runs one full tcod search per turn and the search itself dominates
  (pathfinding per query only 1.05x: the removed entity loop was a small share). Ideas measured and rejected: cropping the
  search window (tcod was *slower* on a small grid) and legacy `tcod.path.AStar` (5x faster but returned costlier routes in
  12 of 1,602 queries). A shared per-turn distance map would help but changes crowding behaviour; candidate for Phase 5's
  simplified NEAR-tier AI.
- **Render, FOV, save/load ~parity.** Glyph lookup had made rendering ~50% slower until it was cached by identity
  (commit 7fff303). Saves are ~1.2 KiB larger (index structures are pickled with the map).

Reproduce: `git archive 8c03308 src | tar -x -C /tmp/p1 && python scripts/benchmark.py --src /tmp/p1/src --json old.json`
and `python scripts/benchmark.py --json new.json`.

## Phase 3: pygame-ce rendering (same machine, same fixed scenario)

The scenario terrain is stored in both tile layouts (`scenario_landscape_tcod.npy` for tcod-era checkouts, `scenario_landscape.npy`
with sprite ids for Phase 3+); `scripts/benchmark.py` picks the right one. Simulation sections are unaffected by the port and
stay within noise of Phase 2 (median ms, 20/5/15/100/10 repetitions):

| benchmark | Phase 2 ms | Phase 3 ms |
|---|---:|---:|
| `floor_generation` | 3.156 | 3.170 |
| `spawn_trees_x500` | 3.128 | 2.985 |
| `turn_passive_200` | 1.977 | 1.951 |
| `turn_hungry_200` | 43.878 | 44.636 |
| `turn_hostile_200` | 46.238 | 47.617 |
| `pathfinding` (per query) | 0.243 | 0.240 |
| `fov` | 0.017 | 0.017 |
| `save_load.save` / `.load` | 9.521 / 0.785 | 10.143 / 0.988 |
| `save_load.size_kib` | 6.3 | 6.2 |

Rendering is a different pipeline, so the numbers are not directly comparable. tcod filled a console array (0.23 ms) and
the GPU drew it (1.1 ms per frame, vsync-capped when presented). pygame blits on the CPU:

| benchmark (50 extra units, in-game view) | median ms | range |
|---|---:|---|
| `render.map_render` (terrain batch + entities) | 3.449 | 3.147–4.122 |
| `render.engine_render` (map + status bars, names, log, side panel) | 3.699 | 3.297–5.028 |
| `render.frame_no_present` (full screen draw) | 3.755 | 3.342–5.553 |
| `render.frame_with_present` (draw + scale to window + flip, dummy driver) | 5.505 | 4.956–6.653 |

A frame costs ~3.8 ms to draw and ~5.5 ms with presenting, i.e. a third of the 16.7 ms budget. Frames are only drawn after an
input event or window change (the old loop redrew every iteration), and the loop is capped at 60 FPS, so an idle game costs
no CPU. The terrain batch dominates: tiles are grouped by distinct graphic with `np.unique`, so the Python-level work is one
list comprehension over visible tiles plus one `Surface.blits` call. The sprite cache stays small (a few hundred variants).
Ideas for the later performance pass: cache the terrain layer as one surface and repaint only when `visible`/`explored`
or terrain changes (moving the player changes FOV nearly every turn, so this needs dirty-rects to pay off), and avoid the
Python list building by drawing tiles through a pre-baked per-chunk surface (fits Phase 5).

Reproduce: `python scripts/benchmark.py --json new.json` (older checkouts via `--src`).

## Phase 5: chunked world

New sections (`chunked.*`, seed 7, floor 1 = 3x3 chunks around the start; median ms):

| benchmark | median ms | range (min–max) | notes |
|---|---:|---|---|
| `chunked.chunk_generate` | 2.760 | 2.371–4.700 | one never-visited chunk: terrain + ~133 entities (mostly plants) |
| `chunked.chunk_unload` | 9.389 | 7.526–10.852 | pickle + lzma of one chunk (4.9 KiB) |
| `chunked.chunk_reload` | 1.860 | 1.355–4.008 | restore + catch-up |
| `chunked.turn_near_ring_0` | 1.217 | 0.221–2.007 | natural spawns only |
| `chunked.turn_near_ring_0.near_tick` | 1.649 | 1.273–2.007 | the turns on which NEAR chunks run |
| **`chunked.turn_near_ring_200`** | **1.945** | 0.248–3.619 | +200 rabbits over the 8 NEAR chunks |
| **`chunked.turn_near_ring_200.near_tick`** | **3.071** | 2.826–3.619 | NEAR step for ~230 units + plant upkeep |
| `chunked.border_crossing` | 38.593 | 8.007–46.957 | player step into a new chunk: generates 3 chunks, unloads 3 |
| `chunked.save` / `.load` | 107.6 / 19.1 | | 27 chunks (9 loaded + 18 stored), 142.7 KiB on disk |

For comparison, 200 rabbits in the ACTIVE chunk cost `turn_passive_200` ≈ 2–6 ms and hungry ones `turn_hungry_200` ≈ 43 ms:
the NEAR tier makes a populated ring about as cheap as idle units. The visible cost of the chunked world is the border
crossing (~40 ms once per 70/40 steps; serialising the chunks that leave the window dominates) and saving a large explored
area (all generated chunks are written; unchanged chunk files are reused on later saves).

`floor_generation` now generates 9 chunks (26.6 ms ≈ 2.9 ms per chunk, vs 8.1 ms for the old single 70x40 map).

## Baseline vs final (same script, same machine, fixed scenario)

Baseline = the original code (`d3f5361`, owner WIP on `crafting`, run with `--src`); final = this branch. Rendering is not
comparable 1:1 (tcod GPU console vs pygame CPU blits, see Phase 3); the scenario runs on a bounded 70x40 map in both.

| benchmark | baseline ms | final ms | change |
|---|---:|---:|---:|
| `floor_generation` | 8.124 (1 map) | 26.564 (9 chunks) | 2.9 ms per 70x40 chunk |
| `spawn_trees_x500` | 12.402 | 4.401 | 2.8x faster |
| `turn_passive_200` | 4.281 | 6.019 | noisy (min 3.6 vs 2.9) |
| `turn_hungry_50` | 14.256 | 10.363 | 1.4x faster |
| `turn_hungry_200` | 73.114 | 43.055 | 1.7x faster |
| `turn_hostile_50` | 10.962 | 8.389 | 1.3x faster |
| `turn_hostile_200` | 55.537 | 36.396 | 1.5x faster |
| `pathfinding` (per query) | 0.265 | 0.214 | 1.2x faster |
| `fov` | 0.018 | 0.067 | now on the 210x120 window (radius 41) |
| frame (draw, no present) | 1.185 (GPU) | 2.551 (CPU) | different pipeline; drawn only on change |
| frame with present | 16.664 (vsync) | 4.371 | |
| `save_load.save` / `.load` | 9.475 / 0.848 | 12.333 / 1.493 | bounded map, now a directory |

Reproduce: `git archive d3f5361 src | tar -x -C /tmp/p0 && python scripts/benchmark.py --src /tmp/p0/src --json base.json`,
then `python scripts/benchmark.py --json final.json`. (The original code needs `matplotlib` installed to import.)
