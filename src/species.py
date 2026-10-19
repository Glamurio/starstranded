"""Immutable, shared definitions ("species"/"kinds") for entities, plus their registries.

Instances (`Unit`, `Plant`, `Item` …) hold only per-instance state and a reference to one of these.
Static definitions live in the registries below and pickle *by key*, so every loaded entity points at the
process-wide object. Procedural definitions (plant species, fruit kinds) are created at map generation, are not
registered, and pickle by value (pickle's memo keeps them shared within one save).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional, Tuple, Union

import color
import spriteconfig
from atlas import COLUMNS as SHEET_COLUMNS
from capabilities import Grant, grants
from damage import DamageType, Resistances
from ecology import Habitat
from equipment_types import EquipmentType
from materials import Material
from render_order import RenderOrder

RGB = Tuple[int, int, int]
Sprite = Tuple[int, int]  # (column, row) on the Urizen sheet


class AIKind(Enum):
    NONE = auto()
    PASSIVE = auto()
    HOSTILE = auto()


class Diet(Enum):
    HERBIVORE = auto()  # eats plant food; hunted by meat eaters
    CARNIVORE = auto()  # eats meat; hunts herbivores
    OMNIVORE = auto()   # eats both; hunts herbivores


class PlantCategory(Enum):
    TREE = auto()
    SHRUB = auto()
    FLOWER = auto()      # small ground plants that bear one bloom to pick (see components.plant.Flower)


def _lookup(kind_name: str, key: str):
    return _REGISTRIES[kind_name][key]


class _Definition:
    """Mixin: registered definitions pickle as a registry lookup (identity preserved across save/load)."""

    key: Optional[str]

    @property
    def sprite_id(self) -> Optional[int]:
        """Atlas id of the sprite (None if the definition has none)."""
        sprite = self.sprite  # type: ignore[attr-defined]
        return None if sprite is None else sprite[1] * SHEET_COLUMNS + sprite[0]

    @property
    def corpse_sprite_id(self) -> Optional[int]:
        """Atlas id of the corpse sprite (None for definitions without one)."""
        sprite = getattr(self, "corpse_sprite", None)
        return None if sprite is None else sprite[1] * SHEET_COLUMNS + sprite[0]

    def __reduce_ex__(self, protocol):
        registry = _REGISTRIES.get(type(self).__name__, {})
        if self.key is not None and registry.get(self.key) is self:
            return (_lookup, (type(self).__name__, self.key))
        return super().__reduce_ex__(protocol)


@dataclass(frozen=True)
class ItemKind(_Definition):
    key: Optional[str]
    object_type: str
    species: Optional[str] = None
    sprite: Optional[Sprite] = None
    color: RGB = color.white
    shade_sigma: Optional[float] = None  # None: shade is white (the old default for items)
    material: Optional[str] = None
    render_order: RenderOrder = RenderOrder.ITEM
    blocks_movement: bool = False
    blocks_sight: bool = False
    hunger_amount: int = 0
    thirst_amount: int = 0
    equipment_type: Optional[EquipmentType] = None
    damage_type: Optional[DamageType] = None  # weapons: what they deal (None: the wielder's natural type)
    power_bonus: int = 0
    defense_bonus: int = 0
    light_radius: int = 0
    lit_color: Optional[RGB] = None
    toxicity: int = 0  # turns of poison when eaten (hidden until identified or suffered)
    tool_tags: Tuple[str, ...] = ()  # capabilities held while this tool is carried (see capabilities.py)
    station: Optional[str] = None    # capability a placed copy provides to crafters nearby (workbench, furnace)
    base_power: int = 0              # property-made weapons: power at a delivery rating of 5 (see items.Gear.power_bonus)


@dataclass(frozen=True)
class UnitSpecies(_Definition):
    key: Optional[str]
    name: str
    sprite: Sprite
    corpse_sprite: Sprite
    mirror: bool = True
    color: Optional[RGB] = None  # None: random colour per instance
    shade_sigma: Optional[float] = 20  # None: shade == colour
    max_hp: int = 10
    power: int = 1
    defense: int = 1
    radius: int = 8
    max_hunger: int = 100
    max_thirst: int = 100
    inventory_capacity: int = 10
    level_up_base: int = 0
    xp_given: int = 0
    ai: AIKind = AIKind.NONE
    diet: Diet = Diet.OMNIVORE
    leather: bool = False  # leaves a piece of leather when it dies
    damage_type: DamageType = DamageType.BLUNT  # natural attack
    resistances: Resistances = ()
    name_origin: Optional[str] = None  # namegen set for auto-generated names
    default_name: Optional[str] = None
    render_order: RenderOrder = RenderOrder.UNIT
    habitat: Optional[Habitat] = None  # where it lives (planet species); None: placed by the old spawn tables
    hide: Optional[Material] = None    # what its skin/fur/shell is made of (drops as hide when it dies)
    grants: Tuple[Grant, ...] = ()     # innate tags (see capabilities)
    rarity: float = 1.0                # relative abundance where it can live
    blood_color: RGB = (150, 18, 24)   # what it bleeds when it dies (robots could leave black oil, say)
    blood_name: str = "blood"
    covering: str = "fur"              # what covers its body: fur, feather, chitin, scale or skin (see `COVERINGS`)


@dataclass(frozen=True)
class PlantSpecies(_Definition):
    key: Optional[str]
    name: str
    category: PlantCategory
    sprite: Sprite
    corpse_sprite: Sprite
    color: RGB
    fruit: Optional[ItemKind] = None
    max_hp: int = 10
    resistances: Resistances = ()
    growth_cycle: int = 10
    inventory_capacity: int = 10
    blocks_movement: bool = False
    blocks_sight: bool = False
    render_order: RenderOrder = RenderOrder.TREE
    mirror: bool = True
    habitat: Optional[Habitat] = None
    material: Optional[Material] = None  # what its wood (or stem) is made of
    fiber: Optional[Material] = None     # fibre/vines it yields when cut (shrubs)
    rarity: float = 1.0


Definition = Union[ItemKind, UnitSpecies, PlantSpecies]

ITEM_KINDS: Dict[str, ItemKind] = {}
UNIT_SPECIES: Dict[str, UnitSpecies] = {}
_REGISTRIES = {"ItemKind": ITEM_KINDS, "UnitSpecies": UNIT_SPECIES, "PlantSpecies": {}}


def register(definition):
    kind = type(definition).__name__
    registry = _REGISTRIES[kind]
    if kind in ("ItemKind", "UnitSpecies") and definition.key is not None:
        definition = spriteconfig.registered(definition, "item" if kind == "ItemKind" else "unit")   # data/sprites.json
    assert definition.key not in registry, f"duplicate key {definition.key!r}"
    registry[definition.key] = definition
    return definition


# ── Units ────────────────────────────────────────────────────────────────────────
_RACE_BASE = dict(max_hp=30, power=2, defense=1, level_up_base=100, xp_given=50, ai=AIKind.HOSTILE, inventory_capacity=20)
HUMAN = register(UnitSpecies(
    "human", "Human", sprite=(117, 0), corpse_sprite=(24, 16), color=(255, 255, 255), shade_sigma=None,
    default_name="Ardan", diet=Diet.OMNIVORE,
    grants=grants("improved_crafting", "omnivore", "requires_organic", "night_aversion"), **_RACE_BASE,
))
SELENITE_PEOPLE = register(UnitSpecies(
    "selenite_people", "Selenite", sprite=(118, 1), corpse_sprite=(44, 16), color=(190, 215, 255), shade_sigma=None,
    default_name="Zudaab", diet=Diet.HERBIVORE, damage_type=DamageType.BLUNT,
    grants=grants("increased_plant_yield", "faster_crop_growth", "prolonged_breath_holding", "herbivore", "frail_exoskeleton",
                  "requires_organic"), **dict(_RACE_BASE, max_hp=26),
))
MAU = register(UnitSpecies(
    "mau", "Mau", sprite=(120, 0), corpse_sprite=(44, 16), color=(230, 190, 110), shade_sigma=None,
    default_name="Bastu", diet=Diet.CARNIVORE, damage_type=DamageType.SHARP,
    grants=grants(("increased_agility", 2.0), "darkvision", "carnivore", "clawed", "liquid_averse", "requires_organic"),
    **dict(_RACE_BASE, max_hp=24),
))
PLAYABLE_SPECIES = (HUMAN, SELENITE_PEOPLE, MAU)
SELENITE = register(UnitSpecies(
    "selenite", "Selenite", sprite=(118, 1), corpse_sprite=(44, 16), color=color.light_blue,
    max_hp=10, power=3, defense=0, level_up_base=100, xp_given=35, ai=AIKind.HOSTILE, name_origin="selenite",
    damage_type=DamageType.SHARP, diet=Diet.CARNIVORE,
))

# ── Items ────────────────────────────────────────────────────────────────────────
MEAT = register(ItemKind("meat", "Meat", sprite=(1, 21), color=color.red, hunger_amount=10, thirst_amount=5))
LEATHER = register(ItemKind("leather", "Leather", sprite=(1, 25), color=(0xA0, 0x6A, 0x3A), shade_sigma=8))
FLASK = register(ItemKind("flask", "Flask", sprite=(3, 23), color=(0xB0, 0x78, 0x40), material="Leather"))
BRANCH = register(ItemKind("branch", "Branch", sprite=(108, 0), shade_sigma=10))
DAGGER = register(ItemKind("dagger", "Dagger", sprite=(44, 26), color=(0, 191, 255), material="Bronze",
                           equipment_type=EquipmentType.WEAPON, power_bonus=2, damage_type=DamageType.SHARP))
AXE = register(ItemKind("axe", "Axe", sprite=(26, 28), color=(0x8B, 0x6B, 0x3D), material="Wooden", tool_tags=("chopping",),
                        equipment_type=EquipmentType.WEAPON, power_bonus=4, damage_type=DamageType.SHARP))
LEATHER_ARMOR = register(ItemKind("leather_armor", "Armor", sprite=(25, 30), color=color.brown, material="Leather",
                                  equipment_type=EquipmentType.ARMOR, defense_bonus=1))
CAMPFIRE = register(ItemKind("campfire", "Campfire", species="Campfire", sprite=(0, 42), color=color.white,
                             lit_color=color.orange, light_radius=8))
STUMP = register(ItemKind("stump", "Stump", sprite=(4, 10), color=color.brown, render_order=RenderOrder.CORPSE))
WOODEN_FLOOR = register(ItemKind("wooden_floor", "Wooden floor", sprite=(8, 5), color=(150, 105, 60)))
WOODEN_STAIRS = register(ItemKind("wooden_stairs", "Wooden stairs", sprite=(24, 1), color=(150, 105, 60)))


RATION = register(ItemKind("ration", "Ration pack", sprite=(54, 21), color=(210, 190, 120), hunger_amount=40, thirst_amount=10))
AMMO = register(ItemKind("ammo", "Pistol rounds", sprite=(68, 22), color=(210, 190, 90)))

# ── Material pieces (what the world gives you; each instance carries its own Material, see items.Stuff) ──
def _piece(key, name, sprite, **kw):
    return register(ItemKind(key, name, sprite=sprite, shade_sigma=6, **kw))


PIECE_STONE = _piece("piece_stone", "Stone", (20, 5))
PIECE_ORE = _piece("piece_ore", "Ore", (1, 13))
PIECE_FIBER = _piece("piece_fiber", "Fibre", (2, 27))
PIECE_HIDE = _piece("piece_hide", "Hide", (2, 25))
PIECE_FEATHER = _piece("piece_feather", "Feather", (5, 25))
PIECE_CHITIN = _piece("piece_chitin", "Chitin", (72, 25))
PIECE_SCALE = _piece("piece_scale", "Scale", (4, 22))
PIECE_SAND = _piece("piece_sand", "Sand", (5, 13))
PIECE_CLAY = _piece("piece_clay", "Clay", (14, 5))
PIECE_COAL = _piece("piece_coal", "Coal", (4, 13))
PIECE_INGOT = _piece("piece_ingot", "Ingot", (6, 25))
PIECE_BRICK = _piece("piece_brick", "Brick", (31, 33))
PIECE_GLASS = _piece("piece_glass", "Glass", (2, 24))
PIECE_CORD = _piece("piece_cord", "Cord", (100, 1))
PIECE_WIRE = _piece("piece_wire", "Wire", (55, 9))
PIECE_FORMS = (PIECE_STONE, PIECE_ORE, PIECE_FIBER, PIECE_HIDE, PIECE_FEATHER, PIECE_CHITIN, PIECE_SCALE, PIECE_SAND, PIECE_CLAY, PIECE_COAL, PIECE_INGOT,
               PIECE_BRICK, PIECE_GLASS, PIECE_CORD, PIECE_WIRE)

# What covers an animal's body -> (the piece it leaves, the noun in the material's name). Fur and skin are hides (they make
# leather things); feathers pad, chitin and scales armour and edge. Every covering is good for something (see recipes.py).
COVERINGS = {
    "fur": (PIECE_HIDE, "fur"), "skin": (PIECE_HIDE, "skin"), "feather": (PIECE_FEATHER, "feathers"),
    "chitin": (PIECE_CHITIN, "chitin"), "scale": (PIECE_SCALE, "scales"),
}

# ── Tools, weapons and armour made of parts (power/defence come from the parts' properties) ──
_WOOD = (0x8B, 0x6B, 0x3D)
HATCHET = register(ItemKind("hatchet", "Hatchet", sprite=(27, 28), color=_WOOD, equipment_type=EquipmentType.WEAPON,
                            damage_type=DamageType.SHARP, base_power=3, tool_tags=("chopping", "cutting")))
PICKAXE = register(ItemKind("pickaxe", "Pickaxe", sprite=(1, 31), color=_WOOD, equipment_type=EquipmentType.WEAPON,
                            damage_type=DamageType.PIERCE, base_power=2, tool_tags=("mining",)))
SHOVEL = register(ItemKind("shovel", "Shovel", sprite=(0, 31), color=_WOOD, equipment_type=EquipmentType.WEAPON,
                           damage_type=DamageType.BLUNT, base_power=1, tool_tags=("digging",)))
KNIFE = register(ItemKind("knife", "Knife", sprite=(44, 26), color=_WOOD, equipment_type=EquipmentType.WEAPON,
                          damage_type=DamageType.SHARP, base_power=2, tool_tags=("cutting",)))
CLUB = register(ItemKind("club", "Club", sprite=(27, 27), color=_WOOD, equipment_type=EquipmentType.WEAPON,
                         damage_type=DamageType.BLUNT, base_power=3))
SPEAR = register(ItemKind("spear", "Spear", sprite=(40, 27), color=_WOOD, equipment_type=EquipmentType.WEAPON,
                          damage_type=DamageType.PIERCE, base_power=3))
HAMMER = register(ItemKind("hammer", "Hammer", sprite=(5, 31), color=_WOOD, equipment_type=EquipmentType.WEAPON,
                           damage_type=DamageType.BLUNT, base_power=2, tool_tags=("hammering",)))
HIDE_ARMOR = register(ItemKind("hide_armor", "Armour", sprite=(25, 30), color=color.brown,
                               equipment_type=EquipmentType.ARMOR, base_power=1))
SALVAGE_TOOL = register(ItemKind("salvage_tool", "Salvage tool", sprite=(59, 25), color=(180, 180, 190),
                                 equipment_type=EquipmentType.WEAPON, damage_type=DamageType.PIERCE, base_power=1,
                                 tool_tags=("salvaging", "cutting", "hammering")))
OMNITOOL = register(ItemKind("omnitool", "Omnitool", sprite=(68, 23), color=(140, 200, 240),
                             equipment_type=EquipmentType.WEAPON, damage_type=DamageType.SHARP, base_power=3,
                             tool_tags=("chopping", "mining", "digging", "cutting", "hammering", "salvaging")))
PISTOL = register(ItemKind("pistol", "Pistol", sprite=(50, 22), color=(190, 190, 200), equipment_type=EquipmentType.WEAPON,
                           damage_type=DamageType.PIERCE, base_power=6))
# ── Things made of parts that are not worn or wielded ──
BED = register(ItemKind("bed", "Bed", sprite=(0, 36), color=_WOOD, station="bed"))
WORKBENCH = register(ItemKind("workbench", "Workbench", sprite=(54, 20), color=_WOOD, station="workbench"))
FURNACE = register(ItemKind("furnace", "Furnace", sprite=(28, 38), color=(140, 140, 150), station="furnace"))
TORCH = register(ItemKind("torch", "Torch", sprite=(4, 42), color=color.orange, lit_color=color.orange, light_radius=5))
WALL_BLOCK = register(ItemKind("wall_block", "Wall", sprite=(12, 0), color=(150, 150, 150)))
CIRCUIT = register(ItemKind("circuit", "Circuit board", sprite=(78, 7), color=(80, 200, 120)))
POWER_CELL = register(ItemKind("power_cell", "Power cell", sprite=(52, 9), color=(120, 220, 120)))
HULL_PLATE = register(ItemKind("hull_plate", "Hull plate", sprite=(75, 7), color=(160, 160, 170)))
LENS = register(ItemKind("lens", "Lens", sprite=(61, 9), color=(200, 230, 255)))
MEDKIT = register(ItemKind("medkit", "Medkit", sprite=(58, 9), color=(240, 100, 100)))
SURVEY_KIT = register(ItemKind("survey_kit", "Survey kit", sprite=(62, 26), color=(120, 180, 240), tool_tags=("surveying",)))
ARTIFACT = register(ItemKind("artifact", "Relic", sprite=(57, 26), color=(120, 230, 200)))
BEACON = register(ItemKind("beacon", "Distress beacon", sprite=(52, 19), color=(255, 120, 80)))
# ── places: the crash site and the precursor ruins (see structures.py) ──
SHIP = register(ItemKind("ship", "Crashed shuttle", sprite=(76, 4), color=(190, 190, 205), blocks_movement=True))
WRECKAGE = register(ItemKind("wreckage", "Wreckage", sprite=(19, 6), color=(150, 150, 165), blocks_movement=True))
CARGO_POD = register(ItemKind("cargo_pod", "Cargo pod", sprite=(84, 4), color=(230, 170, 70), blocks_movement=True))
RUIN = register(ItemKind("ruin", "Ruin", sprite=(26, 23), color=(170, 200, 190), blocks_movement=True))
GATE = register(ItemKind("gate", "Precursor gate", sprite=(12, 1), color=(120, 230, 200), blocks_movement=True))
NAV_UNIT = register(ItemKind("nav_unit", "Navigation unit", sprite=(75, 18), color=(120, 160, 240)))


# ── Procedural definitions ───────────────────────────────────────────────────────
def make_fruit_kind(rng: random.Random = random) -> ItemKind:
    """A random fruit (same rules as the old `Fruit()` / `Plant()` constructors)."""
    from components.names import color_names, fruit_pos_names
    from utilities import get_color_group

    fruit_color = _random_color(rng)
    position, shape_names = rng.choice(list(fruit_pos_names.items()))
    name = rng.choice(color_names[get_color_group(fruit_color)]) + rng.choice(shape_names)
    return ItemKind(None, "Consumable", species=name, sprite=position, color=fruit_color, shade_sigma=10,
                    hunger_amount=10, thirst_amount=10)


# Wood is cut, not bashed or poked, only sharp tools fell a tree quickly.
TREE_RESISTANCES: Resistances = ((DamageType.BLUNT, 0.2), (DamageType.SHARP, 1.0), (DamageType.PIERCE, 0.3))
SHRUB_RESISTANCES: Resistances = ((DamageType.BLUNT, 0.5), (DamageType.SHARP, 1.0), (DamageType.PIERCE, 0.5))


def make_plant_species(category: PlantCategory, rng: random.Random = random) -> PlantSpecies:
    """Roll one tree or shrub species (same rules as the old `Tree()`/`Shrub()` constructors: 80 % bear fruit)."""
    from components.names import color_names, shrub_pos_names, tree_pos_names
    from utilities import get_color_group

    fruit = make_fruit_kind(rng) if rng.random() > 0.2 else None
    plant_color = _random_color(rng)
    table = tree_pos_names if category is PlantCategory.TREE else shrub_pos_names
    sprite, shape_names = rng.choice(list(table.items()))
    group = color_names[get_color_group(plant_color)]
    if fruit:
        name = f"{fruit.species} {rng.choice(shape_names)}"
    else:
        name = f"{rng.choice(group)} {rng.choice(shape_names)}"
    if category is PlantCategory.TREE:
        return PlantSpecies(f"proc:tree:{name}", name, category, sprite=sprite, corpse_sprite=(4, 10), color=plant_color,
                            fruit=fruit, max_hp=30, growth_cycle=10, blocks_movement=True, blocks_sight=True,
                            render_order=RenderOrder.TREE, resistances=TREE_RESISTANCES)
    return PlantSpecies(f"proc:shrub:{name}", name, category, sprite=sprite, corpse_sprite=(3, 9), color=plant_color,
                        fruit=fruit, max_hp=8, growth_cycle=5, blocks_movement=False, blocks_sight=False,
                        render_order=RenderOrder.SHRUB, resistances=SHRUB_RESISTANCES)


def _random_color(rng: random.Random, threshold: int = 30) -> RGB:
    """`utilities.get_random_color` but driven by `rng`."""
    return (int(max(255 * rng.random(), threshold)), int(max(255 * rng.random(), threshold)),
            int(max(255 * rng.random(), threshold)))


STUMP_SPRITES = frozenset({(0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8)})
"""Tree sprites (deciduous, evergreen, palm) that leave a stump when felled. Fungi and cacti do not."""
