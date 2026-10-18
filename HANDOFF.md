# HANDOFF

> Fresh session? Read this, then ARCHITECTURE_NOTES.md (final architecture) and the bottom of DECISIONS.md ("Phase 5 outcome").

## Current state
- **All phases (0–5) DONE.** 375 tests pass (`python -m pytest -q`, ~10 s). Branch `modernize` (forked from `crafting` @ e01d7a4).
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

## Performance pass 1 — done
Path planning, chunk (de)compression, saves and plant growth were fixed (see BENCHMARKS.md, DECISIONS.md "Performance pass 1").
Left: generating chunks ahead of the player (crossing ≈ 20 ms), animal AI cost (200 hungry animals ≈ 18 ms/turn; the AI rework
should make it goal-driven), `Entity`/`Item` construction (gaussian tint per item).

## Day/night, layers, bigger simulation — done
- Lighting (`lighting.py`), layers (`shafts.py`, `GameWorld.layers`), buildable floors/stairs, `sim_radius` 2. See CHANGELOG and
  DECISIONS for what and why; 375 tests.

## Known issues / next candidates
- No water or drinking yet: `Meat` quenches thirst as a stopgap. Needs a liquid flag in `tile_dt` (like `open`/`stairs`) and a
  drink action/behaviour step.
- Felled trees leave no stump; saplings never regrow after being cut (plants are only removed).
- `open` tiles are not walkable and nothing falls; creatures and items on a layer you are not on are frozen, then caught up
  (only hunger/thirst/growth are replayed, not movement or hunts).
- Looking down shows terrain only, not creatures or items on the lower layer.
- Creatures never change layers (stairs are for the player); Selenites are hostile to the player, so they rarely hunt rabbits
  when you are in view.
- Wall edge sprites next to carved cave rooms are not recomputed for the carved tiles' neighbours beyond the chunk's padded
  region (cosmetic).
- Visible map is fixed at one 70x40 view, the window only scales (DECISIONS.md, "Lighting and visible map size").
