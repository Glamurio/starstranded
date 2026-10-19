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
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import spriteconfig
import numpy as np  # type: ignore

import biomes
import namegen
from capabilities import Grant, grants
from damage import DamageType
from ecology import Habitat, suitability
from materials import Family, Material
from naming import Namer, hue_name
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


_FERTILE = (0.4, 1.0)
FLORA_TEMPLATES: Tuple[FloraTemplate, ...] = (
    FloraTemplate("broadleaf", PlantCategory.TREE, ((0, 8), (1, 8)), Habitat((-0.3, 0.6), (0.0, 1.0), fertility=_FERTILE), variants=2, rarity=1.5),
    FloraTemplate("acacia", PlantCategory.TREE, ((2, 8),), Habitat((0.2, 0.9), (-0.45, 0.3)), rarity=1.0, wood_bias=(("hardness", 1.0), ("elasticity", 1.0))),
    FloraTemplate("willow", PlantCategory.TREE, ((2, 8),), Habitat((-0.1, 0.8), (0.1, 1.0), water=(0.4, 1.0)), rarity=1.2, wood_bias=(("elasticity", 2.5),)),
    FloraTemplate("conifer", PlantCategory.TREE, ((3, 8),), Habitat((-0.9, 0.1), (-0.3, 1.0), fertility=(0.1, 1.0)), variants=2, rarity=1.6, color_range=((20, 70, 40), (70, 120, 80)),
                  wood_bias=(("flammability", 1.5), ("combustibility", 1.0), ("insulation", 1.0))),
    FloraTemplate("cypress", PlantCategory.TREE, ((4, 8),), Habitat((0.1, 0.9), (0.2, 1.0), water=(0.2, 1.0)), rarity=1.0, wood_bias=(("toughness", 1.0),)),
    FloraTemplate("palm", PlantCategory.TREE, ((5, 8),), Habitat((0.3, 1.0), (-0.6, 0.6), water=(0.3, 1.0)), rarity=0.8, wood_bias=(("elasticity", 2.0), ("hardness", -1.5))),
    FloraTemplate("fungal_tree", PlantCategory.TREE, ((101, 0),), Habitat((-0.5, 0.8), (0.2, 1.0), light=(0.0, 1.0), substrate=("fungal", "swamp", "bog")), rarity=2.0,
                  color_range=((120, 70, 120), (220, 160, 200)), fruit_chance=0.4, max_hp=14, growth_cycle=8,
                  wood_bias=(("insulation", 2.5), ("toughness", -2.5), ("hardness", -2.0), ("density", -2.0)), name_family="fungus"),
    FloraTemplate("cactus", PlantCategory.TREE, ((102, 0), (103, 0)), Habitat((0.3, 1.0), (-1.0, -0.1)), rarity=1.2, color_range=((40, 120, 60), (100, 170, 90)),
                  fruit_chance=0.5, max_hp=18, wood_bias=(("toughness", -2.0), ("hardness", -2.0), ("tenacity", 1.0)), name_family="shrub"),
    FloraTemplate("reeds", PlantCategory.SHRUB, ((6, 9),), Habitat((-0.3, 1.0), (0.0, 1.0), water=(0.6, 1.0)), variants=1, rarity=2.0, fruit_chance=0.3, max_hp=6, growth_cycle=5, name_family="grass",
                  color_range=((100, 140, 60), (170, 190, 100))),
    FloraTemplate("bush", PlantCategory.SHRUB, ((105, 0),), Habitat((-0.5, 0.8), (-0.4, 1.0), fertility=(0.2, 1.0)), variants=2, rarity=2.0, max_hp=8, growth_cycle=5, name_family="shrub"),
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


FAUNA_TEMPLATES: Tuple[FaunaTemplate, ...] = (
    FaunaTemplate("hopper", (3, 20), Habitat((-0.6, 0.8), (-0.4, 0.9), fertility=(0.15, 1.0)), Diet.HERBIVORE, AIKind.PASSIVE, 1, 3, rarity=3.0, name_family="small_herbivore", xp=10),
    FaunaTemplate("grazer", (4, 18), Habitat((-0.5, 0.7), (-0.35, 0.5), fertility=(0.25, 1.0)), Diet.HERBIVORE, AIKind.PASSIVE, 8, 2, rarity=1.6, name_family="grazer", xp=25),
    FaunaTemplate("strider", (5, 18), Habitat((0.0, 0.9), (-0.5, 0.2)), Diet.HERBIVORE, AIKind.PASSIVE, 11, 3, rarity=1.0, name_family="grazer", xp=30),
    FaunaTemplate("rooter", (2, 20), Habitat((-0.4, 0.8), (0.0, 1.0), fertility=(0.4, 1.0)), Diet.OMNIVORE, AIKind.HOSTILE, 10, 3, rarity=1.0, name_family="animal", xp=35, hide_kind="skin"),
    FaunaTemplate("hunter", (10, 20), Habitat((-0.9, 0.5), (-0.5, 1.0), fertility=(0.1, 1.0)), Diet.CARNIVORE, AIKind.HOSTILE, 9, 3, rarity=0.9, name_family="predator", damage_type=DamageType.SHARP, xp=40),
    FaunaTemplate("stalker", (0, 18), Habitat((-0.3, 1.0), (0.1, 1.0), fertility=(0.4, 1.0)), Diet.CARNIVORE, AIKind.HOSTILE, 10, 4, rarity=0.6, name_family="predator", damage_type=DamageType.SHARP, xp=50),
    FaunaTemplate("scuttler", (7, 18), Habitat((-0.2, 1.0), (0.1, 1.0), water=(0.4, 1.0)), Diet.HERBIVORE, AIKind.PASSIVE, 6, 2, defense=1, rarity=1.5, name_family="crawler", xp=20, hide_kind="chitin"),
    FaunaTemplate("webspinner", (2, 19), Habitat((0.0, 1.0), (-0.5, 1.0), fertility=(0.0, 0.8)), Diet.CARNIVORE, AIKind.HOSTILE, 5, 3, rarity=0.8, name_family="crawler", damage_type=DamageType.PIERCE, xp=25, hide_kind="chitin"),
    FaunaTemplate("serpent", (2, 18), Habitat((0.2, 1.0), (-0.8, 0.5)), Diet.CARNIVORE, AIKind.HOSTILE, 6, 3, rarity=0.9, name_family="serpent", damage_type=DamageType.PIERCE, xp=30, hide_kind="scale"),
    FaunaTemplate("flitter", (5, 20), Habitat((-0.7, 1.0), (-0.6, 1.0)), Diet.HERBIVORE, AIKind.PASSIVE, 2, 1, rarity=1.5, name_family="bird", xp=10, hide_kind="feather"),
)

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
        by_arch = dict(self.stone_ids)
        mats = dict(self.materials)
        keys = list(biomes.BIOMES[biome_key].stones) + list(SURFACE_EXTRAS)
        return [mats[i] for k in keys for i in by_arch.get(k, ())]

    def species_weights(self, env: Mapping[str, object], category: Optional[PlantCategory] = None) -> Tuple[List[PlantSpecies], np.ndarray]:
        """Flora of the given category with their spawn weight for each tile of `env` (arrays): shape (n_species, *tile_shape)."""
        pool = [s for s in self.flora if (category is None and s.category is not PlantCategory.FLOWER) or s.category is category]
        weights = np.stack([suitability(s.habitat, env) * s.rarity for s in pool]) if pool else np.zeros((0,))
        return pool, weights

    def fauna_weights(self, env: Mapping[str, object]) -> Tuple[List[UnitSpecies], np.ndarray]:
        pool = list(self.fauna)
        weights = np.stack([suitability(s.habitat, env) * s.rarity for s in pool]) if pool else np.zeros((0,))
        return pool, weights


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
    for template in FAUNA_TEMPLATES:
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
    color = tuple(rng.randint(lo[i], hi[i]) for i in range(3))
    if template.key != "fungal_tree":
        color = _shift_hue(color, hue_shift + rng.uniform(-0.04, 0.04))
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
        family, key = "wood", f"wood:{template.key}:{index}"
        fam_enum = Family.WOOD
        fuel = dict(burn_yield=round(20 + props["combustibility"] * 5, 1), burn_duration=max(2, int(props["combustibility"] * 1.4)))
    else:
        ranges = dict(hardness=(1, 3), toughness=(2, 4), tenacity=(5, 8), density=(1, 3), elasticity=(2, 6), insulation=(2, 4),
                      flammability=(6, 8), combustibility=(2, 4.5))
        props = _roll(rng, ranges)
        family, key = "fiber", f"fiber:{template.key}:{index}"
        fam_enum = Family.FIBER
        fuel = dict(burn_yield=round(4 + props["combustibility"] * 2, 1), burn_duration=2)
    name = namer.name(f"flora:{template.key}:{index}", template.name_family if template.name_family in ("fungus", "grass", "shrub") else family,
                      color, props)
    material = add(Material(key, name.text, fam_enum, color, **props, **fuel))
    fruit = None
    if rng.random() < template.fruit_chance:
        fruit = _make_fruit(rng, namer, template, index, color)
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


def _make_flower(rng: random.Random, namer: Namer, template: FloraTemplate, index: int, color: RGB, sprite) -> PlantSpecies:
    """A flower species: a named plant that does not block, and the bloom it bears (an item named after it)."""
    name = namer.name(f"flora:{template.key}:{index}", "flower", color, {})
    label = namer.fruit(f"bloom:{template.key}:{index}", color, "bloom")
    toxic = rng.random() < 0.2
    bloom = ItemKind(None, "Consumable", species=label, sprite=sprite, color=color, shade_sigma=8,
                     hunger_amount=rng.choice((2, 3, 4)), thirst_amount=rng.choice((0, 1, 2)), toxicity=rng.randint(6, 14) if toxic else 0)
    return PlantSpecies(
        f"planet:flora:{template.key}:{index}", name.text, PlantCategory.FLOWER, sprite=sprite, corpse_sprite=(3, 9), color=color, fruit=bloom,
        max_hp=template.max_hp, growth_cycle=template.growth_cycle, inventory_capacity=2, blocks_movement=False, blocks_sight=False,
        render_order=RenderOrder.SHRUB, habitat=template.habitat, rarity=template.rarity,
    )


_FRUIT_SPRITES = ((3, 21), (4, 21), (6, 21), (8, 21), (12, 21), (13, 21), (15, 21), (18, 21), (19, 21), (24, 21), (16, 21), (22, 21))


def _make_fruit(rng: random.Random, namer: Namer, template: FloraTemplate, index: int, plant_color: RGB) -> ItemKind:
    from components.names import fruit_pos_names
    fruit_color = tuple(max(30, min(255, int(c * rng.uniform(0.5, 1.6)) + rng.randint(-40, 80))) for c in plant_color)
    sprite = rng.choice(_FRUIT_SPRITES)
    nouns = fruit_pos_names.get(sprite, ["fruit"])
    toxic = rng.random() < 0.25
    shape_word = rng.choice(nouns)  # always drawn: the world must not depend on the naming culture
    label = namer.fruit(f"fruit:{template.key}:{index}", fruit_color, shape_word)
    return ItemKind(None, "Consumable", species=label, sprite=sprite, color=fruit_color, shade_sigma=10,
                    hunger_amount=rng.choice((8, 10, 12)), thirst_amount=rng.choice((6, 10, 14)), toxicity=rng.randint(8, 20) if toxic else 0)


def _make_fauna(rng: random.Random, namer: Namer, add, template: FaunaTemplate) -> UnitSpecies:
    color = tuple(rng.randint(70, 230) for _ in range(3))
    ranges = COVERING_RANGES[template.hide_kind]
    family = Family.HIDE
    props = _roll(rng, ranges)
    if template.hide_kind == "fur" and rng.random() < 0.3:
        _, notable = rng.choice(FUR_NOTABLE)
        props.update(_roll(rng, notable))
    name = namer.name(f"fauna:{template.key}", template.name_family, color, props)
    fuel = {}
    if props.get("combustibility", 0) > 0 and props.get("flammability", 0) > 0:
        fuel = dict(burn_yield=round(5 + props["combustibility"] * 3, 1), burn_duration=max(1, int(props["combustibility"] // 2)))
    import species as defs
    noun = defs.COVERINGS[template.hide_kind][1]
    hide = add(Material(f"hide:{template.key}", f"{name.text} {noun}", family, color, **props, **fuel))
    return UnitSpecies(
        f"planet:fauna:{template.key}", name.text, sprite=spriteconfig.get(f"fauna.{template.key}", template.sprite),
        corpse_sprite=spriteconfig.get(f"fauna.{template.key}.corpse", template.corpse_sprite), mirror=True, color=color,
        shade_sigma=12, max_hp=template.max_hp, power=template.power, defense=template.defense, radius=template.radius,
        level_up_base=100, xp_given=template.xp, ai=template.ai, diet=template.diet, leather=False, damage_type=template.damage_type,
        habitat=template.habitat, hide=hide, grants=grants(*template.grants), rarity=template.rarity, covering=template.hide_kind,
    )
