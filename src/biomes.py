"""Biomes: climate-driven ground types (landmarks, the distinctive regions, live in `landmarks.py`).

Every point of a planet has three environmental numbers, all deterministic functions of the planet seed
(`worldgen.TerrainNoise`): **temperature** `t` and **moisture** `m` (both about -1..1, smooth over a few hundred tiles)
and **elevation** `h` (the existing height noise). `classify` maps `(t, m)` to one *base biome* (a Whittaker-style table:
cold-dry tundra ... hot-wet jungle), and then two overlays may replace it:

- **wetland**: very wet, low ground becomes swamp (warm) or bog (cold),
- **special region**: a separate slowly varying noise marks volcanic fields (hot), crystalline formations (cold or
  anywhere rare) and alien fungal regions (wet); ruins/settlements are *structures* (see `shafts`), not biomes.

Climate and terrain are kept apart from biome identity on purpose: a creature or plant asks for temperature, moisture and
elevation ranges (`ecology.Habitat`), never for a biome name, so new biomes need no new species logic.

Every biome has an `ambient` temperature (degrees C at noon, before the planet's own offset) that the survival system
uses, a ground colour, and the stone families found there.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np  # type: ignore

RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class Biome:
    key: str
    name: str
    ambient: int                  # degrees C at noon
    night_drop: int               # degrees C colder at night
    ground: RGB                   # colour of open ground
    vegetation: float             # multiplier on how much of the ground is vegetated (0 = barren)
    stones: Tuple[str, ...]       # stone archetypes found on the surface here (see planet.STONE_ARCHETYPES)
    description: str


BIOMES: Dict[str, Biome] = {}
BIOME_IDS: List[str] = []


def _biome(*args, **kwargs) -> Biome:
    biome = Biome(*args, **kwargs)
    assert biome.key not in BIOMES
    BIOMES[biome.key] = biome
    BIOME_IDS.append(biome.key)
    return biome


_biome("glacial", "Glacial plain", -25, 8, (200, 215, 230), 0.05, ("pale", "crystal"), "Wind-scoured ice and snow.")
_biome("tundra", "Tundra", -10, 8, (150, 150, 130), 0.25, ("grey", "pale"), "Frozen ground with moss and thin shrubs.")
_biome("taiga", "Taiga", -2, 8, (70, 90, 70), 1.0, ("grey", "dark"), "Cold conifer forest.")
_biome("steppe", "Steppe", 8, 12, (150, 140, 90), 0.4, ("pale", "red"), "Cool, dry, open grassland.")
_biome("temperate_forest", "Temperate forest", 14, 8, (60, 100, 55), 1.2, ("grey", "dark"), "Mixed woodland.")
_biome("grassland", "Grassland", 16, 9, (105, 140, 70), 0.5, ("pale", "red"), "Rolling meadow.")
_biome("shrubland", "Shrubland", 22, 11, (130, 125, 80), 0.6, ("red", "pale"), "Dry scrub.")
_biome("savanna", "Savanna", 30, 12, (170, 150, 75), 0.45, ("red", "pale"), "Warm grass with scattered trees.")
_biome("jungle", "Jungle", 28, 6, (35, 110, 55), 1.6, ("dark", "grey"), "Dense, hot and wet.")
_biome("badlands", "Badlands", 34, 18, (170, 105, 70), 0.15, ("red", "dark"), "Eroded, banded rock.")
_biome("desert", "Desert", 38, 25, (205, 180, 120), 0.08, ("pale", "red"), "Sand and rock under a harsh sun.")
_biome("swamp", "Swamp", 22, 6, (70, 90, 50), 1.1, ("dark",), "Warm, flooded ground.")
_biome("bog", "Bog", 6, 6, (85, 80, 55), 0.7, ("dark", "grey"), "Cold peat and standing water.")

BIOME_INDEX: Dict[str, int] = {key: i for i, key in enumerate(BIOME_IDS)}

# Whittaker table, first match wins: (key, max_t, max_m) with ranges expressed through the checks in `classify`.


def classify(t: np.ndarray, m: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Biome index (into `BIOME_IDS`) for arrays of temperature, moisture and elevation.

    Total function: every input maps to exactly one biome.
    """
    shape = np.broadcast(t, m, h).shape
    t, m, h = (np.broadcast_to(a, shape) for a in (t, m, h))
    out = np.full(shape, BIOME_INDEX["desert"], dtype=np.int16)

    def put(key: str, mask: np.ndarray) -> None:
        out[mask & (out == BIOME_INDEX["desert"]) & ~assigned] = BIOME_INDEX[key]
        assigned[mask] = True

    assigned = np.zeros(shape, dtype=bool)
    rules = (
        ("glacial", t < -0.55),
        ("tundra", (t < -0.3) & (m < 0.0)),
        ("taiga", t < -0.3),
        ("steppe", (t < 0.0) & (m < -0.15)),
        ("temperate_forest", (t < 0.25) & (m > 0.2)),
        ("grassland", (t < 0.25) & (m > -0.1)),
        ("shrubland", t < 0.25),
        ("jungle", m > 0.3),
        ("savanna", m > -0.2),
        ("badlands", m > -0.45),
    )
    for key, mask in rules:
        put(key, mask)
    # overlay
    wet_low = (m > 0.45) & (h < 0.15) & (t > -0.3)
    out[wet_low & (t >= 0.1)] = BIOME_INDEX["swamp"]
    out[wet_low & (t < 0.1)] = BIOME_INDEX["bog"]
    return out


def biome_at(t: float, m: float, h: float) -> Biome:
    return BIOMES[BIOME_IDS[int(classify(np.array(t), np.array(m), np.array(h)))]]


def ground_colors(index: np.ndarray) -> np.ndarray:
    """(…, 3) uint8 ground colour for an array of biome indexes."""
    table = np.array([BIOMES[k].ground for k in BIOME_IDS], dtype=np.uint8)
    return table[index]


def validate_content() -> None:
    from capabilities import validate_content as _  # noqa: F401  (import check only)
    for biome in BIOMES.values():
        assert biome.vegetation >= 0 and biome.stones, biome.key
        assert all(0 <= c <= 255 for c in biome.ground)
