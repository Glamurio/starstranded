"""Scenery: the quiet things that make ground look lived-in (pebbles, small rocks, bones, skulls, rubble).

A scenery piece is not an item: it cannot be picked up, blocks nothing, is drawn faint under everything and is named on hover.
What lies where is data (`SCENERY`): each kind has a base chance per tile, a weight per biome family and per biome, and how much
more likely it is among rocks. Chances are read from the coordinate hash of `TerrainNoise.scatter`, so a tile's scenery does not
depend on how the world is cut into chunks. Placement rules (`tile_is_free`) keep it from burying anything you can use."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

import biomes
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
    family: Dict[str, float] = field(default_factory=dict)    # weight per biome family (missing = `default`); a biome's own `scenery` replaces it
    default: float = 1.0
    rocky: float = 0.0                              # extra chance per unit of nearby rock (0..1)
    near_ruin: float = 0.0                          # extra weight near a precursor ruin chunk


def _fam(**kw: float) -> Dict[str, float]:
    return dict(kw)


# Kinds with default 0 appear only where a biome lists them in `Biome.scenery`.
SCENERY: Tuple[SceneryKind, ...] = (
    SceneryKind("pebbles", "Pebbles", ((14, 6), (5, 26)), (165, 160, 150), 0.006,
                family=_fam(grass=0.6, arid=1.4, forest=0.4, fungal=0.3, crystal=1.2, volcanic=1.5, decay=1.2, alien=0.3, wet=0.3, cold=1.3, coast=1.8, urban=1.0), rocky=3.0),
    SceneryKind("small_rocks", "Small rocks", ((2, 12), (5, 12)), (140, 135, 128), 0.0025,
                family=_fam(grass=0.4, arid=1.5, forest=0.3, fungal=0.2, crystal=2.0, volcanic=3.0, decay=1.0, alien=0.2, wet=0.2, cold=1.5, coast=1.0, urban=1.0), rocky=4.0),
    SceneryKind("bones", "Scattered bones", ((5, 27),), (205, 198, 180), 0.0009,
                family=_fam(grass=0.6, arid=3.0, forest=0.3, fungal=0.2, crystal=0.5, volcanic=1.0, decay=5.0, alien=0.5, wet=0.4, cold=1.2, coast=0.8, urban=0.8)),
    SceneryKind("skull", "Skull", ((7, 26),), (215, 210, 195), 0.0004,
                family=_fam(grass=0.4, arid=2.5, forest=0.2, fungal=0.0, crystal=0.3, volcanic=0.8, decay=6.0, alien=0.5, wet=0.2, cold=0.8, coast=0.4, urban=0.5), near_ruin=4.0),
    SceneryKind("rubble", "Rubble", ((19, 6), (18, 6)), (150, 145, 140), 0.0004, default=0.0, family=_fam(decay=1.0, urban=3.0), near_ruin=12.0),
    # what makes a biome look like itself (default 0: only biomes that list them)
    SceneryKind("crystal_cluster", "Crystal cluster", ((7, 11), (8, 11), (5, 11)), (150, 190, 240), 0.002, default=0.0, rocky=2.0),
    SceneryKind("salt_crust", "Salt crust", ((9, 11), (10, 11)), (235, 235, 225), 0.003, default=0.0),
    SceneryKind("glass_shards", "Glass shards", ((5, 13), (4, 13)), (190, 225, 235), 0.003, default=0.0),
    SceneryKind("obsidian", "Obsidian", ((10, 11), (11, 11)), (40, 35, 50), 0.002, default=0.0, rocky=2.0),
    SceneryKind("ash_pile", "Ash pile", ((12, 11),), (95, 90, 90), 0.003, default=0.0),
    SceneryKind("mushroom_ring", "Mushroom ring", ((2, 10), (3, 10)), (190, 140, 200), 0.002, default=0.0),
    SceneryKind("stump", "Stump", ((4, 10),), (110, 85, 60), 0.002, default=0.0),
    SceneryKind("tendrils", "Tendrils", ((23, 8), (24, 8)), (190, 90, 110), 0.003, default=0.0),
    SceneryKind("gravestone", "Gravestone", ((0, 11),), (150, 150, 145), 0.001, default=0.0),
    SceneryKind("driftwood", "Driftwood", ((4, 10),), (170, 150, 120), 0.002, default=0.0),
    SceneryKind("shell", "Shell", ((14, 6),), (235, 215, 200), 0.002, default=0.0),
    SceneryKind("monolith", "Standing stone", ((1, 11),), (120, 118, 125), 0.0004, default=0.0),
    SceneryKind("lamp_post", "Lamp post", ((73, 3),), (150, 150, 150), 0.001, default=0.0),
    SceneryKind("signpost", "Signpost", ((60, 5),), (170, 160, 140), 0.001, default=0.0),
    SceneryKind("wreck_car", "Wrecked car", ((59, 7),), (130, 100, 90), 0.0006, default=0.0),
    SceneryKind("wreck_truck", "Wrecked truck", ((50, 7),), (120, 110, 95), 0.0004, default=0.0),
    SceneryKind("pipe", "Broken pipe", ((57, 3),), (130, 120, 110), 0.0015, default=0.0),
    SceneryKind("drum", "Rusted drum", ((76, 7),), (140, 90, 60), 0.0012, default=0.0),
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


STONE_KINDS = ("pebbles", "small_rocks", "rubble")
"""These take their colour from the stones of the planet's rock in the biome (so they differ from planet to planet)."""
STONE_SHARE = 0.65


def vary(color: RGB, hue: float, light: float) -> RGB:
    """`color` turned in hue by up to +-0.04 of the wheel and made up to 12% lighter or darker (`hue`, `light` are 0..1 draws)."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in color))
    r, g, b = colorsys.hsv_to_rgb((h + (hue - 0.5) * 0.08) % 1.0, s, max(0.0, min(1.0, v * (0.88 + 0.24 * light))))
    return (int(r * 255), int(g * 255), int(b * 255))


def _box_mean(mask: np.ndarray, radius: int) -> np.ndarray:
    """Mean of `mask` over the (2r+1)-square around each cell (edges use what exists)."""
    padded = np.pad(mask.astype(float), radius + 1)
    total = padded.cumsum(0).cumsum(1)
    size = 2 * radius + 1
    h, w = mask.shape
    s = (total[size:size + h, size:size + w] - total[:h, size:size + w] - total[size:size + h, :w] + total[:h, :w])
    return s / (size * size)


def weights(kind: SceneryKind, env: dict) -> np.ndarray:
    """The kind's weight on every tile of the chunk: the biome's own weight for it, else its family's, else the kind's default;
    over a region border the neighbour's weight comes in."""
    table = np.array([biomes.BIOMES[k].scenery.get(kind.key, kind.family.get(biomes.BIOMES[k].family, kind.default)) for k in biomes.BIOME_IDS], dtype=float)
    out = table[env["biome"]]
    if "other" in env:
        edge = np.asarray(env.get("edge", 0.0))
        out = out * (1.0 - edge) + table[env["other"]] * edge
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
            color = kind.color
            planet = getattr(source, "planet", None)
            if planet is not None and kind.key in STONE_KINDS:
                stones = planet.stones_for_biome(biomes.BIOME_IDS[int(env["biome"][lx, ly])])
                if stones:
                    stone = stones[variant % len(stones)].color
                    color = tuple(int(c * (1 - STONE_SHARE) + r * STONE_SHARE) for c, r in zip(color, stone))
            color = vary(color, (variant % 97) / 96.0, (variant % 89) / 88.0)
            world.add_entity(Scenery(kind.key, variant, color), x, y)
            placed += 1
    return placed
