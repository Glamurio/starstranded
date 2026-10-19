# Starstranded

Starstranded is a roguelike survival game set on an alien planet.

## Development

Requires Python 3.13+.

- **Install:** `pip install -r requirements.txt` (`tcod`, `pygame-ce`, `numpy`; add `pytest` for development). Use **pygame-ce**,
  not plain `pygame` (no wheels for current Pythons; the two must not be installed together).
- **Run:** `python src/main.py` (or `cd src && python main.py`; `main.py` switches to its own folder) (the window is resizable; it is drawn at 1920x1080 and scaled).
- **Run headless** (no display, e.g. CI): set `SDL_VIDEODRIVER=dummy` (and `SDL_AUDIODRIVER=dummy`). The tests, the benchmark and
  the screenshot script do this themselves.
- **Tests:** `python -m pytest -q` from the repository root.
- **Screenshots of every screen:** `python scripts/screenshots.py [outdir]` (default `docs/phase3`).
- **Benchmark:** `python scripts/benchmark.py [--json out.json] [--quick]` (see `BENCHMARKS.md`); `--src PATH` runs it against
  another checkout's `src/` for A/B comparisons.
- **Debug tools / God Mode:** `python src/main.py --debug` (or set `STARSTRANDED_DEBUG=1`). **F10** toggles God Mode (no damage or needs,
  walk through walls and water, a click walks in a straight line); with it on, **Ctrl + move key** jumps 10 tiles and **Alt + move key**
  jumps one chunk. Terrain is generated exactly as in an ordinary run; nothing is saved. See `src/debug.py`.
- **Saves** go to `src/savegame/` (a folder: manifest + one file per visited chunk).
- **Configuration:** `src/config.py` (`GameConfig`: FOV and path radius, simulation tiers, clutter safeguard).

Project notes for contributors: `ARCHITECTURE_NOTES.md`, `DECISIONS.md`, `CHANGELOG.md`, `HANDOFF.md`.
