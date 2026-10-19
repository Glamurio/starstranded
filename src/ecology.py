"""Environmental suitability: where a species can live.

A `Habitat` states what an organism needs: temperature, moisture, elevation, soil fertility, light and nearness to water
(each an inclusive range on the environment scales below) and, optionally, which special substrates (biome keys) it is
restricted to. `suitability` turns that and an environment into a weight between 0 (cannot live here) and 1 (ideal): a
trapezoid per requirement (full inside the range, falling to 0 over `SOFT` outside it) multiplied together, so every
requirement is binding. Species templates in `planet.py` use it to decide where they spawn.

Environment scales (the same ones `biomes` uses): temperature and moisture about -1..1, elevation the height noise
(about -1..1), fertility 0..1 (richness of the ground, from the biome's vegetation), light 0 (underground) .. 1 (open sky),
water 0 (far from liquid) .. 1 (at the shore). All functions work on numpy arrays or scalars.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple, Union

import numpy as np  # type: ignore

Range = Tuple[float, float]
SOFT = 0.2
"""Width of the falloff outside a range."""
ANY: Range = (-10.0, 10.0)


@dataclass(frozen=True)
class Habitat:
    temperature: Range = ANY
    moisture: Range = ANY
    elevation: Range = ANY
    fertility: Range = (0.0, 1.0)
    light: Range = (0.0, 1.0)
    water: Range = (0.0, 1.0)
    substrate: Tuple[str, ...] = ()   # biome keys the species is restricted to; () = any
    landmarks: Tuple[str, ...] = ()   # landmark keys the species is restricted to (see `landmarks`); () = any

    def __post_init__(self):
        for name in ("temperature", "moisture", "elevation", "fertility", "light", "water"):
            lo, hi = getattr(self, name)
            assert lo <= hi, f"habitat {name} range is inverted"


Env = Mapping[str, Union[float, np.ndarray]]
"""Keys: temperature, moisture, elevation, fertility, light, water, biome (array of biome keys' indexes or a str)."""


def membership(value, rng: Range, soft: float = SOFT):
    """1 inside `rng`, linearly down to 0 at `soft` outside it."""
    lo, hi = rng
    value = np.asarray(value, dtype=float)
    below = np.clip(1.0 - (lo - value) / soft, 0.0, 1.0)
    above = np.clip(1.0 - (value - hi) / soft, 0.0, 1.0)
    return np.minimum(below, above)


LEGACY_BIOMES = {"fungal": "mushroom_forest", "volcanic": "volcanic_mountains", "crystalline": "crystal_badlands"}
"""Biomes of earlier versions that are landmarks now (so an old save's species still find a home)."""


def suitability(habitat: Habitat, env: Env):
    """Weight 0..1 of living in `env` (scalars or arrays). Product of all requirement memberships."""
    weight = 1.0
    for name in ("temperature", "moisture", "elevation", "fertility", "light", "water"):
        weight = weight * membership(env[name], getattr(habitat, name))
    from biomes import BIOME_INDEX
    from landmarks import LANDMARK_INDEX
    substrate = [k for k in habitat.substrate if k in BIOME_INDEX]
    # (a save made before landmarks existed names biomes that became landmarks: they now mean the landmark)
    landmark_keys = tuple(habitat.landmarks) + tuple(LEGACY_BIOMES[k] for k in habitat.substrate if k in LEGACY_BIOMES)
    if substrate:
        allowed = np.array([BIOME_INDEX[k] for k in substrate])
        weight = weight * np.isin(np.asarray(env["biome"]), allowed)
    if landmark_keys:
        allowed = np.array([LANDMARK_INDEX[k] for k in landmark_keys])
        weight = weight * np.isin(np.asarray(env.get("landmark", 0)), allowed) * np.asarray(env.get("landmark_strength", 1.0))
    return weight
