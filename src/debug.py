"""Developer tools, off in normal play: God Mode and teleports for exploring generated terrain.

Switch the tools on with `python main.py --debug` (or the environment variable STARSTRANDED_DEBUG=1). In a debug run:

- F10 toggles God Mode: no damage, hunger, thirst, cold or poison; walking is not stopped by walls, water or things in the way
  (terrain and chunks are generated and loaded exactly as in an ordinary run);
- with God Mode on, Ctrl + a move key jumps 10 tiles and Alt + a move key jumps one whole chunk;
- a click on the map walks in a straight line to that tile, through anything.

Nothing here changes world generation, and nothing is saved: a loaded game always starts in ordinary mode.
"""
from __future__ import annotations

import os
import sys

from chunks import CHUNK_H, CHUNK_W, chunk_key
import exceptions

_enabled = os.environ.get("STARSTRANDED_DEBUG", "") not in ("", "0") or "--debug" in sys.argv

HELP_LINES = (
    ("F10 (debug run)", "God Mode: no damage or needs, walk through anything"),
    ("Ctrl / Alt + move", "God Mode: jump 10 tiles / one chunk"),
)


def enabled() -> bool:
    return _enabled


def enable(on: bool = True) -> None:
    global _enabled
    _enabled = bool(on)


def is_god(engine) -> bool:
    """God Mode is on for this engine's player (always False in an ordinary run)."""
    return _enabled and bool(getattr(engine, "god_mode", False))


def protects(unit) -> bool:
    """True for the player while God Mode is on: damage, hunger and thirst are ignored."""
    if not _enabled:
        return False
    engine = getattr(getattr(unit, "game_map", None), "engine", None)
    return engine is not None and unit is engine.player and is_god(engine)


def toggle_god(engine) -> bool:
    """Flip God Mode (only in a debug run) and say so in the message log."""
    if not _enabled:
        raise exceptions.Impossible("Debug tools are off (start the game with --debug).")
    engine.god_mode = not getattr(engine, "god_mode", False)
    engine.message_log.add_message("God Mode " + ("on." if engine.god_mode else "off."))
    return engine.god_mode


def straight_path(unit, x: int, y: int):
    """The tiles of a straight line from `unit` to (x, y), without the start: God Mode walks through everything."""
    import tcod.los
    line = tcod.los.bresenham((unit.x, unit.y), (x, y)).tolist()
    return [tuple(p) for p in line[1:]]


def teleport(engine, x: int, y: int) -> None:
    """Put the player on (x, y), loading the chunk there first (and, as for any border crossing, its neighbours)."""
    world = engine.game_map
    if world.load_chunk(chunk_key(x, y)) is None:
        raise exceptions.Impossible("Nothing can be reached there.")
    engine.player.set_position(x, y)
    world.update_tiers()
    engine.update_fov()


def jump(engine, dx: int, dy: int, whole_chunk: bool) -> None:
    """God Mode jump: 10 tiles, or one chunk, in direction (dx, dy)."""
    player = engine.player
    if whole_chunk:
        teleport(engine, player.x + dx * CHUNK_W, player.y + dy * CHUNK_H)
    else:
        teleport(engine, player.x + dx * 10, player.y + dy * 10)
