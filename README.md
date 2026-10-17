# Starstranded

Starstranded is a roguelike survival game set on an alien planet.

## Development

Requires Python 3.13+.

- **Install:** `pip install "tcod>=21" numpy` (add `pytest` for development).
- **Run:** `cd src && python main.py`
- **Run headless** (no display, e.g. CI): set `SDL_VIDEODRIVER=dummy` (and `SDL_AUDIODRIVER=dummy`).
- **Tests:** `python -m pytest -q` from the repository root.
- **Benchmark:** `python scripts/benchmark.py [--json out.json] [--quick]` (see `BENCHMARKS.md`).

Project notes for contributors: `ARCHITECTURE_NOTES.md`, `DECISIONS.md`, `CHANGELOG.md`, `HANDOFF.md`.
