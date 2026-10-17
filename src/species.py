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
from typing import Dict, NamedTuple, Optional, Tuple, Union

import color
from equipment_types import EquipmentType
from render_order import RenderOrder

RGB = Tuple[int, int, int]
Sprite = Tuple[int, int]  # (column, row) on the Urizen sheet


class AIKind(Enum):
    NONE = auto()
    PASSIVE = auto()
    HOSTILE = auto()


class PlantCategory(Enum):
    TREE = auto()
    SHRUB = auto()


def _lookup(kind_name: str, key: str):
    return _REGISTRIES[kind_name][key]


class _Definition:
    """Mixin: registered definitions pickle as a registry lookup (identity preserved across save/load)."""

    key: Optional[str]

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
    glyph: Optional[str] = None  # text glyph for items without a sprite (e.g. "!")
    color: RGB = color.white
    shade_sigma: Optional[float] = None  # None: shade is white (the old default for items)
    material: Optional[str] = None
    render_order: RenderOrder = RenderOrder.ITEM
    blocks_movement: bool = False
    blocks_sight: bool = False
    hunger_amount: int = 0
    thirst_amount: int = 0
    heal_amount: int = 0
    equipment_type: Optional[EquipmentType] = None
    power_bonus: int = 0
    defense_bonus: int = 0
    light_radius: int = 0
    lit_color: Optional[RGB] = None
    # parameters of the (unspawned) scroll-like consumables
    damage: int = 0
    radius: int = 0
    max_range: int = 0
    turns: int = 0


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
))
RABBIT = register(UnitSpecies(
    "rabbit", "Rabbit", sprite=(3, 15), corpse_sprite=(44, 11), color=None,
    max_hp=1, power=3, defense=0, level_up_base=100, xp_given=35, ai=AIKind.PASSIVE,
))

# ── Items ────────────────────────────────────────────────────────────────────────
HEALTH_POTION = register(ItemKind("health_potion", "Health Potion", glyph="!", color=(127, 0, 255), heal_amount=4))
MEAT = register(ItemKind("meat", "Meat", sprite=(1, 16), color=color.red, hunger_amount=10))
BRANCH = register(ItemKind("branch", "Branch", sprite=(15, 5), shade_sigma=10))
DAGGER = register(ItemKind("dagger", "Dagger", sprite=(44, 21), color=(0, 191, 255), material="Bronze",
                           equipment_type=EquipmentType.WEAPON, power_bonus=2))
SWORD = register(ItemKind("sword", "Sword", glyph="\\", color=(0, 191, 255), material="Iron",
                          equipment_type=EquipmentType.WEAPON, power_bonus=4))
LEATHER_ARMOR = register(ItemKind("leather_armor", "Armor", sprite=(31, 23), color=color.brown, material="Leather",
                                  equipment_type=EquipmentType.ARMOR, defense_bonus=1))
CHAIN_MAIL = register(ItemKind("chain_mail", "Chain Mail", glyph="]", color=(139, 69, 19), material="Iron",
                               equipment_type=EquipmentType.ARMOR, defense_bonus=3))
WOODEN_SPEAR = register(ItemKind("wooden_spear", "Spear", sprite=(45, 21), color=(0x8B, 0x6B, 0x3D), material="Wooden",
                                 equipment_type=EquipmentType.WEAPON, power_bonus=3))
CAMPFIRE = register(ItemKind("campfire", "Campfire", species="Campfire", sprite=(7, 29), color=color.white,
                             lit_color=color.orange, light_radius=8))
CONFUSION_SCROLL = register(ItemKind("confusion_scroll", "Consumable", glyph="~", color=(207, 63, 255)))
FIREBALL_SCROLL = register(ItemKind("fireball_scroll", "Consumable", glyph="~", color=(255, 0, 0)))
LIGHTNING_SCROLL = register(ItemKind("lightning_scroll", "Consumable", glyph="~", color=(255, 255, 0)))


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
                            fruit=fruit, max_hp=10, growth_cycle=10, blocks_movement=True, blocks_sight=True,
                            render_order=RenderOrder.TREE)
    return PlantSpecies(f"proc:shrub:{name}", name, category, sprite=sprite, corpse_sprite=(14, 4), color=plant_color,
                        fruit=fruit, max_hp=5, growth_cycle=5, blocks_movement=False, blocks_sight=False,
                        render_order=RenderOrder.SHRUB)


def _random_color(rng: random.Random, threshold: int = 30) -> RGB:
    """`utilities.get_random_color` but driven by `rng`."""
    return (int(max(255 * rng.random(), threshold)), int(max(255 * rng.random(), threshold)),
            int(max(255 * rng.random(), threshold)))


# ── Glyphs (tcod-console era; removed in Phase 3) ──────────────────────────────────
class Glyphs(NamedTuple):
    sprite: Union[int, str]
    mirror: Union[int, str]
    corpse: Union[int, str]


_GLYPH_CACHE: Dict[int, Tuple[Definition, Glyphs]] = {}


def glyphs(definition: Definition) -> Glyphs:
    """Codepoints for a definition in the PUA-remapped tileset (or its text glyph).

    Cached by object identity: hashing a frozen dataclass hashes every field, which is too slow per entity per frame.
    The cache holds a reference to the definition, so an id is never reused while its entry exists.
    """
    hit = _GLYPH_CACHE.get(id(definition))
    if hit is not None and hit[0] is definition:
        return hit[1]
    result = _compute_glyphs(definition)
    _GLYPH_CACHE[id(definition)] = (definition, result)
    return result


def _compute_glyphs(definition: Definition) -> Glyphs:
    glyph = getattr(definition, "glyph", None)
    if glyph:
        return Glyphs(glyph, glyph, glyph)
    from utilities import map_codepoints

    corpse = getattr(definition, "corpse_sprite", None)
    mirror = getattr(definition, "mirror", False)
    key = f"{type(definition).__name__}|{definition.sprite}|{corpse}|{mirror}"
    info = map_codepoints(key, definition.sprite, mirror, corpse)
    sprite = info["sprite"]
    return Glyphs(sprite, info.get("mirror", sprite), info.get("corpse", sprite))
