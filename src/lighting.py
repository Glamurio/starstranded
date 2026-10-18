"""Day and night, and what the player can see because of them.

Seeing a tile needs two things: a line of sight to it (`fov_radius` is the farthest anyone can see) and light on it.
Light comes from

- **the ambient light** around the player: a radius that follows the sun (`day_view_radius` at noon down to
  `night_view_radius` in the dead of night; underground there is no sky, so always the night radius), and
- **light sources**: any entity that emits light (a lit campfire, later torches, glowing things) lights the tiles it has
  a clear line to within its own radius, and a lit tile in the player's line of sight is seen at any distance.

So at night the world is dark except a small circle around you and the pools around fires, which you can spot from far away.
"""
from __future__ import annotations

import math
from typing import Iterator, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import tcod.map
from tcod import libtcodpy

from entity import EntityCategory

if TYPE_CHECKING:
    from config import GameConfig
    from engine import Engine
    from entity import Entity
    from world import World


# ── the clock ──────────────────────────────────────────────────────────────────────
def phase(now: int, config: GameConfig) -> float:
    """Fraction of the day (0..1) at game time `now`; 0.25 is dawn, 0.5 noon, 0.75 dusk."""
    return ((now / config.day_length) + config.start_phase) % 1.0


def daylight(now: int, config: GameConfig) -> float:
    """How bright the sky is, 0 (night) to 1 (day): a smooth curve with a long day and a long night."""
    return min(1.0, max(0.0, 0.5 + 0.8 * math.sin(2 * math.pi * (phase(now, config) - 0.25))))


def clock_text(now: int, config: GameConfig) -> str:
    """"Day 3, 14:05": the day number (starting at 1) and the time on a 24 hour clock."""
    total = now / config.day_length + config.start_phase
    day = int(total) + 1
    minutes = int((total % 1.0) * 24 * 60)
    return f"Day {day}, {minutes // 60:02d}:{minutes % 60:02d}"


def ambient_radius(world: World, now: int, config: GameConfig) -> int:
    """How far the player sees by the ambient light (never more than `fov_radius`)."""
    light = daylight(now, config) if world.has_sky else 0.0
    radius = config.night_view_radius + (config.day_view_radius - config.night_view_radius) * light
    return min(config.fov_radius, int(round(radius)))


def darkness(world: World, now: int, config: GameConfig) -> float:
    """0 (bright) to 1 (night), for shading the map."""
    return 1.0 - (daylight(now, config) if world.has_sky else 0.0)


# ── light sources ──────────────────────────────────────────────────────────────────
def light_sources(world: World, rect) -> Iterator[Entity]:
    """Entities in the chunks under `rect` that are emitting light right now."""
    for chunk in world.chunks_in_rect(rect):
        for entity in chunk.lights:
            if entity.emits_light:
                yield entity


# ── visibility ─────────────────────────────────────────────────────────────────────
def compute_visibility(engine: Engine) -> Tuple[np.ndarray, np.ndarray]:
    """`(visible, lit)` on the view window: what the player sees, and the part of that lit by light sources."""
    world = engine.game_map
    config = engine.config
    now = engine.game_world.current_time
    window = world.window.ensure()
    ox, oy = window.origin
    transparent = window.transparent & window.in_bounds
    player = engine.player
    origin = (player.x - ox, player.y - oy)

    def fov(point, radius):
        return tcod.map.compute_fov(transparent, point, radius=radius, algorithm=libtcodpy.FOV_SYMMETRIC_SHADOWCAST)

    ambient = fov(origin, ambient_radius(world, now, config))
    lit = np.zeros_like(ambient)
    for source in light_sources(world, window.rect):
        lit |= fov((source.x - ox, source.y - oy), source.light_radius)
    lit &= window.in_bounds
    if lit.any():
        # a lit tile is seen from as far as the player's line of sight reaches
        visible = ambient | (lit & fov(origin, config.fov_radius))
    else:
        visible = ambient
    visible &= window.in_bounds
    return visible, lit & visible
