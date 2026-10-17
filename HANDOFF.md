# HANDOFF

> Fresh session? Read this, then ARCHITECTURE_NOTES.md (final architecture) and the bottom of DECISIONS.md ("Phase 5 outcome").

## Current state
- **All phases (0–5) DONE.** 321 tests pass (`python -m pytest -q`, ~10 s). Branch `modernize` (forked from `crafting` @ e01d7a4).
- Working tree clean at hand-off. Deliverables: ARCHITECTURE_NOTES.md (final), DECISIONS.md, CHANGELOG.md, BENCHMARKS.md
  (baseline vs final), README dev section, screenshots in `docs/phase3`, `docs/phase4`, `docs/phase5` (Phase 0 tcod ones in `docs/baseline`).
- Owner instruction: the performance overhaul is **postponed**; owner decisions were delegated (see "Needs owner decision" in the final report).

## Phase plan status
| Phase | Model | Status |
|---|---|---|
| 0 Baseline & safety net | Sonnet 5.5 | done |
| 1 Bug fixes | Sonnet 5.5 | done |
| 2 Species/instance split, spatial index, perf | Opus 5.5 | done |
| 3 pygame-ce migration | Sonnet 5.5 | done |
| 4 Sprite layering | Sonnet 5.5 | done |
| 5 Chunked world | Opus 5.5 | done |

## How to run things
```
uv venv --python 3.13 ~/venv313 && . ~/venv313/bin/activate
uv pip install "tcod>=21" numpy pytest "pygame-ce>=2.5"   # (+ matplotlib only for scripts/debug_plot_terrain.py)
```
- Game: `cd src && python main.py` (headless: `SDL_VIDEODRIVER=dummy`). Saves: `src/savegame/`.
- Tests: `python -m pytest -q` (headless; conftest calls `g.init(headless=True)`).
- Benchmark: `python scripts/benchmark.py [--json out.json] [--quick] [--src PATH]`. Screenshots: `python scripts/screenshots.py [outdir]`.

## Gotchas
- **Commits:** never mention Claude (no trailers). Identity `GIT_AUTHOR_NAME="Ryou Takeshi" GIT_AUTHOR_EMAIL=ryou.takeshi@gmail.com`
  (+ same `GIT_COMMITTER_*`). Never rewrite history. Run the full suite before every commit.
- **Line endings:** working tree CRLF, blobs LF ⇒ `git -c core.autocrlf=input add/commit`; preserve CRLF when editing.
- Entities: never assign `_x/_y` or touch chunk indexes directly; use `place()/move()/add_entity()`. Terrain edits through
  `World.modify_tile/set_tile` (the bounded `GameMap.tiles` view marks terrain changed itself).
- Entities can only be placed in **loaded** chunks; `in_bounds` means "loaded". Unloaded chunk entities are bytes in `World.stored`.
- Handlers build their entry lists while rendering: `g.draw(handler)` before sending events in tests.
- `tests/index_helpers.assert_index_consistent(world)` checks all indexes; `tests/render_helpers.py` for pixel checks;
  `worldgen.FlatWorldSource` gives an empty endless world for tests.
- Tool calls are limited to ~175 s; split long runs.

## Ideas for the postponed performance pass
Border crossing (~40 ms: serialising leaving chunks; could be deferred/incremental), save of large explored areas (~100 ms for 27
chunks), CPU rendering (~2.5 ms/frame; a cached terrain layer with dirty rects), per-turn plant upkeep in the ACTIVE chunk, the
remaining O(n) loops over `world.units` (player auto-walk check, lightning target).
