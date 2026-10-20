"""The catalogue of a planet: its flora, fauna and materials, generated once from the seed.

A planet is a *pure function of (seed, culture)*: `generate_planet` rolls reusable species **templates** into concrete
**variants** (a template says "a broadleaf tree that likes moist, fertile temperate ground"; a variant is *this planet's*
particular blue, springy one) and a **material palette** (woods taken from the trees, stones by archetype, metal ores,
fibres from shrubs, hides from animals, sand, clay, coal). Everything is named through `naming.Namer` in a fixed order, so
names are stable, unique and reflect the entity's real properties and colour. The player's culture decides the
language of the names (see `naming`).

`NoiseWorldSource` keeps the `Planet`; worlds ask it which species may live at a place (`species_weights`), where
stones and ores are found (`stone_for`, `ore_for`) and what the planet is called.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import spriteconfig
import numpy as np  # type: ignore

import biomes
import namegen
from capabilities import Grant, grants
from damage import DamageType
from ecology import Habitat, suitability
from materials import Family, Material
from naming import Name, Namer, hue_name
from render_order import RenderOrder
from seeds import mix_seed
from species import ItemKind, PlantCategory, PlantSpecies, UnitSpecies, AIKind, Diet

RGB = Tuple[int, int, int]
Prop = Tuple[float, float]


# ── archetypes (property ranges) ────────────────────────────────────────────────────────────────────────
def _arch(color: RGB, family: Family, **ranges) -> dict:
    return {"color": color, "family": family, "ranges": ranges}


STONE_ARCHETYPES: Dict[str, dict] = {
    "grey": _arch((125, 125, 130), Family.STONE, hardness=(6, 8), toughness=(5, 7), tenacity=(1, 3), abrasivity=(2, 4), density=(6, 8), insulation=(2, 4), thermal_conductivity=(4, 6)),
    "dark": _arch((55, 55, 65), Family.STONE, hardness=(6, 8), toughness=(4, 6), tenacity=(1, 3), abrasivity=(3, 5), density=(7, 9), insulation=(2, 3), thermal_conductivity=(3, 5)),
    "pale": _arch((205, 195, 170), Family.STONE, hardness=(3, 5), toughness=(3, 5), tenacity=(1, 2), abrasivity=(5, 8), density=(4, 6), insulation=(3, 5), thermal_conductivity=(3, 4)),
    "red": _arch((160, 80, 60), Family.STONE, hardness=(5, 7), toughness=(4, 6), tenacity=(1, 2), abrasivity=(3, 5), density=(6, 8), insulation=(2, 3), thermal_conductivity=(4, 5)),
    "crystal": _arch((160, 190, 230), Family.CRYSTAL, hardness=(7, 9), toughness=(2, 4), abrasivity=(4, 6), density=(4, 6), transparency=(5, 8), insulation=(1, 2), thermal_conductivity=(3, 5), incandescence=(0, 5), radioactivity=(0, 3)),
    "flint": _arch((70, 70, 60), Family.STONE, hardness=(8, 9.5), toughness=(2, 3.5), abrasivity=(4, 6), density=(6, 7), insulation=(1, 3), thermal_conductivity=(3, 5)),
    "porous": _arch((190, 185, 175), Family.STONE, hardness=(2, 4), toughness=(2, 4), density=(1.5, 3), insulation=(8, 10), thermal_conductivity=(0.5, 2)),
}
SURFACE_EXTRAS = ("flint", "porous")
"""Archetypes found among the loose stones of any biome (a knapping stone and a light insulating mineral)."""

# metal: (ore ranges, metal ranges, melting point)
METAL_ARCHETYPES: Dict[str, dict] = {
    "conductive": {"ore": _arch((80, 140, 110), Family.STONE, hardness=(3, 4), toughness=(3, 4), density=(6, 7), abrasivity=(1, 2)),
                   "metal": _arch((190, 110, 60), Family.METAL, hardness=(3, 4), toughness=(6, 7), tenacity=(7, 8), density=(8, 9), electrical_conductivity=(9, 10), thermal_conductivity=(8, 9)), "melt": 1080},
    "structural": {"ore": _arch((110, 60, 50), Family.STONE, hardness=(4, 5), toughness=(3, 4), density=(7, 8), abrasivity=(1, 2)),
                   "metal": _arch((150, 150, 160), Family.METAL, hardness=(6, 7), toughness=(6, 8), tenacity=(7, 8), density=(7, 8), electrical_conductivity=(3, 4), thermal_conductivity=(4, 5)), "melt": 1500},
    "heavy": {"ore": _arch((90, 95, 105), Family.STONE, hardness=(2, 3), toughness=(3, 4), density=(8, 9), abrasivity=(0, 1)),
              "metal": _arch((85, 90, 100), Family.METAL, hardness=(1, 2), toughness=(3, 4), tenacity=(2, 3), density=(9, 10), electrical_conductivity=(2, 3), thermal_conductivity=(3, 4)), "melt": 330},
}
RADIOACTIVE = _arch((120, 160, 90), Family.STONE, hardness=(3, 5), toughness=(2, 4), density=(8, 9.5), radioactivity=(6, 9), incandescence=(2, 4), thermal_conductivity=(2, 4))
SAND = _arch((225, 210, 160), Family.SAND, hardness=(5, 6.5), toughness=(1, 2), density=(3, 5), abrasivity=(5, 7), transparency=(2, 4), thermal_conductivity=(2, 3))
CLAY = _arch((175, 100, 70), Family.CLAY, hardness=(1.5, 2.5), toughness=(2, 3), tenacity=(2, 3), density=(4, 5), insulation=(3, 4), thermal_conductivity=(2, 3))
COAL = _arch((25, 25, 28), Family.FUEL, hardness=(2, 3), toughness=(2, 3), density=(3, 4), flammability=(3.5, 4.5), combustibility=(8.5, 9.5))


def _roll(rng: random.Random, ranges: Mapping[str, Prop]) -> Dict[str, float]:
    return {prop: round(rng.uniform(lo, hi), 1) for prop, (lo, hi) in ranges.items()}


def _tint(rng: random.Random, color: RGB, spread: int = 22) -> RGB:
    return tuple(max(0, min(255, c + rng.randint(-spread, spread))) for c in color)  # type: ignore


# ── flora templates ─────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class FloraTemplate:
    key: str
    category: PlantCategory
    sprites: Tuple[Tuple[int, int], ...]
    habitat: Habitat
    variants: int = 1
    rarity: float = 1.0
    fruit_chance: float = 0.8
    max_hp: int = 30
    growth_cycle: int = 10
    color_range: Tuple[RGB, RGB] = ((40, 90, 40), (140, 190, 90))
    wood_bias: Tuple[Tuple[str, float], ...] = ()
    name_family: str = "tree"
    native: bool = False             # grows only in the biomes whose `plants` list it (see `plant_factors`); its habitat is the biome, not a climate
    fixed_hue: bool = False          # keeps its own colours when the planet's foliage hue shifts (fungi, crystals, ash...)


# What each kind of plant looks like, in everyday words (the sprite decides the shape; see components/names.tree_pos_names):
# a species is named "<distinguishing word> <form>", e.g. "scarlet fir".
FORMS: Dict[str, Tuple[str, ...]] = {
    "broadleaf": ("oak", "maple", "beech", "elm", "birch", "apple tree", "plum tree", "pear tree"), "acacia": ("acacia", "thorn tree", "jacaranda"),
    "willow": ("willow", "weeping tree"), "conifer": ("pine", "fir", "larch", "spruce", "hemlock"),
    "cypress": ("cypress", "cedar", "juniper"), "palm": ("palm", "fan palm"), "coast_palm": ("palm", "beach palm"),
    "fungal_tree": ("toadstool", "giant mushroom", "morel", "shelf fungus"), "cactus": ("cactus", "cereus", "succulent"),
    "barrel_cactus": ("barrel cactus", "pincushion"), "reeds": ("reed", "rush", "sedge", "cane"),
    "crop": ("beet", "turnip", "radish", "carrot"), "bush": ("bush", "shrub", "scrub"), "thorns": ("thornbush", "bramble", "briar", "thistle"),
    "spore_bush": ("puffball", "spore bush"), "shard_bush": ("glass thorn", "shard bush"), "ash_shrub": ("ash shrub", "cinder bush"),
    "dead_tree": ("dead tree", "snag"), "beach_grass": ("dune grass", "marram", "sedge"),
    "meadow_flower": ("flower", "bell", "star", "aster", "daisy"), "meadow_bloom": ("bell", "aster", "star", "lily"),
    "marsh_flower": ("marsh bell", "water star", "bog aster"), "dry_flower": ("sun star", "dust aster", "desert bell"),
    "crystal_bloom": ("frost bell", "glass flower", "shard bloom"),
    "frost_tree": ("rime fir", "ice pine", "frost spruce"), "rime_shrub": ("rime bush", "frost shrub"), "frost_bloom": ("ice bell", "rime star"),
    # the plants of the biome catalogue (see `biomes`)
    "tallgrass": ("bluestem", "fescue", "ryegrass", "switchgrass"), "golden_grass": ("wheatgrass", "oat grass", "needlegrass", "timothy"),
    "crop_wild": ("wild beet", "wild turnip", "wild radish", "wild carrot"),
    "ancient_oak": ("old oak", "elder beech", "great elm"), "ancient_giant": ("redwood", "elder oak", "giant fig"),
    "jungle_giant": ("kapok", "ceiba", "strangler fig"), "amber_tree": ("amber oak", "honey beech", "gold maple"),
    "thorn_tree": ("mesquite", "kiaat", "thorn tree"), "petrified_tree": ("stone tree", "fossil trunk", "flint tree"),
    "giant_cap": ("great cap", "umbrella cap", "giant puffcap"), "crystal_tree": ("crystal tree", "glass spire", "quartz tree"),
    "cinder_tree": ("cinder tree", "char pine", "ember pine"), "tendril_tree": ("tendril tree", "sinew tree", "coil tree"),
    "mangrove": ("mangrove", "stilt tree", "buttonwood"), "fern": ("fern", "bracken", "shield fern"),
    "vine_creeper": ("vine", "liana", "creeper"), "creeper": ("sinew vine", "coil", "bindweed"), "flesh_pod": ("pod", "gut bulb", "flesh bulb"),
    "weed": ("weed", "dock", "nettle", "fireweed"), "ivy": ("ivy", "bindvine"), "saltbush": ("saltbush", "samphire", "glasswort"),
    "agave": ("agave", "yucca", "aloe"), "glass_cactus": ("glass cactus", "crystal spine", "glass pillar"),
    "bone_thorn": ("bone thorn", "rib bush", "white briar"), "glowcap": ("glowcap", "lantern cap", "lumen cap"),
    "rot_cap": ("rot cap", "blight cap", "mould cap"), "algae_mat": ("algal mat", "slime weed", "scum"),
    "glow_reed": ("glow reed", "lantern rush"), "lumen_frond": ("lumen frond", "glow fern"),
    "toxic_bloom": ("bane bell", "gall flower", "venom star"), "spore_flower": ("spore bell", "puff flower"),
    "ember_bloom": ("ember bell", "cinder flower", "fire star"), "iris_bloom": ("prism bell", "iris star", "sheen flower"),
}
# What each form bears: (fruit sprite, fruit name). An oak bears acorns, an apple tree apples; unlisted forms fall back to the
# template's list. The sprites are the item sheet's row 21 (see components.names.fruit_pos_names).
FORM_FRUITS: Dict[str, Tuple[Tuple[Tuple[int, int], str], ...]] = {
    "oak": (((13, 21), "acorn"),), "beech": (((14, 21), "beechnut"),), "maple": (((8, 21), "seed"),), "elm": (((8, 21), "seed"),),
    "birch": (((8, 21), "seed"),), "apple tree": (((3, 21), "apple"),), "plum tree": (((21, 21), "plum"),), "pear tree": (((17, 21), "pear"),),
    "acacia": (((122, 0), "bean pod"),), "thorn tree": (((122, 0), "bean pod"),), "jacaranda": (((122, 0), "bean pod"),),
    "willow": (((18, 21), "catkin"),), "weeping tree": (((18, 21), "catkin"),),
    "pine": (((14, 21), "cone"),), "fir": (((14, 21), "cone"),), "larch": (((14, 21), "cone"),), "spruce": (((14, 21), "cone"),),
    "hemlock": (((14, 21), "cone"),), "cypress": (((14, 21), "cone"),), "cedar": (((14, 21), "cone"),), "juniper": (((18, 21), "juniper berry"),),
    "palm": (((122, 0), "date"),), "fan palm": (((122, 0), "date"),), "beach palm": (((15, 21), "coconut"),),
    "toadstool": (((0, 21), "spore cap"),), "giant mushroom": (((0, 21), "spore cap"),), "morel": (((0, 21), "spore cap"),),
    "shelf fungus": (((0, 21), "spore cap"),), "puffball": (((0, 21), "spore cap"),), "spore bush": (((0, 21), "spore cap"),),
    "cactus": (((17, 21), "prickly pear"),), "cereus": (((17, 21), "prickly pear"),), "succulent": (((17, 21), "prickly pear"),),
    "barrel cactus": (((17, 21), "prickly pear"),), "pincushion": (((17, 21), "prickly pear"),),
    "reed": (((22, 21), "seed head"),), "rush": (((22, 21), "seed head"),), "sedge": (((22, 21), "seed head"),), "cane": (((22, 21), "seed head"),),
    "beet": (((2, 21), "root"),), "turnip": (((2, 21), "root"),), "radish": (((2, 21), "root"),), "carrot": (((2, 21), "root"),),
    "dune grass": (((22, 21), "seed head"),), "marram": (((22, 21), "seed head"),),
    "bush": (((18, 21), "berry"), ((24, 21), "berry")), "shrub": (((18, 21), "berry"),), "scrub": (((18, 21), "berry"),),
    "thornbush": (((18, 21), "sloe"),), "bramble": (((18, 21), "blackberry"),), "briar": (((6, 21), "hip"),), "thistle": (((22, 21), "seed head"),),
    "glass thorn": (((24, 21), "glass berry"),), "shard bush": (((24, 21), "glass berry"),), "ash shrub": (((18, 21), "ash berry"),),
    "cinder bush": (((18, 21), "ember berry"),),
    "bluestem": (((22, 21), "seed head"),), "fescue": (((22, 21), "seed head"),), "ryegrass": (((22, 21), "grain"),), "switchgrass": (((22, 21), "seed head"),),
    "wheatgrass": (((22, 21), "grain"),), "oat grass": (((22, 21), "oats"),), "needlegrass": (((22, 21), "seed head"),), "timothy": (((22, 21), "grain"),),
    "wild beet": (((2, 21), "root"),), "wild turnip": (((2, 21), "root"),), "wild radish": (((2, 21), "root"),), "wild carrot": (((2, 21), "root"),),
    "old oak": (((13, 21), "acorn"),), "elder beech": (((14, 21), "beechnut"),), "great elm": (((8, 21), "seed"),),
    "redwood": (((14, 21), "cone"),), "elder oak": (((13, 21), "acorn"),), "giant fig": (((19, 21), "fig"),),
    "kapok": (((15, 21), "seed pod"),), "ceiba": (((15, 21), "seed pod"),), "strangler fig": (((19, 21), "fig"),),
    "amber oak": (((13, 21), "amber acorn"),), "honey beech": (((14, 21), "beechnut"),), "gold maple": (((8, 21), "seed"),),
    "mesquite": (((122, 0), "bean pod"),), "kiaat": (((122, 0), "bean pod"),),
    "giant fig": (((19, 21), "fig"),), "mangrove": (((15, 21), "propagule"),), "stilt tree": (((15, 21), "propagule"),), "buttonwood": (((6, 21), "button"),),
    "agave": (((17, 21), "agave heart"),), "yucca": (((17, 21), "yucca fruit"),), "aloe": (((17, 21), "aloe pulp"),),
    "saltbush": (((18, 21), "salt berry"),), "samphire": (((18, 21), "sea bean"),), "glasswort": (((18, 21), "sea bean"),),
    "glowcap": (((0, 21), "glow cap"),), "lantern cap": (((0, 21), "glow cap"),), "lumen cap": (((0, 21), "glow cap"),),
    "rot cap": (((0, 21), "rot spore"),), "blight cap": (((0, 21), "rot spore"),), "mould cap": (((0, 21), "rot spore"),),
    "great cap": (((0, 21), "spore cap"),), "umbrella cap": (((0, 21), "spore cap"),), "giant puffcap": (((0, 21), "puffball"),),
    "flesh bulb": (((6, 21), "bulb"),), "gut bulb": (((6, 21), "bulb"),), "pod": (((6, 21), "seed pod"),),
    "fern": (((19, 21), "frond tip"),), "bracken": (((19, 21), "frond tip"),), "shield fern": (((19, 21), "frond tip"),),
    "vine": (((16, 21), "grape"),), "liana": (((16, 21), "grape"),), "creeper": (((16, 21), "berry"),),
    "glow reed": (((22, 21), "seed head"),), "lantern rush": (((22, 21), "seed head"),), "algal mat": (((12, 21), "algal nub"),),
}
BLOOM_SPRITE = (107, 0)
BLOOM_NOUNS = ("blossom", "bud")

_FERTILE = (0.4, 1.0)
FLORA_TEMPLATES: Tuple[FloraTemplate, ...] = (
    FloraTemplate("broadleaf", PlantCategory.TREE, ((0, 8), (1, 8)), Habitat((-0.3, 0.6), (0.0, 1.0), fertility=_FERTILE), variants=2, rarity=1.5),
    FloraTemplate("acacia", PlantCategory.TREE, ((2, 8),), Habitat((0.2, 0.9), (-0.45, 0.3)), rarity=1.0, wood_bias=(("hardness", 1.0), ("elasticity", 1.0))),
    FloraTemplate("willow", PlantCategory.TREE, ((2, 8),), Habitat((-0.1, 0.8), (0.1, 1.0), water=(0.4, 1.0)), rarity=1.2, wood_bias=(("elasticity", 2.5),)),
    FloraTemplate("conifer", PlantCategory.TREE, ((3, 8),), Habitat((-0.9, 0.1), (-0.3, 1.0), fertility=(0.1, 1.0)), variants=2, rarity=1.6, color_range=((20, 70, 40), (70, 120, 80)),
                  wood_bias=(("flammability", 1.5), ("combustibility", 1.0), ("insulation", 1.0))),
    FloraTemplate("cypress", PlantCategory.TREE, ((4, 8),), Habitat((0.1, 0.9), (0.2, 1.0), water=(0.2, 1.0)), rarity=1.0, wood_bias=(("toughness", 1.0),)),
    FloraTemplate("palm", PlantCategory.TREE, ((5, 8),), Habitat((0.3, 1.0), (-0.6, 0.6), water=(0.3, 1.0)), rarity=0.8, wood_bias=(("elasticity", 2.0), ("hardness", -1.5))),
    FloraTemplate("cactus", PlantCategory.TREE, ((102, 0), (103, 0)), Habitat((0.3, 1.0), (-1.0, -0.1)), rarity=1.2, color_range=((40, 120, 60), (100, 170, 90)),
                  fruit_chance=0.5, max_hp=18, wood_bias=(("toughness", -2.0), ("hardness", -2.0), ("tenacity", 1.0)), name_family="shrub"),
    FloraTemplate("reeds", PlantCategory.SHRUB, ((6, 9),), Habitat((-0.3, 1.0), (0.0, 1.0), water=(0.6, 1.0)), variants=1, rarity=2.0, fruit_chance=0.3, max_hp=6, growth_cycle=5, name_family="grass",
                  color_range=((100, 140, 60), (170, 190, 100))),
    FloraTemplate("bush", PlantCategory.SHRUB, ((105, 0),), Habitat((-0.5, 0.8), (-0.4, 1.0), fertility=(0.2, 1.0)), variants=2, rarity=2.0, max_hp=8, growth_cycle=5, name_family="shrub"),
    # the crop of a farm's field: never grows wild (no habitat), see `Planet.crop` and settlements.populate
    FloraTemplate("crop", PlantCategory.SHRUB, ((8, 9),), None, rarity=0.0, fruit_chance=1.0, max_hp=4, growth_cycle=5, name_family="grass",
                  color_range=((150, 140, 40), (210, 190, 80))),
    # flowers: small ground plants with one bloom each to pick (food now, medicine and cooking later)
    FloraTemplate("meadow_flower", PlantCategory.FLOWER, ((13, 9), (14, 9), (15, 9), (16, 9)), Habitat((-0.5, 0.7), (-0.2, 1.0), fertility=(0.2, 1.0)),
                  variants=4, rarity=3.0, fruit_chance=1.0, max_hp=2, growth_cycle=6, name_family="flower",
                  color_range=((130, 70, 90), (255, 240, 200))),
    FloraTemplate("marsh_flower", PlantCategory.FLOWER, ((17, 9), (18, 9), (0, 10)), Habitat((-0.2, 1.0), (0.3, 1.0), water=(0.3, 1.0)),
                  variants=3, rarity=2.5, fruit_chance=1.0, max_hp=2, growth_cycle=6, name_family="flower",
                  color_range=((90, 80, 150), (240, 220, 255))),
    FloraTemplate("dry_flower", PlantCategory.FLOWER, ((1, 10), (16, 9)), Habitat((0.1, 1.0), (-1.0, 0.1)),
                  variants=2, rarity=2.0, fruit_chance=1.0, max_hp=2, growth_cycle=8, name_family="flower",
                  color_range=((200, 90, 40), (255, 220, 110))),
    FloraTemplate("thorns", PlantCategory.SHRUB, ((106, 0),), Habitat((-1.0, 1.0), (-1.0, 0.3), fertility=(0.0, 0.8)), variants=1, rarity=1.5, fruit_chance=0.5, max_hp=8, growth_cycle=5, name_family="shrub"),
    # native flora: grows only in the biomes that list it in `Biome.plants`, and takes on the traits those biomes share (see `plant_traits`)
    FloraTemplate("fungal_tree", PlantCategory.TREE, ((101, 0),), Habitat(), native=True, fixed_hue=True, rarity=3.0,
                  color_range=((120, 70, 120), (220, 160, 200)), fruit_chance=0.4, max_hp=14, growth_cycle=8,
                  wood_bias=(("insulation", 2.5), ("toughness", -2.5), ("hardness", -2.0), ("density", -2.0)), name_family="fungus"),
    FloraTemplate("spore_bush", PlantCategory.SHRUB, ((105, 0),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=4.0, max_hp=8, growth_cycle=5,
                  name_family="fungus", color_range=((130, 70, 150), (230, 150, 210))),
    FloraTemplate("barrel_cactus", PlantCategory.SHRUB, ((106, 0),), Habitat(), native=True, variants=2, rarity=4.0, fruit_chance=0.6, max_hp=10,
                  growth_cycle=6, name_family="shrub", color_range=((60, 130, 70), (150, 180, 90))),
    FloraTemplate("shard_bush", PlantCategory.SHRUB, ((106, 0),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=4.0, fruit_chance=0.2, max_hp=12,
                  growth_cycle=8, name_family="shrub", color_range=((110, 140, 190), (190, 220, 245))),
    FloraTemplate("ash_shrub", PlantCategory.SHRUB, ((105, 0),), Habitat(), native=True, fixed_hue=True, variants=1, rarity=4.0, fruit_chance=0.1, max_hp=10,
                  growth_cycle=9, name_family="shrub", color_range=((60, 55, 55), (120, 85, 70))),
    FloraTemplate("dead_tree", PlantCategory.TREE, ((2, 8),), Habitat(), native=True, fixed_hue=True, variants=1, rarity=5.0, fruit_chance=0.0, max_hp=16, growth_cycle=14,
                  name_family="tree", color_range=((70, 62, 58), (115, 105, 98)), wood_bias=(("hardness", -1.5), ("toughness", -1.5), ("flammability", 1.5))),
    FloraTemplate("coast_palm", PlantCategory.TREE, ((5, 8),), Habitat(), native=True, rarity=5.0, wood_bias=(("elasticity", 2.0), ("hardness", -1.5)),
                  color_range=((70, 130, 50), (140, 190, 90))),
    FloraTemplate("beach_grass", PlantCategory.SHRUB, ((105, 0),), Habitat(), native=True, variants=2, rarity=5.0, fruit_chance=0.2, max_hp=6, growth_cycle=5,
                  name_family="grass", color_range=((170, 180, 90), (225, 220, 140))),
    FloraTemplate("frost_tree", PlantCategory.TREE, ((3, 8),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=4.0, fruit_chance=0.3, max_hp=16,
                  growth_cycle=12, color_range=((150, 180, 205), (225, 240, 250)),
                  wood_bias=(("insulation", 1.5), ("hardness", 1.0), ("elasticity", -1.5), ("flammability", -1.0))),
    FloraTemplate("rime_shrub", PlantCategory.SHRUB, ((105, 0),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=4.0, fruit_chance=0.4, max_hp=8,
                  growth_cycle=7, name_family="shrub", color_range=((140, 170, 200), (215, 235, 250))),
    FloraTemplate("frost_bloom", PlantCategory.FLOWER, ((16, 9), (0, 10)), Habitat(), native=True, fixed_hue=True,
                  variants=2, rarity=3.0, fruit_chance=1.0, max_hp=2, growth_cycle=10, name_family="flower", color_range=((170, 200, 240), (240, 248, 255))),
    FloraTemplate("meadow_bloom", PlantCategory.FLOWER, ((13, 9), (14, 9), (15, 9), (16, 9)), Habitat(), native=True,
                  variants=4, rarity=9.0, fruit_chance=1.0, max_hp=2, growth_cycle=6, name_family="flower", color_range=((200, 90, 140), (255, 250, 210))),
    FloraTemplate("crystal_bloom", PlantCategory.FLOWER, ((16, 9), (0, 10)), Habitat(), native=True, fixed_hue=True,
                  variants=2, rarity=3.0, fruit_chance=1.0, max_hp=2, growth_cycle=9, name_family="flower", color_range=((120, 150, 230), (220, 235, 255))),
    # grassland and farmland
    FloraTemplate("tallgrass", PlantCategory.SHRUB, ((6, 9), (7, 9)), Habitat(), native=True, variants=2, rarity=3.0, fruit_chance=0.3, max_hp=4, growth_cycle=4,
                  name_family="grass", color_range=((90, 140, 50), (150, 190, 80))),
    FloraTemplate("golden_grass", PlantCategory.SHRUB, ((7, 9), (5, 9)), Habitat(), native=True, fixed_hue=True, variants=2, rarity=3.0, fruit_chance=0.3, max_hp=4,
                  growth_cycle=4, name_family="grass", color_range=((190, 160, 60), (230, 200, 100))),
    FloraTemplate("crop_wild", PlantCategory.SHRUB, ((8, 9),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=1.0, max_hp=4, growth_cycle=5,
                  name_family="grass", color_range=((150, 140, 40), (210, 190, 80))),
    # forest
    FloraTemplate("ancient_oak", PlantCategory.TREE, ((1, 8),), Habitat(), native=True, rarity=2.0, max_hp=45, growth_cycle=24, color_range=((40, 100, 40), (90, 150, 60)),
                  wood_bias=(("hardness", 1.0), ("toughness", 1.5))),
    FloraTemplate("ancient_giant", PlantCategory.TREE, ((0, 8),), Habitat(), native=True, rarity=2.0, max_hp=70, growth_cycle=36, color_range=((40, 85, 40), (95, 135, 55)),
                  wood_bias=(("hardness", 1.5), ("toughness", 2.0), ("density", 1.0))),
    FloraTemplate("jungle_giant", PlantCategory.TREE, ((1, 8),), Habitat(), native=True, variants=2, rarity=2.0, max_hp=40, growth_cycle=18, color_range=((20, 110, 50), (70, 170, 90)),
                  wood_bias=(("hardness", -1.0), ("elasticity", 1.0), ("flammability", -1.0))),
    FloraTemplate("amber_tree", PlantCategory.TREE, ((2, 8),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=2.0, max_hp=22, growth_cycle=14,
                  color_range=((200, 130, 30), (240, 180, 70)), wood_bias=(("flammability", 1.0), ("elasticity", 1.0))),
    FloraTemplate("thorn_tree", PlantCategory.TREE, ((2, 8),), Habitat(), native=True, rarity=2.0, max_hp=16, growth_cycle=12, color_range=((90, 110, 50), (150, 150, 80)),
                  wood_bias=(("hardness", 1.5), ("toughness", 1.0))),
    FloraTemplate("petrified_tree", PlantCategory.TREE, ((5, 10),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.0, max_hp=40, growth_cycle=40,
                  color_range=((130, 125, 115), (190, 180, 165))),
    FloraTemplate("fern", PlantCategory.SHRUB, ((10, 9), (11, 9), (12, 9)), Habitat(), native=True, variants=2, rarity=3.0, fruit_chance=0.2, max_hp=3, growth_cycle=5,
                  name_family="grass", color_range=((40, 110, 50), (110, 180, 90))),
    FloraTemplate("vine_creeper", PlantCategory.SHRUB, ((23, 9), (24, 9)), Habitat(), native=True, variants=2, rarity=3.0, fruit_chance=0.6, max_hp=5, growth_cycle=5,
                  name_family="shrub", color_range=((30, 120, 50), (100, 180, 80))),
    FloraTemplate("ivy", PlantCategory.SHRUB, ((23, 10), (24, 10)), Habitat(), native=True, rarity=3.0, fruit_chance=0.3, max_hp=5, growth_cycle=5,
                  name_family="shrub", color_range=((50, 110, 50), (100, 160, 80))),
    FloraTemplate("weed", PlantCategory.SHRUB, ((5, 9), (19, 9)), Habitat(), native=True, variants=2, rarity=3.0, fruit_chance=0.2, max_hp=3, growth_cycle=4,
                  name_family="grass", color_range=((90, 130, 50), (150, 170, 80))),
    # arid
    FloraTemplate("agave", PlantCategory.SHRUB, ((102, 0),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.4, max_hp=10, growth_cycle=8,
                  name_family="shrub", color_range=((70, 130, 110), (130, 180, 150))),
    FloraTemplate("saltbush", PlantCategory.SHRUB, ((105, 0),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.4, max_hp=6, growth_cycle=6,
                  name_family="shrub", color_range=((150, 170, 150), (210, 220, 200))),
    FloraTemplate("glass_cactus", PlantCategory.SHRUB, ((103, 0),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.2, max_hp=12, growth_cycle=9,
                  name_family="shrub", color_range=((150, 210, 220), (210, 245, 250))),
    FloraTemplate("bone_thorn", PlantCategory.SHRUB, ((106, 0),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.0, max_hp=8, growth_cycle=9,
                  name_family="shrub", color_range=((200, 195, 175), (235, 230, 215))),
    # fungal
    FloraTemplate("giant_cap", PlantCategory.TREE, ((101, 0),), Habitat(), native=True, fixed_hue=True, rarity=3.0, color_range=((150, 70, 90), (230, 150, 140)),
                  fruit_chance=0.4, max_hp=24, growth_cycle=10, name_family="fungus",
                  wood_bias=(("insulation", 2.5), ("toughness", -2.5), ("hardness", -2.0), ("density", -2.0))),
    FloraTemplate("glowcap", PlantCategory.SHRUB, ((3, 10),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=3.0, fruit_chance=0.4, max_hp=6, growth_cycle=5,
                  name_family="fungus", color_range=((60, 200, 220), (150, 250, 230))),
    FloraTemplate("spore_flower", PlantCategory.FLOWER, ((0, 10),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=3.0, fruit_chance=1.0, max_hp=2,
                  growth_cycle=7, name_family="flower", color_range=((190, 120, 220), (240, 180, 250))),
    # volcanic and dead
    FloraTemplate("crystal_tree", PlantCategory.TREE, ((4, 8),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.2, max_hp=24, growth_cycle=16,
                  color_range=((120, 150, 230), (220, 240, 255)), wood_bias=(("hardness", 1.5), ("toughness", -1.0))),
    FloraTemplate("cinder_tree", PlantCategory.TREE, ((5, 10),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.1, max_hp=20, growth_cycle=16,
                  color_range=((70, 50, 50), (130, 70, 50))),
    FloraTemplate("ember_bloom", PlantCategory.FLOWER, ((16, 9),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=1.0, max_hp=2, growth_cycle=8,
                  name_family="flower", color_range=((240, 110, 40), (255, 200, 80))),
    FloraTemplate("rot_cap", PlantCategory.SHRUB, ((3, 10),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=3.0, fruit_chance=0.3, max_hp=6, growth_cycle=5,
                  name_family="fungus", color_range=((120, 100, 60), (170, 140, 90))),
    # alien
    FloraTemplate("tendril_tree", PlantCategory.TREE, ((6, 8),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.3, max_hp=24, growth_cycle=12,
                  color_range=((160, 80, 90), (210, 120, 130)), wood_bias=(("elasticity", 2.0), ("hardness", -2.0), ("insulation", 1.0))),
    FloraTemplate("flesh_pod", PlantCategory.SHRUB, ((2, 9),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=3.0, fruit_chance=0.6, max_hp=8, growth_cycle=6,
                  name_family="shrub", color_range=((190, 90, 110), (235, 150, 150))),
    FloraTemplate("creeper", PlantCategory.SHRUB, ((24, 9), (24, 10)), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.4, max_hp=5, growth_cycle=5,
                  name_family="shrub", color_range=((150, 70, 90), (210, 110, 120))),
    FloraTemplate("lumen_frond", PlantCategory.SHRUB, ((11, 9),), Habitat(), native=True, fixed_hue=True, variants=2, rarity=3.0, fruit_chance=0.3, max_hp=4, growth_cycle=5,
                  name_family="grass", color_range=((60, 200, 170), (130, 240, 200))),
    FloraTemplate("iris_bloom", PlantCategory.FLOWER, ((14, 9), (18, 9)), Habitat(), native=True, fixed_hue=True, variants=2, rarity=3.0, fruit_chance=1.0, max_hp=2,
                  growth_cycle=7, name_family="flower", color_range=((90, 130, 200), (220, 200, 230))),
    # wetland
    FloraTemplate("mangrove", PlantCategory.TREE, ((6, 8),), Habitat(), native=True, rarity=3.0, max_hp=20, growth_cycle=14, color_range=((50, 110, 70), (100, 160, 90)),
                  wood_bias=(("elasticity", 1.5), ("flammability", -1.0))),
    FloraTemplate("glow_reed", PlantCategory.SHRUB, ((6, 9),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.3, max_hp=5, growth_cycle=5,
                  name_family="grass", color_range=((90, 230, 200), (150, 255, 230))),
    FloraTemplate("toxic_bloom", PlantCategory.FLOWER, ((15, 9), (0, 10)), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=1.0, max_hp=2, growth_cycle=7,
                  name_family="flower", color_range=((160, 220, 60), (220, 255, 120))),
    FloraTemplate("algae_mat", PlantCategory.SHRUB, ((4, 9),), Habitat(), native=True, fixed_hue=True, rarity=3.0, fruit_chance=0.2, max_hp=3, growth_cycle=4,
                  name_family="grass", color_range=((60, 150, 90), (130, 200, 110))),
)

TREE_RESIST = ()  # damage to plants now comes from their material (see damage.py / materials.attack_factor)


# ── fauna templates ────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class FaunaTemplate:
    key: str
    sprite: Tuple[int, int]
    habitat: Habitat
    diet: Diet
    ai: AIKind
    max_hp: int
    power: int
    defense: int = 0
    rarity: float = 1.0
    name_family: str = "animal"
    hide_kind: str = "fur"           # what covers the body: fur | feather | chitin | scale | skin (see `species.COVERINGS`)
    corpse_sprite: Tuple[int, int] = (44, 16)
    grants: Tuple[str, ...] = ()
    xp: int = 20
    damage_type: DamageType = DamageType.BLUNT
    radius: int = 8
    base: str = ""                   # for a regional variant: the key of the baseline template it was generated from
    tint: Optional[Tuple[int, int, int]] = None   # pulls the rolled colour towards this one (a variant takes on its region)
    traits: Tuple[str, ...] = ()     # `biomes.TRAITS` of the region it is adapted to
    underground: bool = False        # lives in the caves only (placed by `underground`, never by the surface spawner; no habitat)


FAUNA_TEMPLATES: Tuple[FaunaTemplate, ...] = (
    FaunaTemplate("hopper", (3, 20), Habitat((-0.6, 0.8), (-0.4, 0.9), fertility=(0.3, 1.0)), Diet.HERBIVORE, AIKind.PASSIVE, 1, 3, rarity=1.6, name_family="small_herbivore", xp=10),
    FaunaTemplate("grazer", (1, 20), Habitat((-0.5, 0.7), (-0.35, 0.5), fertility=(0.25, 1.0)), Diet.HERBIVORE, AIKind.PASSIVE, 8, 2, rarity=1.6, name_family="grazer", xp=25),
    FaunaTemplate("strider", (5, 18), Habitat((0.0, 0.9), (-0.5, 0.2)), Diet.HERBIVORE, AIKind.PASSIVE, 11, 3, rarity=1.0, name_family="grazer", xp=30),
    FaunaTemplate("rooter", (2, 20), Habitat((-0.4, 0.8), (0.0, 1.0), fertility=(0.4, 1.0)), Diet.OMNIVORE, AIKind.PASSIVE, 10, 3, rarity=1.0, name_family="animal", xp=35, hide_kind="skin"),
    FaunaTemplate("hunter", (10, 20), Habitat((-0.9, 0.5), (-0.5, 1.0), fertility=(0.1, 1.0)), Diet.CARNIVORE, AIKind.HOSTILE, 16, 6, rarity=0.5, name_family="predator", damage_type=DamageType.SHARP, xp=40),
    FaunaTemplate("stalker", (0, 18), Habitat((-0.3, 1.0), (0.1, 1.0), fertility=(0.4, 1.0)), Diet.CARNIVORE, AIKind.HOSTILE, 14, 7, rarity=0.35, name_family="predator", damage_type=DamageType.SHARP, xp=50),
    FaunaTemplate("scuttler", (7, 18), Habitat((-0.2, 1.0), (0.1, 1.0), water=(0.4, 1.0)), Diet.HERBIVORE, AIKind.PASSIVE, 6, 2, defense=1, rarity=1.5, name_family="crawler", xp=20, hide_kind="chitin"),
    FaunaTemplate("webspinner", (2, 19), Habitat((0.0, 1.0), (-0.5, 1.0), fertility=(0.0, 0.8)), Diet.CARNIVORE, AIKind.PASSIVE, 5, 3, rarity=0.8, name_family="crawler", damage_type=DamageType.PIERCE, xp=25, hide_kind="chitin"),
    FaunaTemplate("serpent", (2, 18), Habitat((0.2, 1.0), (-0.8, 0.5)), Diet.CARNIVORE, AIKind.HOSTILE, 10, 5, rarity=0.5, name_family="serpent", damage_type=DamageType.PIERCE, xp=30, hide_kind="scale"),
    FaunaTemplate("flitter", (5, 20), Habitat((-0.4, 1.0), (-0.6, 1.0)), Diet.HERBIVORE, AIKind.PASSIVE, 2, 1, rarity=1.0, name_family="bird", xp=10, hide_kind="feather"),
)

FAUNA_FORMS: Dict[str, Tuple[str, ...]] = {
    # the everyday words for the animal each sprite draws (the first is the plainest); the colour word comes from the tint it is drawn with
    "hopper": ("hare", "rabbit"), "grazer": ("deer", "goat"), "strider": ("horse", "stag"), "rooter": ("boar", "hog"),
    "hunter": ("hound", "jackal"), "stalker": ("cat", "lynx"), "scuttler": ("crab", "scuttler"), "webspinner": ("spider",),
    "serpent": ("snake", "serpent", "viper"), "flitter": ("bird", "finch", "swift"),
}

CAVE_FAUNA: Tuple[FaunaTemplate, ...] = (
    # creatures of the caves (see `underground.UBIOMES` for where each lives); the planet rolls their colours and names like any other
    FaunaTemplate("cave_beetle", (0, 19), Habitat(), Diet.HERBIVORE, AIKind.PASSIVE, 7, 2, defense=1, rarity=1.0, name_family="crawler", xp=15, hide_kind="chitin", underground=True),
    FaunaTemplate("cave_moth", (1, 19), Habitat(), Diet.HERBIVORE, AIKind.PASSIVE, 2, 1, rarity=1.0, name_family="crawler", xp=8, hide_kind="chitin", underground=True),
    FaunaTemplate("cave_slug", (10, 18), Habitat(), Diet.HERBIVORE, AIKind.PASSIVE, 11, 2, rarity=1.0, name_family="animal", xp=20, hide_kind="skin", underground=True),
    FaunaTemplate("cave_bat", (6, 18), Habitat(), Diet.CARNIVORE, AIKind.HOSTILE, 10, 5, rarity=1.0, name_family="animal", xp=25, hide_kind="skin",
                  damage_type=DamageType.SHARP, underground=True),
    FaunaTemplate("cave_worm", (3, 19), Habitat(), Diet.CARNIVORE, AIKind.HOSTILE, 10, 5, rarity=1.0, name_family="serpent", xp=35, hide_kind="skin",
                  damage_type=DamageType.PIERCE, underground=True),
    FaunaTemplate("cave_crab", (13, 18), Habitat(), Diet.OMNIVORE, AIKind.PASSIVE, 12, 4, defense=2, rarity=1.0, name_family="crawler", xp=30, hide_kind="chitin",
                  underground=True),
)
FAUNA_FORMS.update({"cave_beetle": ("beetle",), "cave_moth": ("moth",), "cave_slug": ("slug",), "cave_bat": ("bat",), "cave_worm": ("worm",),
                    "cave_crab": ("crab", "rock crab")})

# A region's own animals are not hand-written: they are the baseline creatures above, generated again for a biome *family* through the
# same pipeline (`_make_fauna`) with the family's traits applied, so a "volcanic strider" is a strider that grew up on hot rock.
@dataclass(frozen=True)
class FamilyFauna:
    bases: Tuple[str, ...]            # baseline templates that get a variant in the family
    tint: Tuple[int, int, int]        # colour the variants are pulled towards
    covering: str = ""                # replaces a fur or skin covering ("" = keep the baseline's)
    hp: float = 1.0                   # multiplies hit points
    power: int = 0                    # added to the power of hostile variants
    defense: int = 0                  # added to everyone's defence


FAMILY_FAUNA: Dict[str, FamilyFauna] = {
    "arid": FamilyFauna(("strider", "scuttler", "serpent"), (220, 160, 90), covering="scale", defense=1),
    "forest": FamilyFauna(("grazer", "rooter", "stalker"), (110, 105, 70)),
    "fungal": FamilyFauna(("hopper", "scuttler", "stalker"), (150, 100, 200), covering="skin", hp=0.9),
    "crystal": FamilyFauna(("grazer", "scuttler", "hunter"), (120, 150, 230), covering="scale", hp=1.2, defense=2),
    "volcanic": FamilyFauna(("strider", "scuttler", "hunter"), (170, 60, 40), covering="scale", power=1, defense=1),
    "decay": FamilyFauna(("rooter", "strider", "hunter"), (110, 100, 110), hp=0.9, power=1),
    "alien": FamilyFauna(("scuttler", "stalker", "flitter"), (90, 200, 170), covering="skin", hp=0.9, power=1),
    "wet": FamilyFauna(("scuttler", "flitter", "rooter"), (80, 140, 150), covering="skin"),
    "cold": FamilyFauna(("grazer", "hopper", "hunter"), (205, 225, 245), covering="fur", hp=1.1),
    "coast": FamilyFauna(("scuttler", "flitter", "rooter"), (230, 215, 170), defense=1),
    "urban": FamilyFauna(("hopper", "rooter", "flitter"), (150, 140, 130)),
}
FAMILY_FAUNA_RARITY = 4.0
"""A variant is this many times as common as its baseline inside its family (it lives nowhere else)."""


def family_variants(templates: Tuple[FaunaTemplate, ...] = FAUNA_TEMPLATES) -> Tuple[FaunaTemplate, ...]:
    """The templates of the regional animals: each baseline named in `FAMILY_FAUNA`, re-made for its biome family."""
    by_key = {t.key: t for t in templates}
    out = []
    for family, spec in FAMILY_FAUNA.items():
        for key in spec.bases:
            base = by_key[key]
            hostile = base.ai is AIKind.HOSTILE
            covering = spec.covering if spec.covering and base.hide_kind in ("fur", "skin") else base.hide_kind
            out.append(replace(
                base, key=f"{key}.{family}", base=key, habitat=Habitat(substrate=(family,)), hide_kind=covering, tint=spec.tint,
                max_hp=max(1, round(base.max_hp * spec.hp)), power=base.power + (spec.power if hostile else 0),
                defense=base.defense + spec.defense, rarity=base.rarity * FAMILY_FAUNA_RARITY,
                traits=biomes.FAMILIES[family].traits))
    return tuple(out)


UNLISTED_PLANT = 0.2
"""Weight of a plant that a biome does not list, in a biome that lists some (what the biome names is what it is known for)."""


@lru_cache(maxsize=None)
def plant_factors(template_key: str) -> np.ndarray:
    """One number per biome index: how much of the biome's ground a plant template gets (see `Biome.plants`)."""
    native = {t.key for t in FLORA_TEMPLATES if t.native}
    out = []
    for key in biomes.BIOME_IDS:
        biome = biomes.BIOMES[key]
        if template_key in biome.plants:
            out.append(biome.plants[template_key])
        elif biome.plants_only or template_key in native:
            out.append(0.0)
        else:
            out.append(UNLISTED_PLANT if biome.plants else 1.0)
    return np.array(out, dtype=float)


def validate_plants() -> None:
    """Every plant a biome lists exists, and every native plant is listed by some biome."""
    keys = {t.key for t in FLORA_TEMPLATES}
    for biome in biomes.BIOMES.values():
        for plant in biome.plants:
            assert plant in keys, f"{biome.key} lists the unknown plant {plant}"
    for template in FLORA_TEMPLATES:
        assert not template.native or biomes.listing(template.key), f"native plant {template.key} grows in no biome"


COVERING_RANGES = {   # property ranges of each body covering's material
    "fur": dict(insulation=(5, 8), tenacity=(3, 5), toughness=(2, 4), hardness=(0.5, 1.5), flammability=(5, 8),
                combustibility=(3, 5), thermal_conductivity=(0.5, 2), density=(1, 2)),
    "skin": dict(insulation=(2, 4), tenacity=(4, 6), toughness=(3, 5), hardness=(1, 2), flammability=(3, 5),
                 combustibility=(1, 3), thermal_conductivity=(1, 2), density=(1.5, 2.5)),
    "feather": dict(insulation=(6.5, 9), tenacity=(1, 3), toughness=(1, 3), hardness=(0.3, 1), flammability=(5, 8),
                    combustibility=(2, 4), thermal_conductivity=(0.3, 1.2), density=(0.5, 1.2)),
    "chitin": dict(hardness=(6, 8), toughness=(3, 5), tenacity=(1, 2), density=(2, 4), insulation=(1, 2), flammability=(0, 1)),
    "scale": dict(hardness=(4, 6), toughness=(5, 7), tenacity=(3, 5), density=(3, 5), insulation=(1, 3), flammability=(0, 1.5)),
}

FUR_NOTABLE = (  # (chance, property ranges): the "interesting" fur a planet's animal may have
    ("conductive", {"electrical_conductivity": (7, 9)}),
    ("fuel", {"flammability": (7, 9), "combustibility": (6, 8)}),
    ("down", {"insulation": (9, 10)}),
    ("elastic", {"elasticity": (8, 9.5), "tenacity": (7, 8)}),
)


@dataclass(frozen=True)
class Planet:
    seed: int
    culture: str
    name: str
    oxygen: float
    temp_offset: int
    flora: Tuple[PlantSpecies, ...]
    fauna: Tuple[UnitSpecies, ...]
    materials: Tuple[Tuple[str, Material], ...]          # id -> material (ordered for stable pickles)
    stone_ids: Tuple[Tuple[str, Tuple[str, ...]], ...]    # archetype -> material ids
    ore_ids: Tuple[str, ...]                              # ore material ids (each has refines_to)
    sand_id: str
    clay_id: str
    coal_id: str
    radioactive_id: str
    glosses: Tuple[Tuple[str, str], ...] = ()                # name -> English meaning (empty for English names)

    def material(self, material_id: str) -> Material:
        return dict(self.materials)[material_id]

    def definitions(self) -> List:
        found: List = list(self.flora) + list(self.fauna)
        found += [s.fruit for s in self.flora if s.fruit is not None]
        return found

    def stones_for_biome(self, biome_key: str) -> List[Material]:
        """Stones of a biome and the everywhere ones."""
        by_arch = dict(self.stone_ids)
        mats = dict(self.materials)
        keys = list(dict.fromkeys(list(biomes.BIOMES[biome_key].stones) + list(SURFACE_EXTRAS)))
        return [mats[i] for k in keys for i in by_arch.get(k, ())]

    def species_weights(self, env: Mapping[str, object], category: Optional[PlantCategory] = None) -> Tuple[List[PlantSpecies], np.ndarray]:
        """Flora of the given category with their spawn weight for each tile of `env` (arrays): shape (n_species, *tile_shape)."""
        pool = [s for s in self.flora if s.habitat is not None and ((category is None and s.category is not PlantCategory.FLOWER) or s.category is category)]
        weights = np.stack([suitability(s.habitat, env) * s.rarity for s in pool]) if pool else np.zeros((0,))
        if pool and "biome" in env:
            here = np.asarray(env["biome"])
            other = np.asarray(env["other"]) if "other" in env else None
            edge = np.asarray(env.get("edge", 0.0))

            def blend(table: np.ndarray) -> np.ndarray:        # a region's plants thin out and the neighbour's come in over a border
                value = table[here]
                return value if other is None else value * (1.0 - edge) + table[other] * edge

            weights = np.stack([weights[i] * blend(plant_factors(s.key.split(":")[2])) for i, s in enumerate(pool)])
            if category is None:
                share = blend(biomes.table("tree_share"))
                for i, species in enumerate(pool):
                    if species.category is PlantCategory.TREE:
                        weights[i] = weights[i] * share
        return pool, weights

    @property
    def crop(self) -> PlantSpecies:
        """The plant this planet's farmers grow (a root vegetable that is never found wild)."""
        return next(s for s in self.flora if s.habitat is None)

    def fauna_weights(self, env: Mapping[str, object]) -> Tuple[List[UnitSpecies], np.ndarray]:
        pool = [s for s in self.fauna if s.habitat is not None]        # (the cave creatures live below, see `cave_fauna`)
        weights = np.stack([suitability(s.habitat, env) * s.rarity for s in pool]) if pool else np.zeros((0,))
        return pool, weights


    def cave_fauna(self, biome_key: str) -> Tuple[List[UnitSpecies], List[float]]:
        """The creatures that live in an underground biome and their relative weights (empty when none do)."""
        import underground
        by_key = {s.key.split(":")[-1]: s for s in self.fauna}
        found = [(by_key[k], w) for k, w in underground.UBIOMES[biome_key].fauna if k in by_key]
        return [s for s, _ in found], [w for _, w in found]


CULTURE_NAME_SET = {"human": "survey", "selenite": "selenite", "mau": "mau", "corporate": "survey"}


def generate_planet(seed: int, culture: str = "human") -> Planet:
    """Roll the whole catalogue (deterministic). Order of generation is fixed so names never depend on anything else."""
    rng = random.Random(mix_seed(seed, 31337))
    namer = Namer(mix_seed(seed, 4242), culture)
    materials: Dict[str, Material] = {}

    def add(material: Material) -> Material:
        assert material.id not in materials
        materials[material.id] = material
        return material

    # planet-wide traits
    name = namegen.generate_name(CULTURE_NAME_SET.get(culture, "survey"), random.Random(mix_seed(seed, 5)))
    oxygen = round(rng.uniform(0.16, 0.26), 3)
    temp_offset = rng.randint(-6, 6)

    # stones (one or two variants of each archetype)
    stone_ids: Dict[str, List[str]] = {}
    for arch, spec in STONE_ARCHETYPES.items():
        for i in range(2 if arch in ("grey", "dark", "pale", "red") else 1):
            props = _roll(rng, spec["ranges"])
            color = _tint(rng, spec["color"])
            mid = f"stone:{arch}:{i}"
            nm = namer.name(mid, spec["family"].value, color, props)
            add(Material(mid, nm.text, spec["family"], color, **props))
            stone_ids.setdefault(arch, []).append(mid)

    # ores and their metals
    ore_ids: List[str] = []
    for arch, spec in METAL_ARCHETYPES.items():
        metal_props = _roll(rng, spec["metal"]["ranges"])
        metal_color = _tint(rng, spec["metal"]["color"], 14)
        metal_id = f"metal:{arch}"
        metal_name = namer.name(metal_id, "metal", metal_color, metal_props)
        add(Material(metal_id, metal_name.text, Family.METAL, metal_color, melting_point=spec["melt"], **metal_props))
        ore_props = _roll(rng, spec["ore"]["ranges"])
        ore_color = _tint(rng, spec["ore"]["color"], 14)
        ore_id = f"ore:{arch}"
        ore_name = namer.name(ore_id, "stone", ore_color, ore_props)
        add(Material(ore_id, ore_name.text + " ore", Family.STONE, ore_color, refines_to=metal_id, **ore_props))
        ore_ids.append(ore_id)
    rad_props = _roll(rng, RADIOACTIVE["ranges"])
    rad_color = _tint(rng, RADIOACTIVE["color"])
    rad_name = namer.name("ore:radioactive", "crystal", rad_color, rad_props)
    add(Material("ore:radioactive", rad_name.text + " ore", Family.STONE, rad_color, **rad_props))

    sand_props = _roll(rng, SAND["ranges"])
    sand_color = _tint(rng, SAND["color"])
    add(Material("sand:0", namer.name("sand:0", "sand", sand_color, sand_props).text, Family.SAND, sand_color,
                 is_amorphous=True, melting_point=rng.randint(1300, 1480), **sand_props))
    clay_props = _roll(rng, CLAY["ranges"])
    clay_color = _tint(rng, CLAY["color"])
    add(Material("clay:0", namer.name("clay:0", "clay", clay_color, clay_props).text, Family.CLAY, clay_color, **clay_props))
    coal_props = _roll(rng, COAL["ranges"])
    coal_color = _tint(rng, COAL["color"], 6)
    add(Material("coal:0", namer.name("coal:0", "fuel", coal_color, coal_props).text, Family.FUEL, coal_color,
                 burn_yield=round(rng.uniform(100, 140), 1), burn_duration=rng.randint(16, 24), **coal_props))

    # flora (a planet-wide foliage hue shift: green planets, blue planets, red planets)
    hue_shift = rng.choice((0.0, 0.0, 0.08, 0.35, 0.55, 0.7, 0.9))
    flora: List[PlantSpecies] = []
    for template in FLORA_TEMPLATES:
        for i in range(template.variants):
            flora.append(_make_flora(rng, namer, add, template, i, hue_shift))

    # fauna
    fauna: List[UnitSpecies] = []
    for template in FAUNA_TEMPLATES + family_variants() + CAVE_FAUNA:
        fauna.append(_make_fauna(rng, namer, add, template))

    return Planet(
        seed=seed, culture=culture, name=name, oxygen=oxygen, temp_offset=temp_offset,
        flora=tuple(flora), fauna=tuple(fauna), materials=tuple(materials.items()),
        stone_ids=tuple((k, tuple(v)) for k, v in stone_ids.items()), ore_ids=tuple(ore_ids),
        sand_id="sand:0", clay_id="clay:0", coal_id="coal:0", radioactive_id="ore:radioactive",
        glosses=tuple(sorted(namer.glosses.items())) if culture != "human" else (),
    )


def _shift_hue(color: RGB, shift: float) -> RGB:
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in color))
    r, g, b = colorsys.hsv_to_rgb((h + shift) % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def _make_flora(rng: random.Random, namer: Namer, add, template: FloraTemplate, index: int, hue_shift: float = 0.0) -> PlantSpecies:
    lo, hi = template.color_range
    if template.key == "dead_tree":     # (grey-brown wood: one shared brightness, so it never drifts to green or blue)
        t = rng.random()
        color = tuple(int(lo[i] + (hi[i] - lo[i]) * t) for i in range(3))
    else:
        color = tuple(rng.randint(lo[i], hi[i]) for i in range(3))
    if not template.fixed_hue and template.key != "crop":   # (fungus, crystal, dead wood and ash keep their own colours)
        color = _shift_hue(color, hue_shift + rng.uniform(-0.04, 0.04) + 0.1 * index)    # (a template's variants differ in colour)
    slot = index % len(template.sprites)
    sprite = spriteconfig.get(f"flora.{template.key}.{slot}", template.sprites[slot])
    if template.category is PlantCategory.FLOWER:
        return _make_flower(rng, namer, template, index, color, sprite)
    if template.category is PlantCategory.TREE:
        ranges = dict(hardness=(3, 6), toughness=(4, 8), tenacity=(3, 6), density=(3, 7), elasticity=(2, 7), insulation=(3, 6),
                      thermal_conductivity=(1, 3), flammability=(5, 7.5), combustibility=(5, 7.5))
        props = _roll(rng, ranges)
        for prop, delta in template.wood_bias:
            props[prop] = max(0.0, min(10.0, props[prop] + delta))
        _adapt(props, template)
        family, key = "wood", f"wood:{template.key}:{index}"
        fam_enum = Family.WOOD
        fuel = dict(burn_yield=round(20 + props["combustibility"] * 5, 1), burn_duration=max(2, int(props["combustibility"] * 1.4))) if props["combustibility"] >= 0.5 else {}
    else:
        ranges = dict(hardness=(1, 3), toughness=(2, 4), tenacity=(5, 8), density=(1, 3), elasticity=(2, 6), insulation=(2, 4),
                      flammability=(6, 8), combustibility=(2, 4.5))
        props = _roll(rng, ranges)
        _adapt(props, template)
        family, key = "fiber", f"fiber:{template.key}:{index}"
        fam_enum = Family.FIBER
        fuel = dict(burn_yield=round(4 + props["combustibility"] * 2, 1), burn_duration=2) if props["combustibility"] >= 0.5 else {}
    forms = FORMS.get(template.key) or (("bush",) if template.category is PlantCategory.SHRUB else ("tree",))
    form = rng.choice(forms)     # (drawn here, not by the namer, so the world does not depend on the naming culture)
    name = namer.organism(f"flora:{template.key}:{index}", (form,), color, props, template.name_family if template.name_family in ("fungus", "grass", "shrub") else family)
    material = add(Material(key, name.text, fam_enum, color, **props, **fuel))
    fruit = None
    if rng.random() < template.fruit_chance:
        fruit = _make_fruit(rng, namer, template, index, color, name, form)
    stem = material if template.category is PlantCategory.TREE else None
    fiber = material if template.category is PlantCategory.SHRUB else None
    return PlantSpecies(
        f"planet:flora:{template.key}:{index}", name.text, template.category, sprite=sprite,
        corpse_sprite=(4, 10) if template.category is PlantCategory.TREE else (3, 9), color=color, fruit=fruit,
        max_hp=template.max_hp, resistances=(), growth_cycle=template.growth_cycle,
        blocks_movement=template.category is PlantCategory.TREE, blocks_sight=template.category is PlantCategory.TREE,
        render_order=RenderOrder.TREE if template.category is PlantCategory.TREE else RenderOrder.SHRUB,
        habitat=template.habitat, material=stem, fiber=fiber, rarity=template.rarity,
    )


def _adapt(props: Dict[str, float], template: FloraTemplate) -> None:
    """Shift a native plant's properties by the traits all the biomes it grows in share (a plant of hot country is heat-proof)."""
    if template.native:
        for prop, delta in biomes.trait_bias(biomes.plant_traits(template.key)).items():
            props[prop] = max(0.0, min(10.0, props.get(prop, 0.0) + delta))


def _make_flower(rng: random.Random, namer: Namer, template: FloraTemplate, index: int, color: RGB, sprite) -> PlantSpecies:
    """A flower species: a named plant that does not block, and the bloom it bears (an item named after it)."""
    name = namer.organism(f"flora:{template.key}:{index}", (rng.choice(FORMS.get(template.key, ("flower",))),), color, {}, "flower")
    noun = rng.choice(BLOOM_NOUNS)
    label = namer.fruit_of(f"bloom:{template.key}:{index}", name, (noun,)) if namer.culture == "human" and name.modifier \
        else namer.fruit(f"bloom:{template.key}:{index}", color, "bloom")
    toxic = rng.random() < 0.2
    bloom = ItemKind(None, "Consumable", species=label, sprite=sprite, color=color, shade_sigma=8,
                     hunger_amount=rng.choice((2, 3, 4)), thirst_amount=rng.choice((0, 1, 2)), toxicity=rng.randint(6, 14) if toxic else 0,
                     parent_key=f"planet:flora:{template.key}:{index}", bloom=True)
    return PlantSpecies(
        f"planet:flora:{template.key}:{index}", name.text, PlantCategory.FLOWER, sprite=sprite, corpse_sprite=(3, 9), color=color, fruit=bloom,
        max_hp=template.max_hp, growth_cycle=template.growth_cycle, inventory_capacity=2, blocks_movement=False, blocks_sight=False,
        render_order=RenderOrder.SHRUB, habitat=template.habitat, rarity=template.rarity,
    )


_FRUIT_SPRITES = ((3, 21), (4, 21), (6, 21), (8, 21), (12, 21), (13, 21), (15, 21), (18, 21), (19, 21), (24, 21), (16, 21), (22, 21))


def _make_fruit(rng: random.Random, namer: Namer, template: FloraTemplate, index: int, plant_color: RGB, parent: "Name", form: str) -> Optional[ItemKind]:
    """The fruit a plant bears: a kind that suits its form (an oak: acorns), named after its parent ("scarlet acorn")."""
    options = FORM_FRUITS.get(form)
    if not options:       # an unlisted form: any fruit sprite, with the names its picture suggests
        from components.names import fruit_pos_names
        sprite = rng.choice(_FRUIT_SPRITES)
        options = ((sprite, rng.choice(fruit_pos_names.get(sprite, ["fruit"]))),)
    sprite, shape_word = rng.choice(options)
    # a fruit keeps its parent's colour family, lighter or deeper (so the name's colour word is true)
    fruit_color = tuple(max(30, min(255, int(c * rng.uniform(0.85, 1.25)) + rng.randint(-12, 30))) for c in plant_color)
    toxic = rng.random() < 0.25 and template.key != "crop"     # (a crop is bred to be safe)
    if shape_word in ("rot spore", "blight spore") or template.name_family == "fungus" and template.key == "rot_cap":
        toxic = True        # something called a rot spore is never wholesome
    if namer.culture == "human" and parent.modifier:
        label = namer.fruit_of(f"fruit:{template.key}:{index}", parent, (shape_word,))
    else:
        label = namer.fruit(f"fruit:{template.key}:{index}", fruit_color, shape_word)
    return ItemKind(None, "Consumable", species=label, sprite=sprite, color=fruit_color, shade_sigma=10,
                    hunger_amount=rng.choice((8, 10, 12)), thirst_amount=rng.choice((6, 10, 14)), toxicity=rng.randint(8, 20) if toxic else 0,
                    parent_key=f"planet:flora:{template.key}:{index}")


def _make_fauna(rng: random.Random, namer: Namer, add, template: FaunaTemplate) -> UnitSpecies:
    color = tuple(rng.randint(70, 230) for _ in range(3))
    if template.tint:
        color = tuple(round(c * 0.35 + t * 0.65) for c, t in zip(color, template.tint))
    ranges = COVERING_RANGES[template.hide_kind]
    family = Family.HIDE
    props = _roll(rng, ranges)
    if template.hide_kind == "fur" and rng.random() < 0.3:
        _, notable = rng.choice(FUR_NOTABLE)
        props.update(_roll(rng, notable))
    for prop, delta in biomes.trait_bias(template.traits).items():
        props[prop] = max(0.0, min(10.0, props.get(prop, 0.0) + delta))
    forms = FAUNA_FORMS.get(template.base or template.key)
    if forms:       # named for what the picture shows ("sage cat"), not for a family word that may not fit the sprite
        name = namer.creature(f"fauna:{template.key}", template.base or template.key, forms, color, props, template.name_family,
                              hostile=template.ai is AIKind.HOSTILE)
    else:
        name = namer.name(f"fauna:{template.key}", template.name_family, color, props)
    fuel = {}
    if props.get("combustibility", 0) > 0 and props.get("flammability", 0) > 0:
        fuel = dict(burn_yield=round(5 + props["combustibility"] * 3, 1), burn_duration=max(1, int(props["combustibility"] // 2)))
    import species as defs
    noun = defs.COVERINGS[template.hide_kind][1]
    hide = add(Material(f"hide:{template.key}", f"{name.text} {noun}", family, color, **props, **fuel))
    return UnitSpecies(
        f"planet:fauna:{template.key}", name.text, sprite=spriteconfig.get(f"fauna.{template.base or template.key}", template.sprite),
        corpse_sprite=spriteconfig.get(f"fauna.{template.base or template.key}.corpse", template.corpse_sprite), mirror=True, color=color,
        shade_sigma=12, max_hp=template.max_hp, power=template.power, defense=template.defense, radius=template.radius,
        level_up_base=100, xp_given=template.xp, ai=template.ai, diet=template.diet, leather=False, damage_type=template.damage_type,
        habitat=None if template.underground else template.habitat, hide=hide, grants=grants(*template.grants), rarity=template.rarity, covering=template.hide_kind,
    )
