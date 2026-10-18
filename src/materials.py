"""The material model: physical properties decide what a thing is good for.

Scale: every continuous property is a float on **0-10** (0 = absent, 1 = negligible, 5 = middling, 10 = extreme).
Specialised attributes have their own units (see `Material`). All rules that turn properties into game numbers live
here (thermal behaviour, structural rating, damage interaction, composition), so no other system re-derives them.

Property meanings
-----------------
hardness       resists scratching and indentation; a hard edge cuts, a hard point pierces.
toughness      absorbs impact without breaking (glass: hard but not tough).
tenacity       resists tearing and pulling apart (rope, sinew, wire); what binds things together.
abrasivity     how well it wears other materials down (whetstone, sandpaper).
density        mass per volume: heavy things hit hard, shield well, and need strong supports.
elasticity     springs back after bending (bows, springs, rubber).
insulation     slows the flow of heat; keeps warmth in or out.
electrical_conductivity   carries current (wire, circuits).
thermal_conductivity      carries heat (pots, furnace linings are low).
radioactivity  ionising emission (power source and hazard).
flammability   how *easily* it ignites (lower ignition temperature).
combustibility how *well* it keeps burning and how much energy it gives once burning (fuel quality).
transparency   lets light through (windows, lenses).
incandescence  glows when hot enough (higher = glows at a lower temperature, and brighter).

Flammability and combustibility are separate on purpose: dry grass ignites at once (flammability 9) but is a poor fuel
(combustibility 2) and may only flash; coal is hard to ignite (flammability 4) but burns long and hot (combustibility 9).

Specialised attributes: `burn_yield` (energy units per unit of fuel), `burn_duration` (turns one unit burns),
`is_amorphous` (melts into a glass-like state: transparency rises when it is melted and cooled), `melting_point`
(degrees C reachable by a furnace, 0 = does not melt in reach), `nutrition` is *not* here (food rules live in `survival`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

from damage import DamageType
from skills import Skill

RGB = Tuple[int, int, int]

PROPERTY_KEYS: Tuple[str, ...] = (
    "hardness", "toughness", "tenacity", "abrasivity", "density", "elasticity", "insulation",
    "electrical_conductivity", "thermal_conductivity", "radioactivity", "flammability", "combustibility",
    "transparency", "incandescence",
)

# Which skill reads each property, and how hard it is to read (see knowledge.py).
PROPERTY_READING: Dict[str, Tuple[Skill, int]] = {
    "hardness": (Skill.GEOLOGY, 2), "toughness": (Skill.ENGINEERING, 2), "tenacity": (Skill.ENGINEERING, 3),
    "abrasivity": (Skill.GEOLOGY, 3), "density": (Skill.ENGINEERING, 1), "elasticity": (Skill.ENGINEERING, 2),
    "insulation": (Skill.ENGINEERING, 3), "electrical_conductivity": (Skill.ENGINEERING, 3),
    "thermal_conductivity": (Skill.CHEMISTRY, 3), "radioactivity": (Skill.CHEMISTRY, 2),
    "flammability": (Skill.CHEMISTRY, 2), "combustibility": (Skill.CHEMISTRY, 3),
    "transparency": (Skill.GEOLOGY, 1), "incandescence": (Skill.CHEMISTRY, 4),
}


class Family(Enum):
    WOOD = "wood"
    STONE = "stone"
    METAL = "metal"
    FIBER = "fiber"
    HIDE = "hide"
    BONE = "bone"
    CLAY = "clay"
    SAND = "sand"
    GLASS = "glass"
    CERAMIC = "ceramic"
    CRYSTAL = "crystal"
    FUEL = "fuel"
    ORGANIC = "organic"
    COMPOSITE = "composite"


@dataclass(frozen=True)
class Material:
    """One concrete material of a planet (a particular wood, a particular stone). Frozen and hashable."""

    id: str                       # stable key, e.g. "wood:3"
    name: str                     # the discovered name (naming.py decides it)
    family: Family
    color: RGB
    hardness: float = 0
    toughness: float = 0
    tenacity: float = 0
    abrasivity: float = 0
    density: float = 0
    elasticity: float = 0
    insulation: float = 0
    electrical_conductivity: float = 0
    thermal_conductivity: float = 0
    radioactivity: float = 0
    flammability: float = 0
    combustibility: float = 0
    transparency: float = 0
    incandescence: float = 0
    burn_yield: float = 0.0       # energy units released per unit of fuel
    burn_duration: int = 0        # turns one unit burns
    is_amorphous: bool = False
    melting_point: int = 0        # degrees C; 0 = cannot be melted
    refines_to: str = ""          # id of the material a furnace turns it into (an ore -> its metal)

    def __post_init__(self):
        assert self.id and self.name, "a material needs an id and a name"
        assert all(0 <= c <= 255 for c in self.color) and len(self.color) == 3, f"{self.id}: bad colour"
        for key in PROPERTY_KEYS:
            value = getattr(self, key)
            assert 0 <= value <= 10, f"{self.id}: {key}={value} is outside 0-10"
        assert self.burn_yield >= 0 and self.burn_duration >= 0 and self.melting_point >= 0
        if self.burn_yield > 0:
            assert self.combustibility > 0 and self.burn_duration > 0, f"{self.id}: a fuel needs combustibility and a burn duration"
        if self.is_amorphous:
            assert self.melting_point > 0, f"{self.id}: an amorphous material must be meltable"

    def get(self, prop: str) -> float:
        assert prop in PROPERTY_KEYS, f"unknown property {prop!r}"
        return getattr(self, prop)

    def props(self) -> Dict[str, float]:
        return {k: getattr(self, k) for k in PROPERTY_KEYS}

    def replace(self, **changes) -> "Material":
        values = {f.name: getattr(self, f.name) for f in fields(self)}
        values.update(changes)
        return Material(**values)


def clamp10(value: float) -> float:
    return max(0.0, min(10.0, value))


# ── thermal behaviour ─────────────────────────────────────────────────────────────────────────────────
AMBIENT_OXYGEN = 0.21
FLASH_TURNS = 2
SUSTAIN_MIN_COMBUSTIBILITY = 3


class Burn(Enum):
    NONE = "none"            # too cool, or not flammable at all
    FLASH = "flash"          # ignites and flares for a moment, then dies (can't sustain)
    SUSTAINED = "sustained"  # keeps burning and releases its energy


def ignition_temp(material: Material) -> Optional[float]:
    """Degrees C needed to ignite it; None if it cannot burn. Flammability 10 -> 150, 1 -> 555."""
    if material.flammability <= 0:
        return None
    return 600.0 - 45.0 * material.flammability


def min_oxygen(material: Material) -> float:
    """Oxygen fraction of the air needed to keep it burning (better fuels burn in thinner air)."""
    return 0.08 + 0.015 * (10 - material.combustibility)


def ignite(material: Material, source_temp: float, oxygen: float = AMBIENT_OXYGEN) -> Burn:
    """What happens when a heat source at `source_temp` touches the material in air with `oxygen`."""
    threshold = ignition_temp(material)
    if threshold is None or source_temp < threshold or oxygen < 0.05:
        return Burn.NONE
    sustained = (material.combustibility >= SUSTAIN_MIN_COMBUSTIBILITY and material.burn_yield > 0
                 and oxygen >= min_oxygen(material))
    return Burn.SUSTAINED if sustained else Burn.FLASH


def burn_turns(material: Material, units: int = 1, burn: Burn = Burn.SUSTAINED) -> int:
    """How long `units` of the material burn."""
    if burn is Burn.NONE:
        return 0
    if burn is Burn.FLASH:
        return FLASH_TURNS
    return material.burn_duration * units


def burn_energy(material: Material, units: int = 1, burn: Burn = Burn.SUSTAINED) -> float:
    """Total energy released; a flash releases a tenth of one unit's yield."""
    if burn is Burn.NONE:
        return 0.0
    if burn is Burn.FLASH:
        return material.burn_yield * 0.1
    return material.burn_yield * units


def glow_threshold(material: Material) -> Optional[float]:
    """Degrees C at which it glows (incandescence 10 -> 300, 1 -> 1380); None if it never glows."""
    if material.incandescence <= 0:
        return None
    return 1500.0 - 120.0 * material.incandescence


def glow_radius(material: Material, temp: float) -> int:
    """Light radius (tiles) of the material at `temp`; 0 below its glow threshold."""
    threshold = glow_threshold(material)
    if threshold is None or temp < threshold:
        return 0
    return 1 + int(material.incandescence // 3)


def melt_and_cool(material: Material) -> Material:
    """Melt the material and let it cool: amorphous materials come out glassy (more transparent, harder, more brittle)
    under a new family; others are simply recast (a little purer: tenacity and toughness up by one)."""
    if material.melting_point <= 0:
        raise ValueError(f"{material.name} cannot be melted")
    if material.is_amorphous:
        return material.replace(
            id=material.id + "+melt", family=Family.GLASS, transparency=clamp10(material.transparency + 4),
            hardness=clamp10(material.hardness + 1), toughness=clamp10(material.toughness - 2),
            flammability=0, combustibility=0, burn_yield=0.0, burn_duration=0,
            color=tuple(int(c * 0.6 + 255 * 0.4) for c in material.color))
    return material.replace(id=material.id + "+cast", tenacity=clamp10(material.tenacity + 1),
                            toughness=clamp10(material.toughness + 1))


def fire_clay(material: Material) -> Material:
    """Fire a clay in a kiln: it comes out as hard, heat-resistant ceramic (bricks, pots)."""
    return material.replace(id=material.id + "+fired", name=material.name + " ceramic", family=Family.CERAMIC,
                            hardness=clamp10(material.hardness + 3), toughness=clamp10(material.toughness + 1),
                            density=clamp10(material.density + 1), insulation=clamp10(material.insulation + 1),
                            tenacity=0.0, color=tuple(int(c * 0.85 + 30) for c in material.color))


# ── structures ──────────────────────────────────────────────────────────────────────────────────────────
def structural_rating(material: Material) -> float:
    """How good a load-bearing or wall material it is: the geometric mean of toughness, density and hardness, so one
    high property cannot cover for a missing one (glass: hard but brittle, lead: dense but soft)."""
    return (max(material.toughness, 0.1) * max(material.density, 0.1) * max(material.hardness, 0.1)) ** (1 / 3)


def wall_hit_points(material: Material, quality: float = 1.0) -> int:
    return max(1, round(3.0 * structural_rating(material) * quality))


def can_bear_load(material: Material, span: int = 1) -> bool:
    """A beam/roof support needs toughness and tenacity (not to crack or pull apart) and some stiffness; `span` (tiles) raises
    the bar."""
    return material.toughness >= 3 + span and material.tenacity >= 2 + span and structural_rating(material) >= 3.0


def shelter_insulation(material: Material) -> float:
    """Heat kept in by a wall of the material: insulation, minus what leaks through conduction."""
    return clamp10(material.insulation - 0.3 * material.thermal_conductivity)


def radiation_shielding(material: Material) -> float:
    return clamp10(material.density * 0.8 + material.hardness * 0.1)


# ── damage interaction ────────────────────────────────────────────────────────────────────────────────────
# damage type -> (target properties that resist it, attacker properties that deliver it)
DAMAGE_PROPERTIES: Dict[DamageType, Tuple[Tuple[str, str], Tuple[str, str]]] = {
    DamageType.SHARP: (("hardness", "toughness"), ("hardness", "toughness")),   # an edge must be harder than the target and not shatter
    DamageType.BLUNT: (("toughness", "density"), ("density", "toughness")),     # mass and a head that does not fail
    DamageType.PIERCE: (("hardness", "tenacity"), ("hardness", "tenacity")),    # a point must be hard and hold together
}
REFERENCE = 5.0  # a target whose resisting properties average 5 is "ordinary" (multiplier 1.0 for an ordinary weapon)


def attack_factor(damage_type: DamageType, attacker: Optional[Mapping[str, float]], target: Material) -> float:
    """Multiplier on a hit of `damage_type` by a weapon with properties `attacker` (None: bare hands, treated as ordinary
    for the type) against `target`. It is the ratio of how well the weapon delivers the damage to how well the target
    resists it, clamped to 0.2-3.0; a point or edge softer than the target also loses a third of its effect."""
    resist_keys, deliver_keys = DAMAGE_PROPERTIES[damage_type]
    resistance = sum(target.get(k) for k in resist_keys) / 2
    if attacker is None:
        delivery = REFERENCE
    else:
        delivery = sum(attacker.get(k, 0.0) for k in deliver_keys) / 2
        if damage_type is not DamageType.BLUNT and attacker.get("hardness", 0.0) < target.hardness:
            delivery *= 2 / 3
    return max(0.2, min(3.0, delivery / max(resistance, 0.5)))


# ── composition ────────────────────────────────────────────────────────────────────────────────────────
class Rule(Enum):
    ROLE = "role"       # take the property from one role: ("role", "head")
    MEAN = "mean"       # weighted mean over roles: ("mean", {"head": 2, "handle": 1})
    MIN = "min"         # weakest link: ("min", ("head", "handle"))
    MAX = "max"         # best part: ("max", ("a", "b"))


Derivation = Tuple[str, object]


def derive_property(prop: str, parts: Mapping[str, Material], rule: Optional[Derivation]) -> float:
    """One derived property of a composite. Default rule (no rule given): mean over all parts, equally weighted."""
    assert prop in PROPERTY_KEYS
    if rule is None:
        values = [m.get(prop) for m in parts.values()]
        return sum(values) / len(values)
    kind, arg = rule
    if kind == Rule.ROLE.value:
        return parts[arg].get(prop)
    if kind == Rule.MEAN.value:
        total = sum(arg.values())
        return sum(parts[role].get(prop) * w for role, w in arg.items()) / total
    if kind == Rule.MIN.value:
        return min(parts[role].get(prop) for role in arg)
    if kind == Rule.MAX.value:
        return max(parts[role].get(prop) for role in arg)
    raise ValueError(f"unknown derivation rule {kind!r}")


def derive_properties(parts: Mapping[str, Material], rules: Mapping[str, Derivation],
                      quality: float = 1.0, keys: Iterable[str] = PROPERTY_KEYS) -> Dict[str, float]:
    """All properties of a composite from its parts, by the recipe's rules (properties without a rule use the default).
    `quality` (0.5-1.5) scales the mechanical properties a builder can influence (hardness, toughness, tenacity)."""
    out = {}
    for prop in keys:
        value = derive_property(prop, parts, rules.get(prop))
        if prop in ("hardness", "toughness", "tenacity"):
            value *= quality
        out[prop] = clamp10(value)
    return out


def blend_colors(parts: Mapping[str, Material], weights: Mapping[str, float]) -> RGB:
    """Visible colour of a composite: weighted mean of its parts' colours (head of a hatchet dominates, binding barely shows)."""
    total = sum(weights.values())
    return tuple(int(sum(parts[role].color[i] * w for role, w in weights.items()) / total) for i in range(3))  # type: ignore


def describe_property(prop: str, value: float) -> str:
    """Plain-language reading of a property value."""
    return "none" if value <= 0.5 else "very low" if value < 2.5 else "low" if value < 4.5 else "moderate" if value < 6.5 else "high" if value < 8.5 else "extreme"
