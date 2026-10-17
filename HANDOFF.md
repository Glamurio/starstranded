# HANDOFF

> Fresh session? Read this, then DECISIONS.md (bottom: "Phase 2 outcome") and ARCHITECTURE_NOTES.md (top: "Current
> architecture"), then continue at the first incomplete phase. Do not re-read the whole codebase unless the notes say you must.

## Current state
- **Phases 0, 1, 2: DONE** (215 passed). **Next: Phase 3 (pygame-ce migration) — should run on Sonnet 5.5.**
- Branch `modernize` (forked from `crafting` @ e01d7a4, which contains all of `crafting`/`origin/crafting`).
- Working tree clean at hand-off.

## Phase plan status
| Phase | Model | Status |
|---|---|---|
| 0 Baseline & safety net | Sonnet 5.5 | done |
| 1 Bug fixes (one commit + test each) | Sonnet 5.5 | done |
| 2 Species/instance split, spatial index, perf | Opus 5.5 | done |
| 3 pygame-ce migration | **Sonnet 5.5** | next |
| 4 Sprite layering | Sonnet 5.5 | not started |
| 5 Chunked world | **Opus 5.5** | not started — must begin with a design plan in DECISIONS.md |

## How to run things
Dev environment (Linux VM; Python 3.13 required by pyproject):
```
uv venv --python 3.13 ~/venv313 && . ~/venv313/bin/activate
uv pip install "tcod>=21" numpy pytest pygame-ce   # (+ matplotlib only for scripts/debug_plot_terrain.py)
```
- Tests (repo root): `python -m pytest -q` (~2 s; conftest sets `SDL_VIDEODRIVER=dummy`, imports from `src/` and chdirs per test).
- Benchmark: `python scripts/benchmark.py [--json out.json] [--quick] [--src PATH]` (~5 s). Fixed scenario; `--src` runs it against
  another checkout (`git archive <commit> src | tar -x -C /tmp/x`). Phase 2 A/B numbers in BENCHMARKS.md.
- Screenshots (tcod era): `python scripts/screenshot_baseline.py [outdir]`; Phase 0 PNGs in `docs/baseline/`.
  Use `docs/_scratch/` (git-ignored) for throwaway renders you want to look at.
- Run the game: `cd src && python main.py` (headless: `SDL_VIDEODRIVER=dummy`).

## Gotchas
- **Commits:** project rule — never mention Claude in commits (no trailers). Identity:
  `GIT_AUTHOR_NAME="Ryou Takeshi" GIT_AUTHOR_EMAIL=ryou.takeshi@gmail.com` (+ same `GIT_COMMITTER_*`). Never rewrite history.
  Run the full test suite before every commit (one commit slipped through red in Phase 2).
- **Line endings:** working tree CRLF, blobs LF ⇒ `git -c core.autocrlf=input add/commit`; preserve CRLF when editing existing files.
- **Deletion permission** in the connected folder is per session; git needs it (temp/lock files). If a stale `.git/*.lock` from
  your own earlier command appears, remove it once permission is granted.
- Never `git add tests` blindly before checking `git status` (bytecode was committed once; root .gitignore now covers it).
- Importing `g` opens an SDL window ⇒ `SDL_VIDEODRIVER=dummy` for headless. `import setup_game` **first** (circular imports).
- Entities: never assign `_x/_y` or mutate `GameMap` dicts directly; use `place()`/`move()`/`add_entity()`. After editing
  `tiles` walkable/transparent outside generation call `game_map.terrain_changed()` (pathfinding also self-validates).
- `tests/index_helpers.assert_index_consistent(game_map)` checks every index; use it in new tests that move entities.
- Tool calls are limited to ~175 s and background jobs die with the call; split long runs.

## Phase 3 notes (from Phase 2)
- Rendering touch points: `g.py`, `main.py` loop, `GameMap.render` (buckets via `entities_in_render_order()`),
  `Engine.render`, `message_log.render*`, `render_functions`, all `input_handlers`/`setup_game` `on_render`/`ev_*`.
- Sprite data already lives in definitions: `kind.sprite` / `kind.corpse_sprite` / `kind.glyph` (text items) plus per-instance
  `mirrored`, `shade`, `is_corpse`. Delete `species.glyphs`, `Entity.glyph/char`, `utilities.map_codepoints`, the PUA charmap.
- Tile dtype still stores (ch, fg, bg); `Plant.on_added_to_map` writes its glyph into `tile['dark']` (remembered view).
- UI rows currently off-screen (message log row 49, dungeon level row 47 on a 45-row console); fix when laying out pygame UI.
- `scripts/benchmark.py` render section and `scripts/screenshot_baseline.py` are tcod-specific; port them.

## Open gameplay questions
See DECISIONS.md → "Open gameplay questions" (seek_food never walks to distant food, etc.). Not blocking.

## MODEL CHECKPOINT
Phase 3 should run on **Claude Sonnet 5.5**. Switch models (new session if needed) and reply "continue".
