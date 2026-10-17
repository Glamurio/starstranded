# HANDOFF

> Fresh session? Read this, then DECISIONS.md and ARCHITECTURE_NOTES.md, then continue at the first incomplete phase.
> Do not re-read the whole codebase unless the notes say you must.

## Current state
- **Phase 0: DONE. Phase 1: DONE** (137 tests passing). **Next: Phase 2 — must run on Opus 5.5 (checkpoint below).**
- Branch `modernize` (from `crafting`). Commit history: owner WIP carry-over → Phase 0 (tests, benchmark, notes) → one commit per Phase 1 fix.
- Phases 0 & 1 run on Sonnet 5.5 (continue without waiting between them). **Phase 2 needs Opus 5.5 — STOP at that checkpoint.**

## Phase plan status
| Phase | Model | Status |
|---|---|---|
| 0 Baseline & safety net | Sonnet 5.5 | done |
| 1 Bug fixes (one commit + test each) | Sonnet 5.5 | done |
| 2 Species/instance split, spatial index, perf | **Opus 5.5** | not started — must begin with a design plan in DECISIONS.md |
| 3 pygame-ce migration | Sonnet 5.5 | not started |
| 4 Sprite layering | Sonnet 5.5 | not started |
| 5 Chunked world | **Opus 5.5** | not started — must begin with a design plan in DECISIONS.md |

## How to run things
Dev environment used so far (Linux VM, Python 3.13 required by pyproject):
```
uv venv --python 3.13 ~/venv313 && . ~/venv313/bin/activate
uv pip install "tcod>=21" numpy pytest pygame-ce   # (+ matplotlib only for scripts/debug_plot_terrain.py)
```
- Tests (from repo root): `python -m pytest -q`  (137 tests, ~2 s; conftest chdirs to `src/` and sets `SDL_VIDEODRIVER=dummy`)
- Benchmark: `python scripts/benchmark.py [--json out.json] [--quick]` (~5 s). Baseline in BENCHMARKS.md.
- Baseline screenshots: `python scripts/screenshot_baseline.py [outdir]` → `docs/baseline/*.png` (tcod-render era; Phase 3 replaces it).
- Run the game: `cd src && python main.py` (needs a display; headless: `SDL_VIDEODRIVER=dummy`).

## Gotchas
- **Line endings:** working tree is CRLF, repo blobs are LF. Commit with `git -c core.autocrlf=input add/commit`. Edit existing files
  preserving CRLF (python `open(p,'rb')` read-modify-write, or `tr -d '\r'` only for *reading*). New files: LF is fine.
- **Git identity:** none configured. Use `GIT_AUTHOR_NAME=Pascal GIT_AUTHOR_EMAIL=p.kammer@satzweiss.com` (+ `GIT_COMMITTER_*`).
  End commit messages with the attribution lines from the session reminder (Co-Authored-By + Claude-Session).
- Deletion in the connected folder was approved for this session (needed by git for temp/lock files). If a stale `.git/*.lock`
  appears, `mv` it aside; don't delete anything else.
- Importing `g` opens an SDL window ⇒ always set `SDL_VIDEODRIVER=dummy` for headless. `import setup_game` **first** (circular imports).
- `tcod.noise.Noise()` is unseeded ⇒ terrain is not reproducible from `random.seed`. Tile colours for water/wall are random per process.
- Tool-call limit: don't run long jobs in one shell call (120–175 s); background jobs started from a call get killed when it ends.
- `Selenite()` without a name calls `generate_name` (re-parses all cfg files: very slow) — pass `name=` in benchmarks/tests.
- Screenshots need the text tileset merged like `main.main()` does (see `scripts/screenshot_baseline.py`).

## Needs owner decision
See DECISIONS.md → "Needs owner decision" (8 items so far). None blocks Phase 1; item 1 (hunger semantics) uses the proposed default
unless you object.

## Next steps
1. **Phase 2 (Opus 5.5).** Start by writing the design plan into DECISIONS.md (class layout for `PlantSpecies`/`UnitSpecies`/`ItemKind`,
   how `parent`/`engine`/`game_map` back-references are removed or reduced, pickling/identity effects, `SAVE_VERSION`), then implement:
   species registries (no `deepcopy`), `GameMap` spatial index (`add_entity/remove_entity/move_entity`, per-kind sets, AI set), cached
   pathfinding with entity overlays, configurable FOV radius, bucketed render, vectorised vegetation + lake dilation.
2. Things Phase 2 must keep in mind: `test_current_*` tests still pin quirks (corpse/unit lookup, `Plant.die`, class-level
   `CharacterCreation.PLAYER`, shared `get_names_at_location` scan); update them only where an API legitimately changes and say so.
   Old saves need not load; version the new format. Pickle graph and back-references are described in ARCHITECTURE_NOTES.md.
3. Decide with the owner (DECISIONS.md → "Needs owner decision") before Phase 2 touches unit lookup semantics (#2).

## MODEL CHECKPOINT
Phase 2 should run on **Claude Opus 5.5**. Switch models (new session if needed) and reply "continue".
