# Starstranded

Starstranded is a roguelike survival game set on an alien planet.

## Development

Requires Python 3.13+.

- **Install:** `pip install -r requirements.txt` (`tcod`, `pygame-ce`, `numpy`; add `pytest` for development).
- **Run:** `cd src && python main.py` (the window is resizable; it is drawn at 1920x1080 and scaled).
- **Run headless** (no display, e.g. CI): set `SDL_VIDEODRIVER=dummy` (and `SDL_AUDIODRIVER=dummy`). The tests, the benchmark and
  the screenshot script do this themselves.
- **Tests:** `python -m pytest -q` from the repository root.
- **Screenshots of every screen:** `python scripts/screenshots.py [outdir]` (default `docs/phase3`).
- **Benchmark:** `python scripts/benchmark.py [--json out.json] [--quick]` (see `BENCHMARKS.md`).

Project notes for contributors: `ARCHITECTURE_NOTES.md`, `DECISIONS.md`, `CHANGELOG.md`, `HANDOFF.md`.
