"""Biomes: the identity of a region of the planet.

A **biome** is a large place with its own look and its own life: a fungal forest, a salt flat, a volcanic waste, an abandoned
city district. Biomes are laid out at world scale (`regions`: a few hundred tiles across, chosen by the planet's climate, the same
for every chunk and in any order of loading) and each one is *data*: its ground, ground cover, plants, rocks, scenery, climate,
animals, music, underground counterpart and the points of interest that suit it. There is no per-biome code; adding a biome is
adding one `_biome(...)` line below (and, if it needs plants of its own, a template in `planet.py`).

Three things are kept apart on purpose:

- **biome** - what a region *is* (this module). 72 of them, in 12 **families** (`FAMILIES`) that share defaults: music, animals,
  the underground below and the way living things adapt (`TRAITS`: a hot family's plants and creatures are heat-proof);
- **variant** - how hot, cold, wet or dry a tile is *for its biome* (`variant_bits`): they colour, thin or thicken the biome and
  change its temperature without changing what it is ("Cold Crystal Fields"); the list of named combinations to offer is
  in `docs/BIOMES.md`;
- **point of interest** - a single place inside a biome (`pois.py`): a wreck, a ruin, a research outpost. They take the
  biome's context but never replace it.

Where a biome forms: each has a climate (temperature, moisture and smooth elevation ranges, the scales of `ecology`) and a
`rarity`; the region assignment draws, for every cell of the world, among the biomes whose climate suits the cell, weighted by
rarity. Two biomes get applied on top of the regions by the terrain itself: **wetlands** (very wet low ground by water takes
the region's `wet_twin`) and **beaches** (the shore).

Each biome has an `ambient` temperature (degrees C at noon, before the planet's own offset) that the survival system uses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from functools import lru_cache

import numpy as np  # type: ignore

RGB = Tuple[int, int, int]
Cell = Tuple[int, int]
Range = Tuple[float, float]
ANY: Range = (-10.0, 10.0)


# ── families ───────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Family:
    key: str
    name: str
    music: str                 # the soundtrack pool of the family's own regions ("" = only the generic pool)
    generic: str               # the generic pool ('forest', 'plains', 'cold', 'wet', 'dry'...) used when `music` has no tracks
    under: str                 # the underground biome below (see `underground`)
    traits: Tuple[str, ...]    # how living things here are adapted (keys of `TRAITS`)


FAMILIES: Dict[str, Family] = {}


def _family(*args) -> Family:
    family = Family(*args)
    FAMILIES[family.key] = family
    return family


_family("grass", "Open grassland", "", "plains", "barren", ())
_family("arid", "Arid country", "", "dry", "salt", ("hot", "dry"))
_family("forest", "Forest", "", "forest", "rootbound", ())
_family("fungal", "Fungal country", "mushroom_forest", "forest", "mycelial", ("fungal", "wet"))
_family("crystal", "Crystalline country", "crystal_badlands", "dry", "crystal", ("crystal",))
_family("volcanic", "Volcanic country", "volcanic_mountains", "dry", "volcanic", ("hot", "volcanic"))
_family("decay", "Dead country", "decayed_land", "dry", "bone_vault", ("dead", "dry"))
_family("alien", "Alien growth", "alien", "wet", "warren", ("wet",))
_family("wet", "Wetland", "", "wet", "wet", ("wet",))
_family("cold", "Cold country", "", "cold", "ice", ("cold",))
_family("coast", "Shore", "beach", "plains", "wet", ())
_family("urban", "Abandoned cities", "urban", "plains", "infrastructure", ())

TRAITS: Dict[str, Dict[str, float]] = {
    "hot": dict(insulation=2.0, thermal_conductivity=-1.0, flammability=-1.5, combustibility=-1.5),
    "cold": dict(insulation=2.5, thermal_conductivity=-1.0, tenacity=1.0, density=0.5),
    "wet": dict(flammability=-2.0, combustibility=-2.0, elasticity=1.0),
    "dry": dict(flammability=1.5, combustibility=1.5, density=-0.5, toughness=1.0),
    "volcanic": dict(hardness=1.5, flammability=-2.5, density=1.0),
    "crystal": dict(hardness=2.0, toughness=-1.5, density=1.0),
    "fungal": dict(insulation=1.5, toughness=-2.0, hardness=-1.5, density=-1.5),
    "dead": dict(hardness=-1.0, toughness=-1.0, flammability=2.0),
    "petrified": dict(hardness=3.0, density=2.5, flammability=-3.0, combustibility=-3.0, elasticity=-3.0),
    "toxic": dict(tenacity=1.0, toughness=1.0),
    "salty": dict(density=1.0, flammability=-1.0, hardness=1.0),
    "fleshy": dict(elasticity=2.0, toughness=1.0, hardness=-2.0, flammability=-1.0),
    "glassy": dict(hardness=2.5, toughness=-2.0, thermal_conductivity=1.0, flammability=-2.0),
}
"""Property shifts applied to the wood, fibre and hide of every plant and animal that lives only in a biome or family with the trait
(so a scorching region's species are heat-proof: well insulating, poorly conducting, hard to light)."""


def trait_bias(traits) -> Dict[str, float]:
    """The summed property shifts of some traits."""
    out: Dict[str, float] = {}
    for name in traits:
        for prop, delta in TRAITS[name].items():
            out[prop] = out.get(prop, 0.0) + delta
    return out


# ── urban style ─────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class UrbanStyle:
    """How a city region is laid out (see `urban`): a grid of streets with a block of lots between them."""
    pitch: Tuple[int, int] = (26, 20)      # street spacing (x, y) in tiles
    road: int = 3                          # street width
    built: float = 0.8                     # share of lots with a building
    ruin: float = 0.3                      # share of a building's wall that has fallen
    towers: float = 0.15                   # share of buildings that are solid tower blocks
    vehicles: float = 0.05                 # wrecks per street tile
    overgrown: float = 0.0                 # share of the open ground that is wild again (trees, bushes) 0 .. 1
    industrial: float = 0.0                # share of lots that are factories
    huts: bool = False                     # small stone huts instead of a street grid (an old settlement)


# ── the catalogue ───────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Biome:
    key: str
    name: str
    family: str
    description: str
    features: str                           # what makes it recognisable, for the catalogue
    temperature: Range                      # climate in which a region of it may form
    moisture: Range
    elevation: Range = ANY                  # (smooth elevation)
    rarity: float = 1.0                     # weight among the biomes that suit a cell
    ambient: int = 15                       # degrees C at noon
    night_drop: int = 9                     # degrees C colder at night
    ground: RGB = (110, 130, 80)
    ground_alt: Optional[RGB] = None        # a second ground colour that patches of the ground take
    alt_share: float = 0.3
    texture: Tuple[Cell, ...] = ()          # sprites that mottle the open ground (see worldgen `_texture_ground`)
    vegetation: float = 0.5                 # how much of the ground is vegetated (0 = barren)
    floor_density: float = 0.0              # at least this much vegetation density
    tree_share: float = 1.0                 # tree weight against shrubs
    cover: Tuple[Cell, ...] = ()            # ground cover sprites (tufts, ferns...)
    cover_boost: float = 1.0                # multiplies the share of ground that carries cover
    plants: Dict[str, float] = field(default_factory=dict)    # plant template -> weight (missing = 1.0)
    plants_only: bool = False               # only the listed plants grow
    stones: Tuple[str, ...] = ("grey",)     # stone archetypes found on the surface
    scenery: Dict[str, float] = field(default_factory=dict)   # scenery kind -> weight here (missing = the kind's default)
    rock_tint: Optional[RGB] = None         # colour of mountain rock (None = ordinary stone, snow on the crests)
    rock_mix: float = 0.0
    outcrops: float = 0.0                   # extra loose rock formations (a mineral labyrinth is mostly outcrop)
    flood: float = 0.0                      # share of the low ground that is shallow water
    liquid: int = 0                         # kind of its lakes when it has to be one (0 = by the planet's own field)
    hot_springs: float = 0.0                # multiplies the chance of a hot spring (volcanic and geothermal ground)
    urban: Optional[UrbanStyle] = None
    music: str = ""                         # soundtrack pool ("" = the family's)
    under: str = ""                         # underground biome below ("" = the family's)
    traits: Tuple[str, ...] = ()            # additional adaptation traits on top of the family's
    wet_twin: str = ""                      # what its very wet low ground by water becomes (a biome key)
    coastal: bool = False                   # only forms on the shore (beach)
    pois: Dict[str, float] = field(default_factory=dict)      # points of interest -> weight here (missing = the kind's default)
    full: bool = True                       # False: only basic support (see docs/BIOMES.md)

    @property
    def family_info(self) -> Family:
        return FAMILIES[self.family]

    @property
    def vegetation_level(self) -> float:
        return self.vegetation

    @property
    def all_traits(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys(self.family_info.traits + self.traits))

    @property
    def music_pool(self) -> str:
        return self.music or self.family_info.music

    @property
    def generic_pool(self) -> str:
        return self.family_info.generic

    @property
    def under_key(self) -> str:
        return self.under or self.family_info.under

    @property
    def mid_temperature(self) -> float:
        return sum(self.temperature) / 2.0

    @property
    def mid_moisture(self) -> float:
        return sum(self.moisture) / 2.0


BIOMES: Dict[str, Biome] = {}
BIOME_IDS: List[str] = []

_TUFTS = ((3, 9), (4, 9), (5, 9), (1, 9), (7, 9), (8, 9), (9, 9), (19, 9), (20, 9))
_GRASS = ((3, 9), (4, 9), (5, 9), (7, 9), (8, 9))
_TALL = ((6, 9), (7, 9), (8, 9), (6, 9))
_FERNS = ((10, 9), (11, 9), (12, 9))
_LEAVES = ((17, 9), (18, 9))
_DRY = ((3, 9), (4, 9), (5, 9))
_SPARSE = ((3, 9), (4, 9))
_VINES = ((23, 9), (24, 9), (23, 10), (24, 10), (23, 8), (24, 8))
_CAPS = ((2, 10), (3, 10), (2, 10), (3, 10), (1, 10))
_BONES = ((5, 27), (7, 26))
_TEX_DOT = ((1, 5),)
_TEX_WEAVE = ((1, 6), (2, 6))
_TEX_WAVE = ((5, 6), (6, 6))
_TEX_DIAG = ((3, 5),)
_TEX_RING = ((9, 6), (10, 6))
_TEX_CROSS = ((0, 6), (11, 6))


def _biome(key: str, name: str, family: str, temperature: Range, moisture: Range, description: str, features: str, **kwargs) -> Biome:
    biome = Biome(key, name, family, description, features, temperature, moisture, **kwargs)
    assert biome.key not in BIOMES, key
    assert biome.family in FAMILIES, key
    BIOMES[biome.key] = biome
    BIOME_IDS.append(biome.key)
    return biome


# Open and grassy ────────────────────────────────────────────────────────────────────────────────────
_biome("plains", "Plains", "grass", (-0.2, 0.5), (-0.1, 0.5), "Rolling, open grass with a copse here and there.",
       "Short grass, scattered trees, rabbits and grazers; the gentle default.", ambient=16, ground=(105, 140, 70), vegetation=0.5,
       cover=_GRASS, tree_share=1.0, stones=("pale", "red"), rarity=1.4, scenery=dict(pebbles=0.6, small_rocks=0.4))
_biome("flowering_meadow", "Flowering meadow", "grass", (-0.2, 0.6), (0.0, 0.8), "Open, airy grass in pale colours, thick with wildflowers.",
       "Pale ground, wildflowers everywhere, almost no trees; butterflies' country.", ambient=16, ground=(150, 190, 120), ground_alt=(190, 200, 140),
       vegetation=0.55, floor_density=0.35, cover=_TUFTS, plants=dict(meadow_bloom=3.0, meadow_flower=2.0, bush=0.4, broadleaf=0.2),
       tree_share=0.15, stones=("pale",), music="flowering_meadow", scenery=dict(pebbles=0.4, small_rocks=0.2, bones=0.1))
_biome("tallgrass_expanse", "Tallgrass expanse", "grass", (0.0, 0.6), (-0.25, 0.3), "Grass as tall as a person, hissing in the wind.",
       "A dense sea of tall grass with narrow trails; hides what moves in it.", ambient=22, ground=(160, 150, 80), ground_alt=(130, 150, 70), vegetation=0.9,
       floor_density=0.8, cover=_TALL, cover_boost=1.8, plants=dict(tallgrass=5.0, golden_grass=3.0, acacia=0.3, bush=0.5), tree_share=0.1,
       stones=("pale", "red"), scenery=dict(bones=1.2, pebbles=0.3))
_biome("ancient_grassland", "Ancient grassland", "grass", (-0.3, 0.4), (-0.2, 0.5), "Old, undisturbed grass round the standing relics of a forgotten age.",
       "Huge solitary old trees, standing stones and weathered bones over thin turf.", ambient=13, ground=(125, 140, 95), ground_alt=(150, 145, 110),
       vegetation=0.4, cover=_GRASS, plants=dict(ancient_oak=2.5, bush=0.6, meadow_flower=0.8), tree_share=0.9, stones=("grey", "pale"), rarity=0.7,
       scenery=dict(monolith=2.0, bones=0.8, skull=0.8, small_rocks=1.0), pois=dict(standing_stones=3.0))
_biome("overgrown_pasture", "Overgrown pasture", "grass", (-0.1, 0.5), (0.0, 0.6), "Fields gone wild between rotting fences.",
       "Gone-to-seed fields, broken fences, abandoned farmsteads and crops left to rot.", ambient=15, ground=(125, 140, 75), ground_alt=(150, 130, 70),
       vegetation=0.6, cover=_TUFTS, plants=dict(crop_wild=3.0, thorns=1.5, bush=1.5, golden_grass=1.5), tree_share=0.5, stones=("pale", "grey"),
       scenery=dict(stump=1.5, pebbles=0.5, rubble=0.4), pois=dict(abandoned_farm=4.0, ruined_cabin=1.5))
_biome("steppe", "Steppe", "grass", (-0.5, 0.1), (-0.6, -0.1), "Cool, dry, open grassland.",
       "Wind-bent dry grass and wide skies; few trees, many bones.", ambient=8, night_drop=12, ground=(150, 140, 90), vegetation=0.4,
       cover=_DRY + ((7, 9), (8, 9)), tree_share=0.4, stones=("pale", "red"), scenery=dict(bones=1.5, pebbles=1.0))
_biome("savanna", "Savanna", "grass", (0.2, 1.0), (-0.35, 0.15), "Warm grass with scattered flat-topped trees.",
       "Gold grass under lone acacias, herds of striders, hunters in the shade.", ambient=30, night_drop=12, ground=(170, 150, 75), vegetation=0.45,
       cover=_DRY + ((7, 9), (8, 9)), plants=dict(acacia=4.0, golden_grass=2.5, thorns=1.2), tree_share=1.1, stones=("red", "pale"),
       scenery=dict(bones=2.0, skull=1.5))
_biome("shrubland", "Shrubland", "grass", (0.0, 0.5), (-0.4, 0.0), "Dry scrub.", "Low wiry scrub and thorns over red dust.", ambient=22, night_drop=11,
       ground=(130, 125, 80), vegetation=0.6, cover=_DRY + ((7, 9), (8, 9)), plants=dict(bush=3.0, thorns=2.0), tree_share=0.3, stones=("red", "pale"),
       scenery=dict(small_rocks=0.8, bones=0.8))

# Arid ──────────────────────────────────────────────────────────────────────────────────────────────
_biome("cactus_desert", "Cactus desert", "arid", (0.25, 1.2), (-1.2, -0.25), "Baked sand, bare red rock and a scatter of cacti.",
       "Orange sand, tall cacti and barrel cacti, red rock, heat that cooks.", ambient=40, night_drop=26, ground=(222, 156, 84), ground_alt=(200, 120, 70),
       vegetation=0.3, floor_density=0.35, cover=_DRY, plants=dict(cactus=3.0, barrel_cactus=3.0, agave=2.0, dry_flower=1.0, bush=0.2), plants_only=True,
       tree_share=0.7, stones=("red", "pale"), music="cactus_desert", scenery=dict(bones=2.5, skull=2.5, small_rocks=1.2), rock_tint=(160, 90, 60), rock_mix=0.5)
_biome("red_dunes", "Red dunes", "arid", (0.4, 1.3), (-1.2, -0.5), "Wind-ribbed dunes of rust-red sand.",
       "Rippled red sand and almost nothing else: a few dry tussocks, a bleached bone.", ambient=42, night_drop=28, ground=(196, 108, 70), ground_alt=(214, 130, 84),
       texture=_TEX_WAVE, vegetation=0.06, cover=_SPARSE, plants=dict(agave=1.0, thorns=0.8), plants_only=True, tree_share=0.1, stones=("red",),
       scenery=dict(bones=1.0, small_rocks=0.4), rock_tint=(150, 80, 55), rock_mix=0.6)
_biome("salt_flats", "Salt flats", "arid", (0.1, 1.2), (-1.2, -0.6), "A blinding white crust over dry lakebed.",
       "Cracked white salt, pink brine pools at the edge; only salt-loving shrubs live here.", ambient=36, night_drop=24, ground=(228, 226, 222),
       ground_alt=(206, 196, 205), texture=_TEX_WEAVE, vegetation=0.05, cover=(), plants=dict(saltbush=1.0), plants_only=True, tree_share=0.0,
       stones=("pale",), scenery=dict(salt_crust=3.0, bones=0.6), elevation=(-1.5, 0.15), rock_tint=(205, 200, 195), rock_mix=0.5, traits=("salty",))
_biome("glass_desert", "Glass desert", "arid", (0.5, 1.3), (-1.2, -0.6), "Sand fused to glass by some old fire.",
       "Smooth green-white glass sheets, shards and glassy cacti; dazzling and sharp.", ambient=44, night_drop=28, ground=(160, 205, 190),
       ground_alt=(120, 170, 170), texture=_TEX_DIAG, vegetation=0.06, plants=dict(glass_cactus=2.0), plants_only=True, tree_share=0.2, stones=("crystal", "pale"),
       scenery=dict(glass_shards=3.0, crystal_cluster=0.5, bones=0.3), rarity=0.5, traits=("glassy",), rock_tint=(120, 170, 160), rock_mix=0.5)
_biome("bone_desert", "Bone desert", "arid", (0.2, 1.0), (-1.2, -0.4), "Sand strewn with the remains of something very large.",
       "Pale sand drifted over ribcages, skulls and vertebrae; a graveyard of giants.", ambient=38, night_drop=24, ground=(214, 200, 170), ground_alt=(228, 218, 196),
       vegetation=0.1, cover=_SPARSE, plants=dict(saltbush=0.5, bone_thorn=1.5, cactus=0.4), plants_only=True, tree_share=0.2, stones=("pale",),
       scenery=dict(bones=9.0, skull=7.0), rarity=0.6, pois=dict(bone_pile=3.0, graveyard=1.5))
_biome("desert_badlands", "Desert badlands", "arid", (0.3, 1.2), (-0.7, -0.3), "Eroded, banded rock and gullies.",
       "Striped red and ochre rock, dry gullies, rock formations, sparse scrub.", ambient=36, night_drop=20, ground=(170, 105, 70), ground_alt=(190, 140, 90),
       vegetation=0.15, outcrops=0.12, plants=dict(thorns=2.0, agave=1.0, barrel_cactus=1.0, cactus=0.5), tree_share=0.3, stones=("red", "dark"),
       scenery=dict(small_rocks=3.0, pebbles=2.0, bones=1.0), rock_tint=(168, 98, 60), rock_mix=0.7)
_biome("desert", "Desert", "arid", (0.3, 1.3), (-1.2, -0.5), "Sand and rock under a harsh sun.",
       "Pale sand and sun-bleached rock; the plain, empty classic.", ambient=38, night_drop=25, ground=(205, 180, 120), vegetation=0.08, cover=_SPARSE,
       plants=dict(cactus=1.0, barrel_cactus=0.6, dry_flower=0.3, agave=0.5), tree_share=0.4, stones=("pale", "red"), scenery=dict(bones=2.0, pebbles=1.4, skull=1.0))

# Forests ───────────────────────────────────────────────────────────────────────────────────────────
_biome("temperate_woodland", "Temperate woodland", "forest", (-0.2, 0.4), (0.1, 0.7), "Mixed, airy woodland.",
       "Oak, maple and birch with ferns and fallen leaves; mild and bright.", ambient=14, ground=(60, 100, 55), vegetation=1.2, cover=_TUFTS + _FERNS + _LEAVES,
       plants=dict(broadleaf=3.0, willow=0.6, bush=1.0), tree_share=3.0, stones=("grey", "dark"), wet_twin="swamp", rarity=1.3,
       scenery=dict(stump=1.0, pebbles=0.5))
_biome("dense_forest", "Dense forest", "forest", (-0.1, 0.4), (0.35, 1.0), "Close-packed trees and little light.",
       "A tight canopy, dark floor, ferns and fallen trunks; hard to see far.", ambient=12, ground=(40, 80, 45), vegetation=1.6, floor_density=0.7,
       cover=_FERNS + _LEAVES + _TUFTS, plants=dict(broadleaf=4.0, conifer=1.5, cypress=1.0, bush=0.6), tree_share=5.0, stones=("dark", "grey"), wet_twin="swamp",
       scenery=dict(stump=2.0, pebbles=0.3))
_biome("ancient_canopy", "Ancient canopy", "forest", (-0.1, 0.5), (0.3, 1.0), "Titanic old trees, a roof of leaves far overhead.",
       "Rare giants with huge trunks, deep shade, thick moss; very old and very quiet.", ambient=11, ground=(35, 70, 50), ground_alt=(50, 85, 60), vegetation=1.4,
       floor_density=0.6, cover=_FERNS + _LEAVES, plants=dict(ancient_giant=4.0, broadleaf=1.0, fern=3.0), tree_share=4.0, stones=("dark",), rarity=0.5,
       wet_twin="swamp", scenery=dict(stump=2.5, mushroom_ring=1.5), pois=dict(ruined_cabin=1.0, standing_stones=1.5))
_biome("amberwood", "Amberwood", "forest", (-0.2, 0.3), (0.0, 0.6), "A forest permanently in autumn, every leaf amber and rust.",
       "Orange and rust foliage, deep drifts of fallen leaves, russet ground.", ambient=10, ground=(130, 85, 45), ground_alt=(150, 100, 50), vegetation=1.1,
       cover=_LEAVES * 3 + _TUFTS, plants=dict(amber_tree=5.0, broadleaf=0.4, bush=0.8), tree_share=3.0, stones=("red", "grey"), rarity=0.8, scenery=dict(stump=1.0))
_biome("jungle", "Jungle", "forest", (0.35, 1.3), (0.3, 1.2), "Dense, hot and wet.",
       "Vine-hung, steaming, broad leaves and palms; the thickest vegetation there is.", ambient=29, night_drop=6, ground=(35, 110, 55), vegetation=1.7, floor_density=0.8,
       cover=_TUFTS + _FERNS + _LEAVES * 2, plants=dict(palm=2.0, broadleaf=2.0, jungle_giant=3.0, vine_creeper=3.0, fern=2.0, bush=1.0), tree_share=4.0,
       stones=("dark", "grey"), wet_twin="swamp", scenery=dict(stump=1.0, mushroom_ring=0.5), traits=("wet",))
_biome("thornwood", "Thornwood", "forest", (0.0, 0.8), (-0.3, 0.4), "A dry wood of black-barked, thorned trees.",
       "Hooked, dark trees and bramble walls; every path is a gauntlet.", ambient=20, ground=(70, 62, 55), ground_alt=(88, 70, 60), vegetation=1.1, floor_density=0.5,
       cover=_DRY, plants=dict(thorn_tree=4.0, thorns=4.0, bush=0.4), plants_only=True, tree_share=2.5, stones=("dark", "red"), rarity=0.8,
       scenery=dict(bones=0.8, stump=1.0))
_biome("petrified_forest", "Petrified forest", "forest", (-0.2, 1.0), (-0.8, 0.1), "Trees turned to stone, standing where they died.",
       "Grey stone trunks, stone logs on the ground, no leaves, mineral dust.", ambient=22, night_drop=14, ground=(150, 142, 130), ground_alt=(120, 112, 108),
       vegetation=0.5, floor_density=0.3, plants=dict(petrified_tree=5.0), plants_only=True, tree_share=4.0, stones=("grey", "pale"), rarity=0.5,
       scenery=dict(stump=3.0, small_rocks=1.0), traits=("petrified",), pois=dict(bone_pile=0.5))
_biome("taiga", "Taiga", "cold", (-0.6, -0.2), (-0.3, 1.0), "Cold conifer forest.",
       "Evergreens in snow-dusted moss; short days, long shadows.", ambient=-2, night_drop=8, ground=(70, 90, 70), vegetation=1.0,
       cover=_TUFTS + _FERNS, plants=dict(conifer=5.0, bush=0.6), tree_share=3.5, stones=("grey", "dark"), wet_twin="bog", rarity=1.3, scenery=dict(stump=1.0, small_rocks=0.5))

# Fungal ───────────────────────────────────────────────────────────────────────────────────────────
_biome("fungal_forest", "Fungal forest", "fungal", (-0.4, 0.8), (0.15, 1.0), "Damp, dim ground under towering fungi, strange and soft-coloured.",
       "Mushroom trees, puffy spore bushes, violet loam and toadstool carpets: only fungi grow.", ambient=13, ground=(120, 66, 128), ground_alt=(98, 60, 112),
       vegetation=1.4, floor_density=0.9, cover=_CAPS + _TUFTS[:3], plants=dict(fungal_tree=3.0, spore_bush=3.0, glowcap=1.5, spore_flower=1.0), plants_only=True,
       tree_share=2.0, stones=("dark",), wet_twin="spore_marsh", scenery=dict(mushroom_ring=2.5, pebbles=0.2, small_rocks=0.2, stump=0.3))
_biome("giant_mushroom_grove", "Giant mushroom grove", "fungal", (-0.2, 0.8), (0.3, 1.0), "Caps as wide as houses.",
       "Huge, widely spaced mushroom trees casting pools of shade over bare soft ground.", ambient=15, ground=(140, 96, 140), ground_alt=(110, 80, 120),
       vegetation=0.7, floor_density=0.4, cover=_CAPS, plants=dict(giant_cap=5.0, fungal_tree=1.0, glowcap=1.0), plants_only=True, tree_share=4.0, stones=("dark",),
       rarity=0.6, scenery=dict(mushroom_ring=3.0))
_biome("spore_marsh", "Spore marsh", "fungal", (-0.2, 0.8), (0.5, 1.2), "Standing water under drifting spores.",
       "Murky pools of spore-thick water, wet fungal loam, drifting haze.", ambient=17, ground=(100, 90, 120), ground_alt=(80, 100, 110), vegetation=1.0,
       cover=_CAPS + _TUFTS[:2], plants=dict(spore_bush=3.0, glowcap=2.0, reeds=1.0, spore_flower=1.5, fungal_tree=0.8), plants_only=True, tree_share=1.0, flood=0.14,
       stones=("dark",), liquid=2, rarity=0.7, scenery=dict(mushroom_ring=1.5))
_biome("mycelial_expanse", "Mycelial expanse", "fungal", (-0.6, 0.8), (-0.2, 0.6), "A white web over everything.",
       "A pale mycelial carpet laced with threads, a few lonely caps; eerily empty.", ambient=11, ground=(190, 182, 196), ground_alt=(160, 150, 175), texture=_TEX_WEAVE,
       vegetation=0.35, cover=_CAPS[:2] + _SPARSE, plants=dict(glowcap=2.0, spore_bush=1.5, spore_flower=1.0), plants_only=True, tree_share=0.2, stones=("pale",),
       scenery=dict(mushroom_ring=2.0, tendrils=1.0), rarity=0.8)
_biome("luminous_fungal_basin", "Luminous fungal basin", "fungal", (-0.4, 0.6), (0.2, 1.0), "A hollow glowing in cyan and magenta.",
       "Neon-bright caps in a low basin, blue-green loam, the most colourful fungal ground.", ambient=12, ground=(40, 120, 140), ground_alt=(120, 60, 150), vegetation=1.2,
       elevation=(-1.5, 0.1), cover=_CAPS, plants=dict(glowcap=4.0, fungal_tree=2.0, spore_flower=2.0, spore_bush=1.0), plants_only=True, tree_share=1.5, stones=("dark", "crystal"),
       rarity=0.5, scenery=dict(mushroom_ring=2.0, crystal_cluster=0.2))
_biome("deep_fungal_growth", "Deep fungal growth", "fungal", (-0.6, 0.5), (0.3, 1.2), "Fungus grown over fungus, dark and dense.",
       "Thick, dark, almost impassable growth: shelf fungi, ropes of mycelium, heavy damp.", ambient=9, night_drop=4, ground=(70, 40, 86), vegetation=1.8, floor_density=1.0,
       cover=_CAPS + _VINES[:2], plants=dict(fungal_tree=4.0, spore_bush=4.0, glowcap=1.0), plants_only=True, tree_share=3.0, stones=("dark",), rarity=0.5,
       wet_twin="spore_marsh", scenery=dict(tendrils=1.5, mushroom_ring=1.0))

# Crystalline ───────────────────────────────────────────────────────────────────────────────────────
_biome("crystal_fields", "Crystal fields", "crystal", (-0.5, 0.5), (-1.2, 0.3), "Open ground bristling with glittering crystal.",
       "Glassy blue-violet ground and clusters of crystal everywhere; chimes in the wind.", ambient=5, night_drop=14, ground=(112, 132, 190), ground_alt=(140, 150, 215),
       texture=_TEX_DIAG, vegetation=0.3, cover=_DRY, plants=dict(shard_bush=3.0, crystal_bloom=3.0, crystal_tree=0.6), plants_only=True, tree_share=0.4,
       stones=("crystal", "pale"), scenery=dict(crystal_cluster=4.0, small_rocks=1.5), rock_tint=(120, 140, 205), rock_mix=0.6)
_biome("crystalline_badlands", "Crystalline badlands", "crystal", (-0.3, 0.6), (-1.2, 0.2), "Broken rock and cold, glittering crystal under a hard sky.",
       "Fractured pale rock, crystal outcrops and sharp ridges; the harshest crystal ground.", ambient=4, night_drop=18, ground=(130, 138, 175), ground_alt=(110, 118, 158),
       vegetation=0.15, elevation=(0.0, 1.5), outcrops=0.14, plants=dict(shard_bush=2.0, crystal_bloom=1.0), plants_only=True, tree_share=0.3, stones=("crystal", "pale", "grey"),
       scenery=dict(crystal_cluster=2.5, small_rocks=3.0, pebbles=2.0), rock_tint=(128, 136, 190), rock_mix=0.6, rarity=0.8)
_biome("luminous_crystal_forest", "Luminous crystal forest", "crystal", (-0.4, 0.5), (-0.4, 0.6), "Spires of crystal standing like trees.",
       "Slender crystal trees in pink, cyan and gold casting rainbow shade; lit from within.", ambient=7, ground=(96, 110, 170), ground_alt=(150, 100, 190), vegetation=0.8,
       cover=_DRY, plants=dict(crystal_tree=5.0, shard_bush=2.0, crystal_bloom=3.0), plants_only=True, tree_share=3.0, stones=("crystal",), rarity=0.5,
       scenery=dict(crystal_cluster=2.0), rock_tint=(130, 120, 200), rock_mix=0.5)
_biome("crystal_desert", "Crystal desert", "crystal", (0.3, 1.2), (-1.2, -0.4), "Sand of crushed gems.",
       "Glittering sparkling sand in warm gold and rose, scattered gem clusters, no plants but glass bushes.", ambient=36, night_drop=24, ground=(225, 190, 190),
       ground_alt=(200, 215, 225), texture=_TEX_DIAG, vegetation=0.06, plants=dict(shard_bush=1.0, glass_cactus=0.8), plants_only=True, tree_share=0.1,
       stones=("crystal", "pale"), scenery=dict(crystal_cluster=2.0, glass_shards=1.0, bones=0.4), rarity=0.4, traits=("hot", "dry"))
_biome("mineral_labyrinth", "Mineral labyrinth", "crystal", (-0.3, 0.8), (-1.0, 0.0), "A maze of rock walls and mineral veins.",
       "Dense rock outcrops forming winding passages, veined walls, little else.", ambient=12, night_drop=14, ground=(120, 112, 118), ground_alt=(100, 96, 110), vegetation=0.1,
       outcrops=0.32, plants=dict(shard_bush=1.0), plants_only=True, tree_share=0.0, stones=("grey", "dark", "crystal"), rarity=0.5,
       scenery=dict(small_rocks=3.0, pebbles=1.5), rock_tint=(110, 104, 112), rock_mix=0.6, full=False)
_biome("geode_basin", "Geode basin", "crystal", (-0.2, 0.6), (-0.6, 0.4), "A great hollow of split stone, glittering inside.",
       "Low ground of broken geodes, purple crystal-lined hollows and amethyst glints.", ambient=10, ground=(120, 90, 150), ground_alt=(90, 80, 120), vegetation=0.2,
       elevation=(-1.5, 0.0), plants=dict(crystal_bloom=2.0, shard_bush=1.0), plants_only=True, tree_share=0.1, stones=("crystal", "dark"), rarity=0.5,
       scenery=dict(crystal_cluster=3.5, small_rocks=2.0), rock_tint=(125, 95, 160), rock_mix=0.6)

# Volcanic ───────────────────────────────────────────────────────────────────────────────────────────
_biome("volcanic_wastes", "Volcanic wastes", "volcanic", (0.2, 1.2), (-0.9, 0.4), "Black rock, ash and vents where the ground is too hot to rest on.",
       "Black ash flats, red-stained rock, hot springs and lava lakes, singed shrubs.", ambient=40, night_drop=10, ground=(58, 38, 40), ground_alt=(80, 44, 40),
       vegetation=0.12, cover=_DRY, plants=dict(ash_shrub=3.0, cinder_tree=0.8, ember_bloom=1.0), plants_only=True, tree_share=0.3, stones=("dark", "red"),
       scenery=dict(ash_pile=3.0, obsidian=1.0, small_rocks=3.0), rock_tint=(70, 52, 50), rock_mix=0.85, hot_springs=1.0)
_biome("lava_highlands", "Lava highlands", "volcanic", (0.4, 1.3), (-0.9, 0.3), "High, scorched ground split by rivers of fire.",
       "Rugged scorched rock, lava lakes, glowing cracks and dark slopes.", ambient=46, night_drop=8, ground=(70, 36, 30), ground_alt=(110, 50, 32), vegetation=0.06,
       elevation=(0.1, 1.5), outcrops=0.1, plants=dict(ash_shrub=1.0, ember_bloom=1.0), plants_only=True, tree_share=0.1, stones=("dark", "red"),
       scenery=dict(ash_pile=2.0, obsidian=2.0, small_rocks=3.0), rock_tint=(86, 44, 38), rock_mix=0.9, hot_springs=2.0, rarity=0.6)
_biome("geothermal_basin", "Geothermal basin", "volcanic", (0.1, 0.9), (-0.2, 0.8), "Pools and geysers in coloured, steaming ground.",
       "Pale mineral crusts in yellow and orange, hot springs and scalding pools; mild but steamy.", ambient=28, night_drop=6, ground=(200, 170, 110),
       ground_alt=(180, 120, 90), vegetation=0.25, elevation=(-1.5, 0.2), plants=dict(ash_shrub=1.0, saltbush=1.0, reeds=1.0), plants_only=True, tree_share=0.1,
       stones=("pale", "red"), scenery=dict(salt_crust=1.5, small_rocks=1.0), hot_springs=5.0, rarity=0.6, traits=("wet",))
_biome("obsidian_fields", "Obsidian fields", "volcanic", (0.2, 1.2), (-1.0, 0.2), "Plains of black volcanic glass.",
       "Glossy black glass flats with sharp edges and bright reflections, almost nothing grows.", ambient=34, night_drop=14, ground=(36, 34, 46), ground_alt=(50, 46, 66),
       texture=_TEX_DIAG, vegetation=0.04, plants=dict(ash_shrub=0.5), plants_only=True, tree_share=0.0, stones=("dark",),
       scenery=dict(obsidian=4.0, glass_shards=1.5, ash_pile=0.5), rock_tint=(40, 38, 54), rock_mix=0.9, rarity=0.6, traits=("glassy",))
_biome("ashen_caldera", "Ashen caldera", "volcanic", (0.3, 1.2), (-0.8, 0.2), "A vast collapsed crater drifted with ash.",
       "Grey ash drifts, dead trees and fumaroles in a huge sunken bowl.", ambient=32, night_drop=12, ground=(112, 106, 106), ground_alt=(84, 78, 80),
       elevation=(-1.5, 0.1), vegetation=0.1, plants=dict(ash_shrub=2.0, cinder_tree=1.0, dead_tree=0.4), plants_only=True, tree_share=0.4, stones=("dark", "grey"),
       scenery=dict(ash_pile=4.0, small_rocks=1.5, bones=0.6), rock_tint=(96, 90, 92), rock_mix=0.8, hot_springs=1.5, rarity=0.6)
_biome("scalded_mountains", "Scalded mountains", "volcanic", (0.5, 1.3), (-0.5, 0.5), "Mountains steaming under a boiling sky.",
       "Bare, yellow-streaked rock, sulphur crusts and scalding steam; hard and hot.", ambient=44, night_drop=10, ground=(150, 120, 60), ground_alt=(120, 90, 50),
       elevation=(0.2, 1.5), vegetation=0.06, outcrops=0.12, plants=dict(ash_shrub=1.0), plants_only=True, tree_share=0.0, stones=("red", "dark", "pale"),
       scenery=dict(small_rocks=3.0, salt_crust=1.0, ash_pile=1.0), rock_tint=(150, 110, 60), rock_mix=0.8, hot_springs=1.5, rarity=0.5, full=False)

# Decay ──────────────────────────────────────────────────────────────────────────────────────────────
_biome("decaying_lands", "Decaying lands", "decay", (-0.3, 1.0), (-0.3, 0.7), "Dead trees on grey ground, a place where something went wrong.",
       "Grey soil, bare blackened trees, drifts of bones and fallen things.", ambient=14, ground=(78, 66, 84), ground_alt=(66, 58, 70), vegetation=0.4,
       floor_density=0.45, cover=_DRY, plants=dict(dead_tree=5.0, bone_thorn=1.0, rot_cap=1.0), plants_only=True, tree_share=2.0, stones=("dark", "grey"),
       scenery=dict(bones=5.0, skull=6.0, rubble=1.5, gravestone=0.8), rarity=1.0, pois=dict(graveyard=2.0, bone_pile=2.0))
_biome("deadwood_expanse", "Deadwood expanse", "decay", (-0.2, 0.8), (-0.6, 0.2), "A forest that died standing.",
       "Endless grey trunks without a leaf, a floor of kindling; spectacularly flammable.", ambient=18, ground=(100, 90, 80), ground_alt=(120, 106, 90), vegetation=0.9,
       cover=_DRY, plants=dict(dead_tree=6.0, bone_thorn=1.0), plants_only=True, tree_share=4.0, stones=("grey",), scenery=dict(stump=2.5, bones=1.5, skull=1.0))
_biome("bone_fields", "Bone fields", "decay", (-0.3, 0.8), (-0.5, 0.5), "Open ground white with old bones.",
       "Pale turf thick with bones and skulls, standing ribs and carrion birds.", ambient=15, ground=(176, 172, 150), ground_alt=(150, 150, 126), vegetation=0.2,
       cover=_SPARSE, plants=dict(bone_thorn=2.0, dead_tree=0.3), plants_only=True, tree_share=0.2, stones=("pale", "grey"),
       scenery=dict(bones=12.0, skull=8.0, gravestone=0.3), rarity=0.5, pois=dict(bone_pile=4.0, graveyard=1.5))
_biome("corrupted_growth", "Corrupted growth", "decay", (-0.2, 0.8), (0.2, 1.0), "Plants gone wrong: black, swollen, pulsing.",
       "Purple-black, knotted growth, weeping caps and dead things strangled in vines.", ambient=17, ground=(54, 34, 66), ground_alt=(80, 36, 70), vegetation=1.2,
       floor_density=0.6, cover=_VINES + _CAPS[:2], plants=dict(rot_cap=3.0, tendril_tree=2.0, bone_thorn=1.0, creeper=2.0), plants_only=True, tree_share=2.0,
       stones=("dark",), scenery=dict(tendrils=3.0, bones=1.0, skull=0.8), rarity=0.5, traits=("fleshy",))
_biome("ruptured_wastes", "Ruptured wastes", "decay", (-0.2, 1.0), (-1.0, 0.2), "Ground torn open as if by a blow from beneath.",
       "Cracked and heaved grey earth, rifts, shattered stone and dust.", ambient=24, night_drop=16, ground=(130, 112, 100), ground_alt=(98, 84, 78), texture=_TEX_CROSS,
       vegetation=0.1, outcrops=0.1, plants=dict(thorns=1.0, bone_thorn=1.0), plants_only=True, tree_share=0.1, stones=("grey", "red", "dark"),
       scenery=dict(rubble=3.0, small_rocks=3.0, bones=1.0), rock_tint=(112, 98, 90), rock_mix=0.7, rarity=0.6, pois=dict(wreck_field=2.0))
_biome("abandoned_industrial_ground", "Abandoned industrial ground", "decay", (-0.4, 0.8), (-0.6, 0.6), "Rust, slag and the stumps of machines.",
       "Rust-red slag ground, pipes, drums and wrecks; industrial junk without the buildings.", ambient=18, ground=(116, 96, 82), ground_alt=(90, 84, 90), texture=_TEX_CROSS,
       vegetation=0.2, cover=_DRY, plants=dict(thorns=2.0, bush=1.0, weed=2.0), plants_only=True, tree_share=0.1, stones=("grey", "red"), rarity=0.6,
       scenery=dict(wreck_car=1.0, wreck_truck=0.6, rubble=2.0, small_rocks=0.6, pipe=2.0, drum=2.0), pois=dict(wreck_field=3.0, research_outpost=1.5))

# Alien ──────────────────────────────────────────────────────────────────────────────────────────────
_biome("visceral_heap", "Visceral heap", "alien", (0.0, 1.0), (0.3, 1.2), "Ground like wet meat, humped and veined.",
       "Pink-red wet ground that looks alive, pulsing pods, tendril trunks, slick membranes.", ambient=33, night_drop=3, ground=(150, 60, 76), ground_alt=(120, 40, 62),
       texture=_TEX_RING, vegetation=0.8, cover=_VINES[:2], plants=dict(tendril_tree=3.0, flesh_pod=4.0, creeper=1.0), plants_only=True, tree_share=1.5,
       stones=("dark", "red"), rarity=0.4, scenery=dict(tendrils=3.0, bones=1.0), liquid=3, traits=("fleshy",))
_biome("undergrowth", "Undergrowth", "alien", (0.0, 1.0), (0.4, 1.2), "A knotted carpet of vines and roots, nothing but tangle.",
       "Low, dense tangle of vines and creeper roots; hard to see into, sprouting from dim loam.", ambient=22, night_drop=5, ground=(60, 86, 50), ground_alt=(40, 66, 56),
       vegetation=1.8, floor_density=1.0, cover=_VINES * 2, cover_boost=2.0, plants=dict(creeper=5.0, vine_creeper=3.0, fern=2.0, glowcap=0.5), plants_only=True, tree_share=0.3,
       stones=("dark",), scenery=dict(tendrils=2.0, stump=1.0), rarity=0.6)
_biome("bioluminescent_expanse", "Bioluminescent expanse", "alien", (-0.4, 0.8), (-0.3, 0.6), "Dark ground dotted with cold, living light.",
       "Near-black ground sprinkled with glowing blue-green blooms, sparse and strange.", ambient=12, ground=(24, 36, 56), ground_alt=(20, 56, 66), vegetation=0.4,
       cover=_TUFTS[:3], plants=dict(lumen_frond=4.0, iris_bloom=3.0, glowcap=1.0), plants_only=True, tree_share=0.2, stones=("dark", "crystal"), rarity=0.6,
       scenery=dict(mushroom_ring=0.8, crystal_cluster=0.3))
_biome("spore_drift_fields", "Spore drift fields", "alien", (-0.2, 0.8), (-0.1, 0.5), "Open ground under slow clouds of drifting spores.",
       "Ochre ground flecked with floating spore motes; low puffballs and rising stalks.", ambient=20, ground=(190, 160, 90), ground_alt=(170, 130, 100), vegetation=0.5,
       cover=_CAPS[:3] + _SPARSE, plants=dict(spore_bush=3.0, spore_flower=3.0, glowcap=1.0), plants_only=True, tree_share=0.1, stones=("pale", "red"), rarity=0.5,
       scenery=dict(mushroom_ring=1.0), full=False)
_biome("iridescent_flats", "Iridescent flats", "alien", (-0.2, 0.9), (-0.8, 0.1), "A mirror-flat plain shifting between colours.",
       "Smooth sheet of rainbow-shifting ground, thin crystal weeds, shimmering heat.", ambient=22, night_drop=14, ground=(168, 140, 210), ground_alt=(120, 200, 190),
       texture=_TEX_WAVE, elevation=(-1.5, 0.15), vegetation=0.15, plants=dict(iris_bloom=3.0, shard_bush=0.5), plants_only=True, tree_share=0.0, stones=("crystal", "pale"),
       rarity=0.5, scenery=dict(glass_shards=1.0, crystal_cluster=0.5))
_biome("organic_wastes", "Organic wastes", "alien", (0.0, 1.0), (0.0, 1.0), "Reeking slumps of rotted growth and slime.",
       "Brown and green slime-slick ground, sunken pits, rot caps and hissing vents.", ambient=26, night_drop=4, ground=(108, 98, 48), ground_alt=(80, 100, 56),
       texture=_TEX_RING, vegetation=0.5, cover=_CAPS[:2], plants=dict(rot_cap=3.0, flesh_pod=1.0, weed=1.0, creeper=1.0), plants_only=True, tree_share=0.2, stones=("dark",),
       liquid=2, scenery=dict(bones=1.5, tendrils=1.0), traits=("toxic",), rarity=0.5, full=False)

# Water-associated ───────────────────────────────────────────────────────────────────────────────────
_biome("swamp", "Swamp", "wet", (0.1, 1.0), (0.45, 1.2), "Warm, flooded ground.", "Dark water, mangrove-like trees, reeds and rot; warm and thick.", ambient=24, night_drop=6,
       ground=(70, 90, 50), vegetation=1.1, flood=0.1, cover=_TUFTS + _FERNS + _LEAVES, plants=dict(mangrove=3.0, willow=1.5, reeds=2.0, marsh_flower=1.5, bush=0.6),
       tree_share=2.0, stones=("dark",), rarity=0.6, scenery=dict(stump=1.0, bones=0.4))
_biome("bog", "Bog", "wet", (-0.4, 0.15), (0.45, 1.2), "Cold peat and standing water.", "Peat-brown ground, pale moss, black pools and sedges; chill and sodden.",
       ambient=5, ground=(85, 80, 55), vegetation=0.7, flood=0.08, cover=_TUFTS + _FERNS, plants=dict(reeds=3.0, conifer=1.0, bush=1.0, marsh_flower=1.0), tree_share=1.0,
       stones=("dark", "grey"), scenery=dict(stump=0.6), rarity=0.6, traits=("cold",))
_biome("toxic_wetlands", "Toxic wetlands", "wet", (0.0, 1.0), (0.5, 1.2), "Pools that burn, fumes that sting.",
       "Sickly yellow-green ground and acid-green pools, bleached reeds, dead birds.", ambient=26, ground=(120, 130, 50), ground_alt=(90, 120, 60), vegetation=0.7,
       flood=0.16, cover=_TUFTS, plants=dict(reeds=2.0, toxic_bloom=3.0, rot_cap=1.0, mangrove=1.0), plants_only=True, tree_share=0.6, stones=("dark", "red"), liquid=2,
       rarity=0.5, scenery=dict(bones=1.5, skull=0.6), traits=("toxic",), wet_twin="toxic_wetlands")
_biome("luminous_marsh", "Luminous marsh", "wet", (-0.2, 0.9), (0.5, 1.2), "A marsh that glows at night.",
       "Reeds and blossoms that shine blue-green over still black water.", ambient=18, ground=(40, 90, 84), ground_alt=(30, 70, 100), vegetation=0.9, flood=0.14,
       cover=_TUFTS + _FERNS, plants=dict(glow_reed=4.0, lumen_frond=1.5, marsh_flower=2.0, mangrove=0.8), plants_only=True, tree_share=0.6, stones=("dark",), rarity=0.5)
_biome("mineral_pools", "Mineral pools", "wet", (0.1, 1.0), (-0.2, 0.6), "Terraced pools in rainbow-banded stone.",
       "Rings of ochre, teal and white mineral crust around bright terraced pools.", ambient=25, ground=(190, 160, 120), ground_alt=(110, 170, 160), texture=_TEX_RING,
       vegetation=0.3, flood=0.12, cover=_SPARSE, plants=dict(saltbush=1.0, reeds=1.0), plants_only=True, tree_share=0.1, stones=("pale", "red"), rarity=0.5,
       scenery=dict(salt_crust=2.0), hot_springs=2.0)
_biome("flooded_forest", "Flooded forest", "wet", (0.0, 0.9), (0.6, 1.2), "Trees standing knee-deep in still water.",
       "Mangrove-like trees in a shallow flood, glassy water, drifting leaves and mist.", ambient=23, ground=(60, 100, 72), vegetation=1.4, floor_density=0.7, flood=0.28,
       cover=_TUFTS, plants=dict(mangrove=5.0, willow=2.0, cypress=2.0, reeds=1.5), plants_only=True, tree_share=4.0, stones=("dark",), rarity=0.5,
       scenery=dict(stump=2.0))
_biome("algal_basin", "Algal basin", "wet", (-0.1, 0.8), (0.5, 1.2), "A shallow bowl thick with green scum.",
       "Neon-green algae mats over still water, flat and bright, few plants.", ambient=19, ground=(80, 150, 80), ground_alt=(40, 120, 70), texture=_TEX_WAVE, vegetation=0.5,
       elevation=(-1.5, 0.1), flood=0.22, plants=dict(algae_mat=5.0, reeds=1.5), plants_only=True, tree_share=0.0, stones=("dark",), rarity=0.5, liquid=1)
_biome("thermal_wetlands", "Thermal wetlands", "wet", (0.2, 1.0), (0.3, 1.2), "Warm marsh steaming gently.",
       "Rust-and-green steaming marsh with hot pools and tall reed beds.", ambient=30, night_drop=3, ground=(100, 130, 70), ground_alt=(150, 130, 80), vegetation=1.1, flood=0.12,
       cover=_TUFTS + _FERNS, plants=dict(reeds=3.0, mangrove=1.5, marsh_flower=1.5, ember_bloom=0.3), tree_share=1.0, stones=("dark", "red"), hot_springs=3.0, rarity=0.5)

# Cold ───────────────────────────────────────────────────────────────────────────────────────────────
_biome("glacial_plain", "Glacial plain", "cold", (-1.3, -0.55), (-1.2, 1.2), "Wind-scoured ice and snow.", "White-blue ice, drifts and blue shadows; almost no life.", ambient=-25,
       night_drop=8, ground=(200, 215, 230), ground_alt=(176, 198, 224), texture=_TEX_DOT, vegetation=0.05, cover=_SPARSE, plants=dict(rime_shrub=0.5), plants_only=True,
       tree_share=0.2, stones=("pale", "crystal"), rarity=1.3, scenery=dict(small_rocks=0.8, bones=0.3), rock_tint=(190, 206, 226), rock_mix=0.6)
_biome("tundra", "Tundra", "cold", (-0.55, -0.3), (-1.2, 0.0), "Frozen ground with moss and thin shrubs.", "Mossy, frost-heaved ground, lichens and stunted shrubs under a low sun.",
       ambient=-10, night_drop=8, ground=(150, 150, 130), vegetation=0.25, cover=_DRY + _SPARSE, plants=dict(rime_shrub=2.0, bush=1.0, frost_bloom=1.0), tree_share=0.4,
       stones=("grey", "pale"), rarity=1.2, scenery=dict(small_rocks=1.5, pebbles=1.3, bones=0.5))
_biome("frost_grove", "Frost grove", "cold", (-1.2, -0.3), (-0.3, 1.0), "Pale, brittle trees furred with rime on blue-white ground, silent and bitterly cold.",
       "Rime-white trees, frosted shrubs and flowers on blue-white ground; absolutely still.", ambient=-14, night_drop=8, ground=(176, 200, 226), ground_alt=(150, 176, 210),
       vegetation=1.0, floor_density=0.5, cover=_DRY, plants=dict(frost_tree=5.0, rime_shrub=3.0, frost_bloom=2.0), plants_only=True, tree_share=2.5, stones=("pale", "grey"),
       music="frost_grove", rarity=0.8, scenery=dict(small_rocks=0.5))
_biome("snow_fields", "Snow fields", "cold", (-1.3, -0.4), (-0.6, 1.2), "Deep unbroken snow.", "Soft deep snow with buried stumps; wide, white and very bright.", ambient=-18,
       night_drop=8, ground=(232, 240, 248), ground_alt=(214, 226, 240), vegetation=0.08, cover=_SPARSE, plants=dict(frost_tree=0.6, rime_shrub=1.0), plants_only=True,
       tree_share=0.3, stones=("pale",), rarity=0.8, scenery=dict(stump=0.6), rock_tint=(220, 232, 244), rock_mix=0.7)
_biome("ice_spires", "Ice spires", "cold", (-1.3, -0.5), (-1.0, 1.0), "Blue spikes of old ice breaking the snow.", "Jagged, translucent ice formations in blue and white over frozen ground.",
       ambient=-22, ground=(160, 196, 230), ground_alt=(190, 214, 236), vegetation=0.04, elevation=(0.0, 1.5), outcrops=0.12, plants=dict(rime_shrub=0.4), plants_only=True,
       tree_share=0.0, stones=("crystal", "pale"), rarity=0.5, scenery=dict(crystal_cluster=2.0, small_rocks=1.0), rock_tint=(160, 200, 236), rock_mix=0.8, full=False)

# Shore (applied by the terrain, not by regions) ──────────────────────────────────────────────────────
_biome("beach", "Beach", "coast", (-0.15, 1.2), (-1.2, 1.2), "Pale sand, driftwood and shells where the land meets the water.", "A strip of pale sand along the water: palms, dune grass, shells.",
       ambient=22, ground=(232, 214, 160), ground_alt=(214, 198, 150), vegetation=0.3, floor_density=0.25, cover=_DRY, plants=dict(coast_palm=4.0, beach_grass=5.0), plants_only=True,
       tree_share=0.8, stones=("pale",), coastal=True, rarity=0.0, scenery=dict(pebbles=1.8, bones=0.8, shell=2.5, driftwood=1.5))

# Urban and constructed ──────────────────────────────────────────────────────────────────────────────
_biome("abandoned_district", "Abandoned urban district", "urban", (-0.3, 0.7), (-0.5, 0.5), "Streets and blocks of a city nobody has lived in for ages.",
       "A street grid with roads, ruined buildings, towers, wrecked vehicles and lamp posts; silent.", ambient=14, ground=(92, 92, 98), ground_alt=(76, 76, 84), vegetation=0.15,
       cover=_SPARSE, plants=dict(weed=2.0, bush=1.0, thorns=0.8), plants_only=True, tree_share=0.2, stones=("grey", "dark"), rarity=0.5,
       urban=UrbanStyle(), scenery=dict(rubble=1.2, pebbles=0.4, lamp_post=0.0, signpost=0.0), pois=dict(research_outpost=1.5))
_biome("overgrown_city", "Overgrown city", "urban", (-0.1, 0.9), (0.2, 1.1), "A city the forest has taken back.",
       "Streets cracked by roots, trees growing out of buildings, vines over wrecks.", ambient=19, ground=(70, 94, 66), ground_alt=(86, 90, 80), vegetation=1.0,
       cover=_TUFTS + _FERNS, plants=dict(broadleaf=2.0, creeper=1.5, ivy=3.0, bush=1.5, vine_creeper=1.0), tree_share=2.0, stones=("grey", "dark"), rarity=0.4,
       urban=UrbanStyle(ruin=0.45, overgrown=0.6, towers=0.1, vehicles=0.04), scenery=dict(rubble=1.0, tendrils=0.8))
_biome("industrial_ruins", "Industrial ruins", "urban", (-0.2, 0.9), (-0.7, 0.4), "Factories, stacks and rusted rails.", "Dense lots of factories, chimneys, pipes, drums and heavy wrecks on rust-red ground.",
       ambient=18, ground=(110, 90, 82), ground_alt=(92, 84, 92), texture=_TEX_CROSS, vegetation=0.1, cover=_SPARSE, plants=dict(weed=2.0, thorns=1.0), plants_only=True,
       tree_share=0.0, stones=("grey", "red"), rarity=0.4, urban=UrbanStyle(pitch=(30, 24), road=3, built=0.85, ruin=0.35, towers=0.05, industrial=0.6, vehicles=0.06),
       scenery=dict(pipe=2.0, drum=2.0, rubble=1.6, wreck_truck=0.4))
_biome("flooded_ruins", "Flooded ruins", "urban", (0.0, 0.9), (0.4, 1.2), "Streets under shallow water.", "A drowned district: roofs and walls rising from a shallow flood, algae on every wall.",
       ambient=21, ground=(70, 100, 100), ground_alt=(60, 80, 96), vegetation=0.5, flood=0.35, cover=_TUFTS, plants=dict(reeds=2.0, mangrove=1.0, ivy=1.0, weed=1.0),
       tree_share=0.5, stones=("grey", "dark"), rarity=0.3, urban=UrbanStyle(ruin=0.5, towers=0.2, vehicles=0.03, built=0.7), scenery=dict(rubble=1.0), liquid=1, full=False)
_biome("ancient_settlement_remains", "Ancient settlement remains", "urban", (-0.4, 0.8), (-0.4, 0.6), "Low stone huts and old hearths, long abandoned.", "Small round stone huts, hearths, cairns and standing stones with no roads.",
       ambient=14, ground=(128, 124, 98), ground_alt=(110, 118, 88), vegetation=0.4, cover=_DRY + _TUFTS[:2], plants=dict(ancient_oak=0.6, bush=2.0, thorns=1.0, golden_grass=1.0),
       tree_share=0.6, stones=("grey", "pale"), rarity=0.5, urban=UrbanStyle(pitch=(22, 18), road=0, built=0.5, ruin=0.6, towers=0.0, vehicles=0.0, huts=True),
       scenery=dict(monolith=1.0, bones=0.8, rubble=1.2), pois=dict(standing_stones=2.0))

BIOME_INDEX: Dict[str, int] = {key: i for i, key in enumerate(BIOME_IDS)}
REGION_BIOMES: List[str] = [k for k in BIOME_IDS if not BIOMES[k].coastal]
"""The biomes a region may be (all but the shore)."""
FAMILY_MEMBERS: Dict[str, Tuple[str, ...]] = {f: tuple(k for k in BIOME_IDS if BIOMES[k].family == f) for f in FAMILIES}


LEGACY_KEYS = {"mushroom_forest": "fungal", "crystal_badlands": "crystal", "volcanic_mountains": "volcanic", "decayed_land": "decay"}
"""What the landmark names of the old system mean now (saved species may still name them)."""


def members(key: str) -> Tuple[str, ...]:
    """The biome keys a name stands for: a biome (itself) or a family (all its biomes). () for an unknown name."""
    key = LEGACY_KEYS.get(key, key)
    if key in BIOMES:
        return (key,)
    return FAMILY_MEMBERS.get(key, ())


def indexes(keys) -> np.ndarray:
    """Biome indexes of biome and family keys."""
    return np.array(sorted({BIOME_INDEX[m] for k in keys for m in members(k)}), dtype=np.int16)


@lru_cache(maxsize=None)
def listing(plant: str) -> Tuple[str, ...]:
    """The biomes that list a plant template in their `plants`."""
    return tuple(k for k in BIOME_IDS if plant in BIOMES[k].plants)


@lru_cache(maxsize=None)
def plant_traits(plant: str) -> Tuple[str, ...]:
    """The traits every biome that lists a plant has (a plant that lives in several kinds of country keeps only what they share)."""
    found = [set(BIOMES[k].all_traits) for k in listing(plant)]
    return tuple(sorted(set.intersection(*found))) if found else ()


def ground_colors(index: np.ndarray) -> np.ndarray:
    """(…, 3) uint8 ground colour for an array of biome indexes."""
    table = np.array([BIOMES[k].ground for k in BIOME_IDS], dtype=np.uint8)
    return table[index]


def table(attr: str, dtype=float) -> np.ndarray:
    """One number per biome (by index) for the attribute `attr`."""
    return np.array([getattr(BIOMES[k], attr) for k in BIOME_IDS], dtype=dtype)


# ── variants ───────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class VariantSpec:
    key: str
    name: str
    ground: Tuple[int, int, int]      # added to the ground colour (before it is clipped)
    vegetation: float                 # multiplies the vegetation density
    ambient: int                      # degrees C added


VARIANTS: Dict[str, VariantSpec] = {
    "hot": VariantSpec("hot", "Hot", (14, 4, -10), 0.85, 8),
    "cold": VariantSpec("cold", "Cold", (-8, 2, 16), 0.8, -10),
    "wet": VariantSpec("wet", "Wet", (-10, -2, 4), 1.2, -2),
    "dry": VariantSpec("dry", "Dry", (14, 8, -6), 0.75, 2),
}
VARIANT_BITS = {"hot": 1, "cold": 2, "wet": 4, "dry": 8}
VARIANT_EDGE = 0.7
"""A tile counts as hot (wet ...) for its biome when it lies in the hottest (wettest...) third beyond the middle of the biome's climate range
(or, for a biome with an open range, beyond +- 0.35 of the climate's middle)."""


def variant_bits(temperature: np.ndarray, moisture: np.ndarray, biome: np.ndarray) -> np.ndarray:
    """Variant flags (bits of `VARIANT_BITS`) of tiles, from how far their climate is from the middle of their biome's."""
    mid_t, mid_m = table("mid_temperature"), table("mid_moisture")
    half_t = np.array([min((BIOMES[k].temperature[1] - BIOMES[k].temperature[0]) / 2.0, 0.5) for k in BIOME_IDS])
    half_m = np.array([min((BIOMES[k].moisture[1] - BIOMES[k].moisture[0]) / 2.0, 0.5) for k in BIOME_IDS])
    dt = (np.asarray(temperature) - mid_t[biome]) / np.maximum(half_t[biome], 0.15)
    dm = (np.asarray(moisture) - mid_m[biome]) / np.maximum(half_m[biome], 0.15)
    out = np.zeros(np.shape(biome), dtype=np.int8)
    out |= np.where(dt > VARIANT_EDGE, VARIANT_BITS["hot"], 0).astype(np.int8)
    out |= np.where(dt < -VARIANT_EDGE, VARIANT_BITS["cold"], 0).astype(np.int8)
    out |= np.where(dm > VARIANT_EDGE, VARIANT_BITS["wet"], 0).astype(np.int8)
    out |= np.where(dm < -VARIANT_EDGE, VARIANT_BITS["dry"], 0).astype(np.int8)
    return out


def variant_name(biome_key: str, bits: int) -> str:
    """"Hot, Dry Crystal fields" for a biome and a variant flag set."""
    words = [spec.name for k, spec in VARIANTS.items() if bits & VARIANT_BITS[k]]
    name = BIOMES[biome_key].name
    return (", ".join(words) + " " + name[0].lower() + name[1:]) if words else name


def validate_content() -> None:
    from capabilities import validate_content as _  # noqa: F401  (import check only)
    assert len(BIOMES) >= 50
    for biome in BIOMES.values():
        assert biome.vegetation >= 0 and biome.stones, biome.key
        assert all(0 <= c <= 255 for c in biome.ground), biome.key
        assert biome.temperature[0] <= biome.temperature[1] and biome.moisture[0] <= biome.moisture[1], biome.key
        assert not biome.wet_twin or biome.wet_twin in BIOMES, biome.key
