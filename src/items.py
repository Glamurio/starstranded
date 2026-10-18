"""Items made of planet materials.

Everything you gather is a `Stuff`: one piece of one `Material` (a particular wood, stone, ore, fibre ...). Everything you
make from pieces is a `Composite` (`Made`, `Gear`, `Placed`, `BuiltPiece`): it remembers which material filled which *role*
(head, handle, binding ...), derives its own properties from them by the recipe's rules (`materials.derive_properties`),
and takes its colour and name from them. The numbers a tool or weapon works with (`power_bonus`, `defense_bonus`, tool
capabilities, structure hit points) are computed here from those properties, never stored in the item definition.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

import capabilities
import materials
from components.equippable import Equippable
from damage import DamageType
from entity import Constructable, Item
import exceptions
import species as defs
from materials import Material

EDGED = (DamageType.SHARP, DamageType.PIERCE)
DULL_FACTOR = 0.75
"""A freshly assembled edged tool is dull: it hits at this fraction of its strength until sharpened."""

HARD_STONE = 7.0
"""A stone at least this hard strikes sparks (flint): it lets you light fires."""
ABRASIVE = 5.0
"""A stone at least this abrasive sharpens edges (a whetstone)."""

DEFAULT_WOOD = Material(
    "wood:generic", "wood", materials.Family.WOOD, (140, 100, 60), hardness=4, toughness=5, tenacity=4, density=4, elasticity=4,
    insulation=4, thermal_conductivity=2, flammability=6, combustibility=6, burn_yield=40.0, burn_duration=8)
"""What a branch from an old-style procedural tree (which has no material of its own) is made of."""
DEFAULT_LEATHER = Material(
    "hide:generic", "leather", materials.Family.HIDE, (160, 106, 58), hardness=2, toughness=5, tenacity=6, density=3,
    elasticity=3, insulation=5, thermal_conductivity=2, flammability=5, combustibility=3, burn_yield=20.0, burn_duration=5)


def noun_title(name: str, noun: str) -> str:
    """"Rustore ore" is just "Rustore ore"; "Dunstone" + "Stone" is "Dunstone"."""
    if name.lower().endswith(noun.lower()):
        return name[0].upper() + name[1:]
    return f"{name[0].upper() + name[1:]} {noun.lower()}"


class Stuff(Item):
    """One piece of one material. `form` (the item kind's noun) says what shape it is in; `substance` what it is."""

    def __init__(self, kind: defs.ItemKind, substance: Material, parent=None):
        Item.__init__(self, kind)
        self.parent = parent
        self.substance: Material = substance
        self.material = substance.name
        self.color = self.shade = substance.color

    @property
    def form(self) -> str:
        return self.kind.object_type

    @property
    def tags(self) -> Tuple[str, ...]:
        """Capabilities a unit gets from carrying this piece (a hard stone strikes sparks, a rough one sharpens)."""
        found = []
        if self.form == "Stone" and self.substance.hardness >= HARD_STONE:
            found.append("firestarting")
        if self.form in ("Stone", "Sand") and self.substance.abrasivity >= ABRASIVE:
            found.append("sharpening")
        return tuple(found)

    def activate(self, user) -> None:
        raise exceptions.Impossible(f"{self.get_title()} is a crafting material: build something with it ('R').")

    def get_title(self, exclude_attributes: bool = False) -> str:
        return noun_title(self.substance.name, self.form)


class Composite:
    """Mixin for things assembled from parts: remembers the parts, derives properties, colour and name from them."""

    parts: Dict[str, Material]
    quality: float
    props: Dict[str, float]
    recipe_key: str

    def init_composite(self, parts: Dict[str, Material], quality: float, recipe_key: str,
                       rules: Optional[dict] = None, weights: Optional[dict] = None, designation: str = "head") -> None:
        self.parts = dict(parts)
        self.quality = quality
        self.recipe_key = recipe_key
        self.designation_role = designation if designation in parts else next(iter(parts))
        self.props = materials.derive_properties(parts, rules or {}, quality)
        colors = weights or {role: 1.0 for role in parts}
        self.color = self.shade = materials.blend_colors(parts, {r: w for r, w in colors.items() if r in parts})
        self.material = self.parts[self.designation_role].name

    @property
    def designation(self) -> Material:
        return self.parts[self.designation_role]

    def describe_parts(self) -> str:
        return ", ".join(f"{role}: {m.name}" for role, m in self.parts.items())


class Made(Composite, Item):
    """A crafted thing that is carried (a circuit board, a power cell, a medkit)."""

    def __init__(self, kind: defs.ItemKind, parts, quality: float, recipe_key: str, rules=None, weights=None,
                 designation: str = "head", parent=None):
        Item.__init__(self, kind)
        self.parent = parent
        self.init_composite(parts, quality, recipe_key, rules, weights, designation)

    @property
    def tool_tags(self) -> Tuple[str, ...]:
        return self.kind.tool_tags

    def activate(self, user) -> None:
        if self.kind is defs.MEDKIT:
            from actions import UseMedkitAction
            return UseMedkitAction(user, self)
        raise exceptions.Impossible(f"{self.get_title()} is a component; it is used by what it is built into.")


class Gear(Composite, Equippable):
    """A tool, weapon or piece of armour: its strength follows its parts."""

    def __init__(self, kind: defs.ItemKind, parts, quality: float, recipe_key: str, rules=None, weights=None,
                 designation: str = "head", parent=None):
        Equippable.__init__(self, kind, parent)
        self.init_composite(parts, quality, recipe_key, rules, weights, designation)
        self.dull = self.damage_type in EDGED
        if self.dull:
            self.add_attribute("dull")

    def delivery(self) -> float:
        """How well this weapon delivers its damage type: 1.0 for an ordinary (property 5) head."""
        if self.damage_type is None:
            return 1.0
        keys = materials.DAMAGE_PROPERTIES[self.damage_type][1]
        return sum(self.props.get(k, 0.0) for k in keys) / 2 / materials.REFERENCE

    @property
    def power_bonus(self) -> int:
        if self.kind.equipment_type is defs.EquipmentType.ARMOR:
            return 0
        value = self.kind.base_power * max(0.5, min(2.2, self.delivery()))
        if self.dull:
            value *= DULL_FACTOR
        return max(1, round(value))

    @property
    def defense_bonus(self) -> int:
        if self.kind.equipment_type is not defs.EquipmentType.ARMOR:
            return 0
        return max(1, round((self.props.get("toughness", 0) + self.props.get("tenacity", 0)) / 5))

    @property
    def insulation(self) -> float:
        return self.props.get("insulation", 0.0) if self.kind.equipment_type is defs.EquipmentType.ARMOR else 0.0

    @property
    def tool_tags(self) -> Tuple[str, ...]:
        return self.kind.tool_tags

    def sharpen(self) -> None:
        self.dull = False
        self.remove_attribute("dull")


class Placed(Composite, Constructable):
    """A crafted thing that is put down on the map (a workbench, a furnace, a bed)."""

    def __init__(self, kind: defs.ItemKind, parts, quality: float, recipe_key: str, rules=None, weights=None,
                 designation: str = "head", parent=None):
        Constructable.__init__(self, kind)
        self.parent = parent
        self.init_composite(parts, quality, recipe_key, rules, weights, designation)

    @property
    def station(self) -> Optional[str]:
        return self.kind.station if self.is_placed else None

    @property
    def comfort(self) -> float:
        """How well a bed insulates its sleeper (sleep keeps you warmer on a good bed)."""
        return self.props.get("insulation", 0.0)


def carried_tags(unit) -> Iterable[str]:
    """Tool and material capabilities from everything `unit` carries."""
    for item in unit.inventory.items:
        yield from getattr(item, "tags", ())
        yield from getattr(item, "tool_tags", ())
        if isinstance(item, Equippable):
            yield from item.kind.tool_tags


def station_tags(unit, radius: int = 2) -> Iterable[str]:
    """Capabilities provided by placed stations within `radius` of `unit` (a workbench, a furnace)."""
    world = unit.game_map
    if world is None:
        return
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            for thing in world.get_entities_at_location(unit.x + dx, unit.y + dy):
                station = getattr(thing, "station", None)
                if station:
                    yield station


class Ammo(Item):
    """A stack of pistol rounds (one inventory slot): firing uses one."""

    def __init__(self, parent=None, rounds: int = 12):
        Item.__init__(self, defs.AMMO)
        self.parent = parent
        self.rounds = rounds

    def get_title(self, exclude_attributes: bool = False) -> str:
        return f"{self.kind.object_type} ({self.rounds})"

    def activate(self, user) -> None:
        raise exceptions.Impossible("Rounds are loaded by firing the pistol ('V').")
