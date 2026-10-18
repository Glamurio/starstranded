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
from atlas import COLUMNS as SHEET_COLUMNS
from damage import DamageType, Resistances
from equipment_types import EquipmentType
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
    damage_type: DamageType = DamageType.BLUNT  # natural attack
    resistances: Resistances = ()
    name_origin: Optional[str] = None  # namegen set for auto-generated names
    default_name: Optional[str] = None
    render_order: RenderOrder = RenderOrder.UNIT


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


Definition = Union[ItemKind, UnitSpecies, PlantSpecies]

ITEM_KINDS: Dict[str, ItemKind] = {}
UNIT_SPECIES: Dict[str, UnitSpecies] = {}
_REGISTRIES = {"ItemKind": ITEM_KINDS, "UnitSpecies": UNIT_SPECIES, "PlantSpecies": {}}


def register(definition):
    registry = _REGISTRIES[type(definition).__name__]
    assert definition.key not in registry, f"duplicate key {definition.key!r}"
    registry[definition.key] = definition
    return definition


# ── Units ────────────────────────────────────────────────────────────────────────
HUMAN = register(UnitSpecies(
    "human", "Human", sprite=(0, 9), corpse_sprite=(24, 11), color=(255, 255, 255), shade_sigma=None,
    max_hp=30, power=2, defense=1, level_up_base=100, xp_given=50, ai=AIKind.HOSTILE, default_name="Ardan",
))
SELENITE = register(UnitSpecies(
    "selenite", "Selenite", sprite=(2, 37), corpse_sprite=(44, 11), color=color.light_blue,
    max_hp=10, power=3, defense=0, level_up_base=100, xp_given=35, ai=AIKind.HOSTILE, name_origin="selenite",
    damage_type=DamageType.SHARP, diet=Diet.CARNIVORE,
))
RABBIT = register(UnitSpecies(
    "rabbit", "Rabbit", sprite=(3, 15), corpse_sprite=(44, 11), color=None,
    max_hp=1, power=3, defense=0, level_up_base=100, xp_given=35, ai=AIKind.PASSIVE, diet=Diet.HERBIVORE,
))

# ── Items ────────────────────────────────────────────────────────────────────────
MEAT = register(ItemKind("meat", "Meat", sprite=(1, 16), color=color.red, hunger_amount=10, thirst_amount=15))
BRANCH = register(ItemKind("branch", "Branch", sprite=(15, 5), shade_sigma=10))
DAGGER = register(ItemKind("dagger", "Dagger", sprite=(44, 21), color=(0, 191, 255), material="Bronze",
                           equipment_type=EquipmentType.WEAPON, power_bonus=2, damage_type=DamageType.SHARP))
AXE = register(ItemKind("axe", "Axe", sprite=(41, 21), color=(0x8B, 0x6B, 0x3D), material="Wooden",
                        equipment_type=EquipmentType.WEAPON, power_bonus=4, damage_type=DamageType.SHARP))
LEATHER_ARMOR = register(ItemKind("leather_armor", "Armor", sprite=(31, 23), color=color.brown, material="Leather",
                                  equipment_type=EquipmentType.ARMOR, defense_bonus=1))
WOODEN_SPEAR = register(ItemKind("wooden_spear", "Spear", sprite=(45, 21), color=(0x8B, 0x6B, 0x3D), material="Wooden",
                                 equipment_type=EquipmentType.WEAPON, power_bonus=3, damage_type=DamageType.PIERCE))
CAMPFIRE = register(ItemKind("campfire", "Campfire", species="Campfire", sprite=(7, 29), color=color.white,
                             lit_color=color.orange, light_radius=8))
WOODEN_FLOOR = register(ItemKind("wooden_floor", "Wooden floor", sprite=(3, 2), color=(150, 105, 60)))
WOODEN_STAIRS = register(ItemKind("wooden_stairs", "Wooden stairs", sprite=(12, 0), color=(150, 105, 60)))


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


# Wood is cut, not bashed or poked: only sharp tools fell a tree quickly.
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
        return PlantSpecies(f"proc:tree:{name}", name, category, sprite=sprite, corpse_sprite=(13, 5), color=plant_color,
                            fruit=fruit, max_hp=30, growth_cycle=10, blocks_movement=True, blocks_sight=True,
                            render_order=RenderOrder.TREE, resistances=TREE_RESISTANCES)
    return PlantSpecies(f"proc:shrub:{name}", name, category, sprite=sprite, corpse_sprite=(14, 4), color=plant_color,
                        fruit=fruit, max_hp=8, growth_cycle=5, blocks_movement=False, blocks_sight=False,
                        render_order=RenderOrder.SHRUB, resistances=SHRUB_RESISTANCES)


def _random_color(rng: random.Random, threshold: int = 30) -> RGB:
    """`utilities.get_random_color` but driven by `rng`."""
    return (int(max(255 * rng.random(), threshold)), int(max(255 * rng.random(), threshold)),
            int(max(255 * rng.random(), threshold)))
