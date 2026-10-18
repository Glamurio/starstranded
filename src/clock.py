"""Small helpers over the game clock."""
from __future__ import annotations


def days_survived(engine) -> int:
    """Whole days since the crash."""
    return int(engine.game_world.current_time // engine.config.day_length) + 1
