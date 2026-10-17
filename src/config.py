"""Game tunables. One `GameConfig` instance is owned by the Engine (`engine.config`) and passed explicitly."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameConfig:
    fov_radius: int = 41
    """Player FOV radius in tiles: 41 = half-diagonal of the 70x40 viewport (+1), so everything the camera shows can be
    seen and nothing far off-screen is. (Phase 0-4: 80, which made the whole single 70x40 map visible.)"""

    clutter_safeguard: bool = True
    """Limit the ground objects (corpses, items) drawn on one tile to `render_order.MAX_GROUND_OBJECTS_PER_TILE`, topmost
    first, and draw a stack marker when more are hidden. Off: draw them all (a big pile becomes an unreadable blob).
    Units, shrubs and trees are always drawn; hidden objects are still listed when you look at the tile."""

    near_radius: int = 1
    """Chunks within this Chebyshev distance of the player's chunk are loaded and simulated (NEAR tier, the player's own
    chunk is ACTIVE). Also the radius of the stitched view window (1 -> 3x3 chunks = 210x120 tiles)."""

    unload_radius: int = 2
    """Chunks further than this from the player's chunk are serialised and dropped (FAR). The band between
    `near_radius` and `unload_radius` stays loaded but frozen, so walking back and forth over a border does not thrash."""

    near_interval: int = 2
    """NEAR chunks are simulated every this many turns (upkeep for the whole interval + one simplified AI step)."""

    path_radius: int = 40
    """Pathfinding searches at most this many tiles (Chebyshev) around the origin; further destinations give no path."""

    smooth_scroll: bool = False
    """Reserved: pixel-smooth camera scrolling between tiles (not implemented; the camera moves tile by tile)."""

    flee_attempts: int = 50
    """How many random tiles a fleeing AI tries before giving up (the old loop could spin forever)."""


DEFAULT_CONFIG = GameConfig()
