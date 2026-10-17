# HANDOFF

> Fresh session? Read this, then DECISIONS.md (bottom: "Phase 2/3/4 outcome") and ARCHITECTURE_NOTES.md (top: "Current
> architecture"), then continue at the first incomplete phase. Do not re-read the whole codebase unless the notes say you must.

## Current state
- **Phases 0–4: DONE** (290 tests pass). **Next: Phase 5 (chunked world) — must run on Opus 5.5 and must begin with a design plan
  in DECISIONS.md, then stop for the owner's checkpoint before implementing.**
- Branch `modernize` (forked from `crafting` @ e01d7a4, which contains all of `crafting`/`origin/crafting`). Working tree clean at hand-off.
- Owner instruction: the performance overhaul (e.g. leftover oddities, tree-inventory copies if any remain) is **postponed**; do not start it.
  Owner decisions are delegated to Claude (document in DECISIONS.md, keep going).

## Phase plan status
| Phase | Model | Status |
|---|---|---|
| 0 Baseline & safety net | Sonnet 5.5 | done |
| 1 Bug fixes (one commit + test each) | Sonnet 5.5 | done |
| 2 Species/instance split, spatial index, perf | Opus 5.5 | done |
| 3 pygame-ce migration | Sonnet 5.5 | done |
| 4 Sprite layering | Sonnet 5.5 | done |
| 5 Chunked world | **Opus 5.5** | next — design plan first, then checkpoint |

## How to run things
Dev environment (Linux VM; Python 3.13 required by pyproject):
```
uv venv --python 3.13 ~/venv313 && . ~/venv313/bin/activate
uv pip install "tcod>=21" numpy pytest "pygame-ce>=2.5"   # (+ matplotlib only for scripts/debug_plot_terrain.py)
```
- Tests (repo root): `python -m pytest -q` (~4 s; conftest sets `SDL_VIDEODRIVER=dummy`, calls `g.init(headless=True)`, imports from `src/`, chdirs per test).
- Benchmark: `python scripts/benchmark.py [--json out.json] [--quick] [--src PATH]` (~5 s). Fixed scenario; `--src` runs it against
  another checkout (`git archive <commit> src | tar -x -C /tmp/x`). Results in BENCHMARKS.md (Phase 0, 2, 3).
- Screenshots: `python scripts/screenshots.py [outdir]` (every screen + Phase 4 stack crops; default `docs/phase3`, layering crops
  in `docs/phase4`); Phase 0 tcod PNGs in `docs/baseline/`. Use `docs/_scratch/` (git-ignored) for throwaway renders.
- Run the game: `cd src && python main.py` (headless: `SDL_VIDEODRIVER=dummy`).

## Gotchas
- **Commits:** project rule — never mention Claude in commits (no trailers). Identity:
  `GIT_AUTHOR_NAME="Ryou Takeshi" GIT_AUTHOR_EMAIL=ryou.takeshi@gmail.com` (+ same `GIT_COMMITTER_*`). Never rewrite history.
  Run the full test suite before every commit.
- **Line endings:** working tree CRLF, blobs LF ⇒ `git -c core.autocrlf=input add/commit`; preserve CRLF when editing existing files.
- **Deletion permission** in the connected folder is per session; git needs it (temp/lock files). If a stale `.git/*.lock` from
  your own earlier command appears, remove it once permission is granted.
- Never `git add tests` blindly before checking `git status` (bytecode was committed once; root .gitignore now covers it).
- `g.init(headless=True)` creates window/atlas/canvas; `import setup_game` **first** (circular imports). Handlers build their entry
  lists while rendering, so call `g.draw(handler)` before sending events in tests. `tests/test_display_events.py` re-inits `g` on teardown.
- Entities: never assign `_x/_y` or mutate `GameMap` dicts directly; use `place()`/`move()`/`add_entity()`. After editing
  `tiles` walkable/transparent outside generation call `game_map.terrain_changed()` (pathfinding also self-validates).
- `tests/index_helpers.assert_index_consistent(game_map)` checks every index; use it in new tests that move entities.
- Tests that inspect pixels: `tests/render_helpers.py` (`cell`, `expected_sprite_cell`, `expected_tile`, `draw_map`).
- Tool calls are limited to ~175 s and background jobs die with the call; split long runs.

## Phase 5 notes
- Axis convention: `tiles/visible/explored` are indexed `[x, y]` (width first), numpy order F; `tcod.noise.grid(shape=(h, w))` returns
  `(w, h)` in tcod 21.2.1 (asserted in `procgen`). Terrain noise is seeded via `random.getrandbits(31)`; generation is reproducible.
- `GameMap.render(canvas, origin)` already accepts a cell offset; the map is currently drawn at (0, 0) filling the 70x40 area
  (`g.screen_width - g.screen_width_offset` x `g.screen_height - g.screen_height_offset`). A camera needs: view window origin in map
  coordinates, slicing of `visible/explored/tiles`, entity culling, and `Engine.mouse_location`/click conversion (cell + camera origin).
- `GameConfig.fov_radius` is 80 (whole map visible); with a centred camera ~41 is the sensible value.
- Saves: `SAVE_VERSION = 3`, `{"version": 3, "engine": Engine}` lzma-pickled, atomic (`Engine.save_as`). Phase 5 target: per-chunk
  lzma files + manifest written atomically, deltas or whole-chunk persistence; keep `IncompatibleSave` for older versions.
- Spec reminders for Phase 5 (from the brief): 70x40 chunks keyed `(cx, cy)`, deterministic per-chunk generation from
  `(world_seed, cx, cy)` with world-coordinate noise (`tcod.noise.grid(origin=...)`), simulation tiers ACTIVE/NEAR/FAR, stitched view
  window, each floor its own `World` by default. Write the design plan into DECISIONS.md first, then stop for the checkpoint.
- Known behaviour left unchanged on purpose (DECISIONS.md "Open gameplay questions"): `PassiveAI.seek_food` never walks to distant food,
  hungry rabbits pick a new random wander target each turn, units without an AI cannot die, `Plant.die` tile swap is unreachable.

## Open gameplay questions
See DECISIONS.md → "Open gameplay questions". Not blocking.

## MODEL CHECKPOINT
Phase 5 should run on **Claude Opus 5.5**. Switch models (new session if needed) and reply "continue".
