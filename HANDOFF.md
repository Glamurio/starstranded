# HANDOFF

> Fresh session? Read this, then DECISIONS.md and ARCHITECTURE_NOTES.md, then continue at the first incomplete phase.
> Do not re-read the whole codebase unless the notes say you must.

## Current state
- **Phase 0: DONE** (baseline tests, benchmark, notes). **Phase 1: IN PROGRESS** (not started yet at this writing).
- Branch `modernize` (from `crafting`). Last commits: owner WIP carry-over → Phase 0 tests/scripts/notes.
- Phases 0 & 1 run on Sonnet 5.5 (continue without waiting between them). **Phase 2 needs Opus 5.5 — STOP at that checkpoint.**

## Phase plan status
| Phase | Model | Status |
|---|---|---|
| 0 Baseline & safety net | Sonnet 5.5 | done |
| 1 Bug fixes (one commit + test each) | Sonnet 5.5 | in progress |
| 2 Species/instance split, spatial index, perf | **Opus 5.5** | not started — must begin with a design plan in DECISIONS.md |
| 3 pygame-ce migration | Sonnet 5.5 | not started |
| 4 Sprite layering | Sonnet 5.5 | not started |
| 5 Chunked world | **Opus 5.5** | not started — must begin with a design plan in DECISIONS.md |

## How to run things
Dev environment used so far (Linux VM, Python 3.13 required by pyproject):
```
uv venv --python 3.13 ~/venv313 && . ~/venv313/bin/activate
uv pip install "tcod>=21" numpy pytest pygame-ce matplotlib   # matplotlib only until Phase 1 removes it
```
- Tests (from repo root): `python -m pytest -q`  (67 tests, ~2 s; conftest chdirs to `src/` and sets `SDL_VIDEODRIVER=dummy`)
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
1. Phase 1: one commit per bug, each with a regression test (flip the matching `test_current_*` test). Order: hunger/thirst,
   handle_health clamp, mutable defaults/class-level state, annotations, get_path_to `[]`, area-target frame, matplotlib removal,
   delete `text_input`, namegen cache/replacement, `asyncio.exceptions` import, Level.increase_* crash, inventory `chr()` crash.
2. Update DECISIONS.md table statuses and CHANGELOG.md; print the **Phase 2 MODEL CHECKPOINT** and stop.
