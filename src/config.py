"""Game tunables. One `GameConfig` instance is owned by the Engine (`engine.config`) and passed explicitly."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameConfig:
    fov_radius: int = 80
    """Player FOV radius in tiles. 80 = ceil(sqrt(69**2 + 39**2)): the whole 70x40 map stays visible from anywhere
    (the behaviour of the old hard-coded radius=100). Once the camera is centred on the player (Phase 5), ~41
    (half-diagonal of a 70x40 view) is the sensible value."""

    flee_attempts: int = 50
    """How many random tiles a fleeing AI tries before giving up (the old loop could spin forever)."""


DEFAULT_CONFIG = GameConfig()
