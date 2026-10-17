# Benchmarks

Run: `python scripts/benchmark.py [--json out.json] [--quick]` (headless, SDL dummy driver). All values are
**milliseconds, median**. The "range" column is min–max of the median across 3 separate runs, i.e. run-to-run noise.

Machine: cloud VM, Intel i7-12700 (2 vCPUs), CPython 3.13.15, tcod 21.2.1, numpy 2.2.6, software SDL renderer.
Seed 7 for `random`/`numpy` (note: tcod noise itself is unseeded, so terrain differs between runs).

## Baseline (Phase 0, untouched game code, tcod console rendering)

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

## Phase 2 / 3 / 5 results
_Filled in as phases complete._
