"""Landmarks: distinctive, spatially coherent regions (a mushroom forest, a cactus desert, crystal badlands ...).

Biomes (`biomes.py`) say what the *climate* is. A landmark is a separate layer on top of it: a large patch with its own
look (ground colour, ground cover, how thickly plants grow), its own species (`Habitat.landmarks` in `ecology`) and its own
music pool. A landmark may only form where the climate suits it: each one has a `climate` habitat (temperature, moisture,
elevation, water ...), so a tropical beach cannot appear on a frozen mountain whatever its noise says.

How a tile gets its landmark (all pure functions of the planet seed, so chunks agree and nothing is saved):

1. every landmark has its own slowly varying noise (`scale`); where it rises above `threshold` the landmark wants the tile
   (`fade` is the width of the soft edge, so borders are gradual, not lines);
2. that is multiplied by how well the tile's climate suits it (`ecology.suitability`);
3. where several landmarks want the same tile the strongest wins, so landmarks never overlap.

`field` returns the winner and its strength (0..1). The strength drives the blend of the ground colour, the density of
vegetation and the share of tiles that carry the landmark's species, so a landmark has a core and a thin edge.

Adding a landmark is adding one `_landmark(...)` line below (and, if it has species, templates in `planet.py`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np  # type: ignore

from ecology import Habitat, suitability

RGB = Tuple[int, int, int]
Cell = Tuple[int, int]
NOISE_BASE = 8
"""Noise generators 0-7 of `worldgen.TerrainNoise` are the terrain and climate ones; landmark `i` uses `NOISE_BASE + i`."""


@dataclass(frozen=True)
class Landmark:
    key: str
    name: str
    description: str
    climate: Habitat                  # where the landmark may form (the same ranges species use)
    scale: float = 0.0045             # noise frequency: features are about 1 / scale tiles across
    threshold: float = 0.3            # noise above this is inside the landmark: higher = rarer and smaller
    fade: float = 0.12                # width of the soft edge, in noise units
    ground: RGB = (128, 128, 128)     # colour blended into the biome's ground
    ground_mix: float = 0.7           # how far (at full strength) the ground moves to `ground`
    cover: Tuple[Cell, ...] = ()      # ground cover sprites (sheet cells) used instead of the biome's; () = the biome's
    vegetation: float = 1.0           # multiplies how thickly open ground is vegetated
    ambient: int = 0                  # degrees C added to the biome's temperature at full strength
    stones: Tuple[str, ...] = ()      # stone archetypes found here in addition to the biome's
    music: str = ""                   # soundtrack pool key (see the music manifest)


LANDMARKS: Dict[str, Landmark] = {}
LANDMARK_IDS: List[str] = []


def _landmark(*args, **kwargs) -> Landmark:
    landmark = Landmark(*args, **kwargs)
    assert landmark.key not in LANDMARKS
    LANDMARKS[landmark.key] = landmark
    LANDMARK_IDS.append(landmark.key)
    return landmark


_TUFTS = ((3, 9), (4, 9), (5, 9), (1, 9), (7, 9), (8, 9), (9, 9))
_DRY = ((3, 9), (4, 9), (5, 9))

_landmark("mushroom_forest", "Mushroom forest", "Damp, dim ground under towering fungi, strange and soft-coloured.",
          Habitat(temperature=(-0.4, 0.8), moisture=(0.15, 1.0)),
          threshold=0.26, ground=(120, 66, 128), ground_mix=0.8, cover=_TUFTS + ((2, 10), (3, 10), (2, 10), (3, 10)),
          vegetation=1.7, stones=("dark",), music="mushroom_forest")
_landmark("cactus_desert", "Cactus desert", "Baked sand, bare red rock and a scatter of cacti.",
          Habitat(temperature=(0.25, 1.2), moisture=(-1.2, -0.25)),
          threshold=0.0, ground=(222, 156, 84), ground_mix=0.65, cover=_DRY, vegetation=0.8, ambient=4,
          stones=("red", "pale"), music="cactus_desert")
_landmark("crystal_badlands", "Crystalline badlands", "Broken rock and cold, glittering crystal under a hard sky.",
          Habitat(temperature=(-0.5, 0.5), moisture=(-1.2, 0.25), elevation=(-0.15, 1.2)),
          threshold=0.26, ground=(112, 132, 190), ground_mix=0.7, cover=_DRY, vegetation=0.25, stones=("crystal", "pale"),
          music="crystal_badlands")
_landmark("volcanic_mountains", "Volcanic mountains", "Black rock, ash and vents where the ground is too hot to rest on.",
          Habitat(temperature=(0.2, 1.2), moisture=(-0.9, 0.4), elevation=(-0.05, 1.2)),
          threshold=0.1, ground=(58, 38, 40), ground_mix=0.85, cover=_DRY, vegetation=0.12, ambient=26,
          stones=("dark", "red"), music="volcanic_mountains")
_landmark("decayed_land", "Decaying landscape", "Dead trees on grey ground, a place where something went wrong.",
          Habitat(temperature=(-0.3, 1.0), moisture=(-0.3, 0.7)),
          threshold=0.36, ground=(78, 66, 84), ground_mix=0.75, cover=_DRY, vegetation=0.4, stones=("dark", "grey"),
          music="decayed_land")
_landmark("flowering_meadow", "Flowering meadow", "Open, airy grass in pale colours, thick with wildflowers.",
          Habitat(temperature=(-0.2, 0.6), moisture=(0.0, 0.8), elevation=(-0.4, 0.3)),
          threshold=0.26, ground=(150, 190, 120), ground_mix=0.55, cover=_TUFTS, vegetation=0.55, stones=("pale",),
          music="flowering_meadow")

LANDMARK_INDEX: Dict[str, int] = {key: i + 1 for i, key in enumerate(LANDMARK_IDS)}
"""Landmark key -> its number in landmark arrays (0 means no landmark)."""
SPAWN = (35, 20)
SPAWN_CLEAR, SPAWN_FULL = 60, 160
"""Landmarks fade out towards the landing site: none within `SPAWN_CLEAR` tiles of it, full strength from `SPAWN_FULL`
(a volcanic field or a crystal waste under the first camp would be a cruel start)."""
MIN_STRENGTH = 0.04
"""Below this a tile counts as outside every landmark (the faint tail of a soft edge)."""


def smooth(x: np.ndarray) -> np.ndarray:
    """Smoothstep of a clipped 0..1 array."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def climate_of(noise, x0: int, y0: int, width: int, height: int, env: dict) -> dict:
    """The climate a landmark is judged against: `env` with only the smooth large-scale relief as elevation (the tile-to-tile
    roughness of `env["elevation"]` would speckle the edges). Fertility (a step per biome) and shore distance are not in any
    landmark's habitat, so climate alone shapes a landmark."""
    return dict(env, elevation=noise.sample(0, 0.05, x0, y0, width, height))


def field(noise, x0: int, y0: int, width: int, height: int, env: dict) -> Tuple[np.ndarray, np.ndarray]:
    """`(index, strength)` of the landmark at every tile of a world rectangle: `index` is 0 or `LANDMARK_INDEX[key]`,
    `strength` 0..1. `env` holds the rectangle's climate arrays (temperature, moisture, elevation, fertility, light, water)."""
    climate = climate_of(noise, x0, y0, width, height, env)
    best = np.zeros((width, height), dtype=np.float64)
    index = np.zeros((width, height), dtype=np.int8)
    for i, key in enumerate(LANDMARK_IDS):
        landmark = LANDMARKS[key]
        wants = smooth((noise.sample(NOISE_BASE + i, landmark.scale, x0, y0, width, height) - landmark.threshold) / landmark.fade)
        strength = wants * suitability(landmark.climate, climate)
        better = strength > best
        best = np.where(better, strength, best)
        index = np.where(better, np.int8(i + 1), index)
    xs = np.arange(x0, x0 + width)[:, None] - SPAWN[0]
    ys = np.arange(y0, y0 + height)[None, :] - SPAWN[1]
    best = best * smooth((np.hypot(xs, ys) - SPAWN_CLEAR) / (SPAWN_FULL - SPAWN_CLEAR))
    index[best < MIN_STRENGTH] = 0
    best[best < MIN_STRENGTH] = 0.0
    return index, best


def blend_ground(ground: np.ndarray, index: np.ndarray, strength: np.ndarray) -> np.ndarray:
    """The biome's ground colours (…, 3) moved towards each landmark's colour by its strength."""
    out = ground.astype(float)
    for key, number in LANDMARK_INDEX.items():
        landmark = LANDMARKS[key]
        mix = np.where(index == number, strength * landmark.ground_mix, 0.0)[..., None]
        out = out * (1.0 - mix) + np.array(landmark.ground, dtype=float) * mix
    return out.astype(np.uint8)


def blend_density(density: np.ndarray, index: np.ndarray, strength: np.ndarray) -> np.ndarray:
    """Vegetation density scaled towards each landmark's `vegetation` multiplier by its strength."""
    factor = np.ones(density.shape)
    for key, number in LANDMARK_INDEX.items():
        factor = np.where(index == number, 1.0 + (LANDMARKS[key].vegetation - 1.0) * strength, factor)
    return density * factor


def key_of(number: int) -> str:
    """Landmark key for an array value ('' for none)."""
    return LANDMARK_IDS[number - 1] if number else ""


def validate_content() -> None:
    from planet import STONE_ARCHETYPES
    for landmark in LANDMARKS.values():
        assert -0.5 < landmark.threshold < 1.0 and landmark.fade > 0, landmark.key
        assert all(0 <= c <= 255 for c in landmark.ground), landmark.key
        assert landmark.cover and all(s in STONE_ARCHETYPES for s in landmark.stones), landmark.key
