"""Scenery: the quiet things that make ground look lived-in (pebbles, small rocks, bones, skulls, rubble).

A scenery piece is not an item: it cannot be picked up, blocks nothing, is drawn faint under everything and is named on hover.
What lies where is data (`SCENERY`): each kind has a base chance per tile, a weight per biome and per landmark, and how much
more likely it is among rocks. Chances are read from the coordinate hash of `TerrainNoise.scatter`, so a tile's scenery does not
depend on how the world is cut into chunks. Placement rules (`tile_is_free`) keep it from burying anything you can use."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

import biomes
import landmarks
from entity import Entity
from render_order import RenderOrder
from species import ItemKind, register

RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class SceneryKind:
    key: str
    name: str
    sprites: Tuple[Tuple[int, int], ...]
    color: RGB
    chance: float                                   # per open tile, in a biome of weight 1
    biome: Dict[str, float] = field(default_factory=dict)     # weight per biome (missing = `default`)
    landmark: Dict[str, float] = field(default_factory=dict)  # weight inside a landmark (replaces the biome's)
    default: float = 1.0
    rocky: float = 0.0                              # extra chance per unit of nearby rock (0..1)
    near_ruin: float = 0.0                          # extra weight near a precursor ruin chunk


SCENERY: Tuple[SceneryKind, ...] = (
    SceneryKind("pebbles", "Pebbles", ((14, 6), (5, 26)), (165, 160, 150), 0.006,
                biome=dict(grassland=0.6, temperate_forest=0.5, jungle=0.3, swamp=0.3, bog=0.3, desert=1.4, badlands=2.0, tundra=1.3),
                landmark=dict(beach=1.8, mushroom_forest=0.3, flowering_meadow=0.4), rocky=3.0),
    SceneryKind("small_rocks", "Small rocks", ((2, 12), (5, 12)), (140, 135, 128), 0.0025,
                biome=dict(grassland=0.4, jungle=0.2, swamp=0.2, bog=0.3, badlands=2.5, desert=1.2, tundra=1.5, glacial=1.5, steppe=1.0),
                landmark=dict(crystal_badlands=2.5, volcanic_mountains=3.0, mushroom_forest=0.2, flowering_meadow=0.2), rocky=4.0),
    SceneryKind("bones", "Scattered bones", ((5, 27),), (205, 198, 180), 0.0009,
                biome=dict(desert=3.0, badlands=3.0, savanna=2.0, steppe=1.5, tundra=1.2, glacial=1.0, grassland=0.6, temperate_forest=0.3,
                           jungle=0.2, swamp=0.4, bog=0.5, taiga=0.5, shrubland=1.0),
                landmark=dict(decayed_land=5.0, cactus_desert=3.5, mushroom_forest=0.2, flowering_meadow=0.1, beach=0.8)),
    SceneryKind("skull", "Skull", ((7, 26),), (215, 210, 195), 0.0004,
                biome=dict(desert=2.5, badlands=2.5, savanna=1.5, steppe=1.0, grassland=0.4, jungle=0.1, temperate_forest=0.2, swamp=0.2),
                landmark=dict(decayed_land=6.0, cactus_desert=3.0, flowering_meadow=0.0, mushroom_forest=0.0), near_ruin=4.0),
    SceneryKind("rubble", "Rubble", ((19, 6), (18, 6)), (150, 145, 140), 0.0004, default=0.0,
                landmark=dict(decayed_land=6.0), near_ruin=12.0),
)
BY_KEY: Dict[str, SceneryKind] = {k.key: k for k in SCENERY}

KINDS: Dict[str, ItemKind] = {
    k.key: register(ItemKind(f"scenery_{k.key}", "Scenery", species=k.name, sprite=k.sprites[0], color=k.color, shade_sigma=8,
                             render_order=RenderOrder.DECAL))
    for k in SCENERY
}


class Scenery(Entity):
    """A pebble, a rock, a bone: scenery you can look at, step over and (for now) do nothing with."""
    object_type = "Scenery"
    scenery = True

    def __init__(self, key: str, variant: int = 0, shade: Optional[RGB] = None):
        Entity.__init__(self, KINDS[key])
        self.scenery_key = key
        self.variant = variant
        self.color = self.shade = tuple(shade) if shade is not None else BY_KEY[key].color
        self.mirrored = bool(variant & 1)

    @property
    def spec(self) -> SceneryKind:
        return BY_KEY[self.scenery_key]

    @property
    def sprite_id(self) -> int:
        from tile_types import sprite_id
        sprites = self.spec.sprites
        return sprite_id(*sprites[self.variant % len(sprites)])

    @property
    def species(self) -> str:
        return self.spec.name

    def get_title(self, exclude_attributes: bool = False) -> str:
        return self.spec.name


def _box_mean(mask: np.ndarray, radius: int) -> np.ndarray:
    """Mean of `mask` over the (2r+1)-square around each cell (edges use what exists)."""
    padded = np.pad(mask.astype(float), radius + 1)
    total = padded.cumsum(0).cumsum(1)
    size = 2 * radius + 1
    h, w = mask.shape
    s = (total[size:size + h, size:size + w] - total[:h, size:size + w] - total[size:size + h, :w] + total[:h, :w])
    return s / (size * size)


def weights(kind: SceneryKind, env: dict) -> np.ndarray:
    """The kind's weight on every tile of the chunk: landmark weight where a landmark is strong, else the biome's."""
    table = np.array([kind.biome.get(key, kind.default) for key in biomes.BIOME_IDS], dtype=float)
    out = table[env["biome"]]
    if kind.landmark:
        lm = np.array([kind.landmark.get(key, np.nan) for key in landmarks.LANDMARK_IDS], dtype=float)
        index = np.clip(env["landmark"], 0, len(lm) - 1)
        strength = np.clip(env["landmark_strength"], 0, 1)
        value = lm[index]
        have = ~np.isnan(value) & (env["landmark"] >= 0)
        out = np.where(have, out * (1 - strength) + np.nan_to_num(value) * strength, out)
    return out


def tile_is_free(world, x: int, y: int, reserved=()) -> bool:
    """Scenery goes only on open, dry, walkable ground with nothing on it: never under a bush, an item or a creature."""
    if (x, y) in reserved or not world.in_bounds(x, y) or not world.is_walkable(x, y) or world.is_blocked(x, y):
        return False
    tile = world.tile_at(x, y)
    if tile is None or int(tile["liquid"]) or int(tile["stairs"]) or bool(tile["open"]):
        return False
    return not world.get_entities_at_location(x, y)


def populate(source, world, chunk, env: dict, reserved, ruin_chunk: bool = False) -> int:
    """Place the chunk's scenery. Returns how many pieces were placed."""
    from chunks import CHUNK_H, CHUNK_W
    noise = source.noise
    rock = _box_mean(~chunk.tiles["walkable"][:CHUNK_W, :CHUNK_H], 3)
    placed = 0
    for number, kind in enumerate(SCENERY):
        chance = kind.chance * weights(kind, env) * (1.0 + kind.rocky * rock)
        if ruin_chunk and kind.near_ruin:
            chance = chance * (1.0 + kind.near_ruin)
        draw = noise.scatter(2000 + number, chunk.x0, chunk.y0, CHUNK_W, CHUNK_H)
        pick = noise.scatter(3000 + number, chunk.x0, chunk.y0, CHUNK_W, CHUNK_H)
        for lx, ly in np.argwhere(draw < chance).tolist():
            x, y = chunk.x0 + lx, chunk.y0 + ly
            if not tile_is_free(world, x, y, reserved):
                continue
            variant = int(pick[lx, ly] * 1000)
            world.add_entity(Scenery(kind.key, variant), x, y)
            placed += 1
    return placed
