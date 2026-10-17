#!/usr/bin/env python3
"""Dev-only: generate a floor headless and plot terrain/vegetation with matplotlib.

    pip install matplotlib        # NOT a runtime dependency of the game
    python scripts/debug_plot_terrain.py [out.png]

(Replaces the commented-out `plt.imshow(...)` debug lines that used to live in procgen.py.)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
os.chdir(SRC)

import numpy as np  # noqa: E402

import setup_game  # noqa: E402
from components.plant import Plant  # noqa: E402


def main() -> None:
    import matplotlib.pyplot as plt  # dev dependency, imported lazily

    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("terrain.png").resolve()
    engine = setup_game.new_game(setup_game.create_player())
    m = engine.game_map
    image = np.zeros((m.height, m.width, 3))
    walkable = m.tiles["walkable"].T  # tiles are [x, y]; imshow wants [row=y, col=x]
    image[walkable] = (0.25, 0.25, 0.25)
    image[~walkable] = (0.1, 0.2, 0.6)
    for entity in m.entities:
        if isinstance(entity, Plant):
            image[entity.y, entity.x] = (0.0, 0.8, 0.0)
    image[engine.player.y, engine.player.x] = (1.0, 1.0, 1.0)
    plt.imshow(image)
    plt.savefig(out)
    print("saved", out)


if __name__ == "__main__":
    main()
