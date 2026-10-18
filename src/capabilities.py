"""Tags, capabilities and numeric modifiers: the one place that says what a trait *means*.

A **tag** is a named trait with documented semantics. Every tag has a `TagKind`:

- ``CAPABILITY``  something a unit can do or perceive (``darkvision``, ``chemical_analysis``). The gameplay system that
  cares (perception, scanner, ...) asks ``caps.has("darkvision")`` / ``caps.magnitude("darkvision")``.
- ``MODIFIER``    a numeric change to a shared *stat* (``increased_agility`` -> ``move_speed`` x2). Systems read the stat
  (``caps.stat("move_speed")``) and never the tag, so equipment, statuses, animals and races reuse the same stats.
- ``RESTRICTION`` something forbidden (``liquid_averse``). The restriction names the system that enforces it, and a
  tag can ``cancel`` it (``liquid_tolerant`` cancels ``liquid_averse``) so future abilities can overcome it.
- ``TRAIT``       descriptive and diet-like tags that other rules key off (``carnivore``, ``clawed``).

Effects can be *conditional* (``when="dark"``): the stat only changes while that context flag is true. The context is
supplied by the caller (`stat(name, dark=True)`), so the lighting system decides what "dark" is, not this module.

A tag counts once however many sources grant it (the largest magnitude wins).
Aggregation (documented, tested): ``add`` effects sum, ``mult`` effects multiply, both applied as
``(base + sum(add)) * product(mult)`` and then clamped to the stat's range. A `Grant` may override the magnitude of
its tag's first effect (a Mau is a x2.0 agile, boots of speed are x1.25) and ``capability`` magnitudes combine by max.

Everything that grants tags (races, backgrounds, creature species, equipment, statuses) produces `Grant`s; a unit's
`CapabilitySet` is built from all of them. `validate_content()` checks the registry is consistent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Dict, Iterable, Mapping, Optional, Tuple


class TagKind(Enum):
    CAPABILITY = "capability"
    MODIFIER = "modifier"
    RESTRICTION = "restriction"
    TRAIT = "trait"


class Op(Enum):
    ADD = "add"
    MULT = "mult"


@dataclass(frozen=True)
class StatDef:
    key: str
    base: float
    low: float
    high: float
    description: str


STATS: Dict[str, StatDef] = {}


def _stat(key: str, base: float, low: float, high: float, description: str) -> None:
    STATS[key] = StatDef(key, base, low, high, description)


_stat("move_speed", 1.0, 0.1, 4.0, "Moves per turn: 2.0 = two steps for the time of one, 0.5 = each step takes two turns.")
_stat("unarmed_damage", 0.0, 0.0, 20.0, "Flat power added to attacks made without a weapon.")
_stat("damage_taken_blunt", 1.0, 0.0, 4.0, "Multiplier on blunt damage received.")
_stat("damage_taken_sharp", 1.0, 0.0, 4.0, "Multiplier on sharp damage received.")
_stat("damage_taken_pierce", 1.0, 0.0, 4.0, "Multiplier on piercing damage received.")
_stat("crop_yield", 1.0, 0.0, 5.0, "Multiplier on fruit or seeds harvested from plants.")
_stat("crop_growth", 1.0, 0.1, 5.0, "Multiplier on the speed plants grow at when this unit tends them.")
_stat("breath_turns", 20.0, 1.0, 500.0, "Turns this unit can stay in a non-breathable place before it starts to suffocate.")
_stat("craft_cost", 1.0, 0.25, 2.0, "Multiplier on the number of components an eligible recipe consumes (never below 1 each).")
_stat("salvage_yield", 1.0, 0.0, 5.0, "Multiplier on the components recovered by salvaging.")
_stat("scan_depth", 0.0, 0.0, 5.0, "Extra information tiers the scanner reveals regardless of skill.")


@dataclass(frozen=True)
class Effect:
    stat: str
    op: Op
    value: float
    when: Optional[str] = None  # context flag that must be true ("dark", ...); None: always


@dataclass(frozen=True)
class TagDef:
    key: str
    kind: TagKind
    description: str
    systems: Tuple[str, ...] = ()           # which systems consume it (documentation, checked to be non-empty)
    effects: Tuple[Effect, ...] = ()        # MODIFIER tags
    cancels: Tuple[str, ...] = ()           # RESTRICTION tags this tag switches off
    default_magnitude: float = 1.0          # CAPABILITY magnitude when a grant gives none


TAGS: Dict[str, TagDef] = {}


def _tag(*args, **kwargs) -> TagDef:
    tag = TagDef(*args, **kwargs)
    assert tag.key not in TAGS, f"duplicate tag {tag.key!r}"
    TAGS[tag.key] = tag
    return tag


# ── modifiers (numbers on shared stats) ────────────────────────────────────────────────────────────────
_tag("increased_agility", TagKind.MODIFIER, "Moves faster. Magnitude = speed multiplier (Mau 2.0).", ("movement",),
     effects=(Effect("move_speed", Op.MULT, 1.5),))
_tag("night_aversion", TagKind.MODIFIER, "Slowed in the dark: moves at half speed where the light is too low to see by.",
     ("movement", "lighting"), effects=(Effect("move_speed", Op.MULT, 0.5, when="dark"),))
_tag("clawed", TagKind.MODIFIER, "Natural claws: extra damage with bare hands.", ("combat",),
     effects=(Effect("unarmed_damage", Op.ADD, 2.0),))
_tag("frail_exoskeleton", TagKind.MODIFIER, "Brittle chitin: takes more blunt damage.", ("combat", "damage"),
     effects=(Effect("damage_taken_blunt", Op.MULT, 1.5),))
_tag("increased_plant_yield", TagKind.MODIFIER, "Harvests more from plants.", ("farming",),
     effects=(Effect("crop_yield", Op.MULT, 1.5),))
_tag("faster_crop_growth", TagKind.MODIFIER, "Tended plants grow faster.", ("farming",),
     effects=(Effect("crop_growth", Op.MULT, 1.5),))
_tag("prolonged_breath_holding", TagKind.MODIFIER, "Can hold their breath much longer.", ("environment",),
     effects=(Effect("breath_turns", Op.MULT, 3.0),))
_tag("improved_crafting", TagKind.MODIFIER, "Wastes less when crafting: eligible recipes consume fewer components.",
     ("crafting",), effects=(Effect("craft_cost", Op.MULT, 0.75),))
_tag("enhanced_salvaging", TagKind.MODIFIER, "Recovers more from salvage.", ("salvage",),
     effects=(Effect("salvage_yield", Op.MULT, 1.5),))

# ── capabilities (what a unit can do or perceive) ─────────────────────────────────────────────────────
_tag("darkvision", TagKind.CAPABILITY, "Sees in the dark. Magnitude = radius (tiles) seen at night.", ("perception",),
     default_magnitude=12.0)
_tag("botanical_expertise", TagKind.CAPABILITY, "Understands plants: scanner reveals extra botanical facts.",
     ("scanner",))
_tag("chemical_analysis", TagKind.CAPABILITY, "Reads the chemistry of liquids and materials.", ("scanner",))
_tag("species_identification", TagKind.CAPABILITY, "Recognises animals and what they can be used for.", ("scanner",))
_tag("universal_translator", TagKind.CAPABILITY, "Reads and understands every known language.", ("translation",))
_tag("target_tracker", TagKind.CAPABILITY, "A corporate tracker locates marked targets within its signal range. "
     "Magnitude = range (tiles).", ("scanner", "contracts"), default_magnitude=60.0)
_tag("surveying", TagKind.CAPABILITY, "Reads terrain: reveals biome and points of interest in a radius. "
     "Magnitude = radius.", ("map", "scanner"), default_magnitude=24.0)
_tag("archaeology", TagKind.CAPABILITY, "Recognises precursor sites and artifacts.", ("scanner", "translation"))
_tag("first_aid", TagKind.CAPABILITY, "Treats injuries better.", ("health",))
_tag("pilot_training", TagKind.CAPABILITY, "Can fly and repair spacecraft systems.", ("escape",))

# ── tool and station capabilities (granted by held tools and nearby stations; see crafting.py / items.py) ─────
_tag("chopping", TagKind.CAPABILITY, "Fells trees and cuts wood quickly (hatchets, axes).", ("gathering", "crafting"))
_tag("mining", TagKind.CAPABILITY, "Breaks rock and digs out ore (pickaxes).", ("gathering", "crafting"))
_tag("digging", TagKind.CAPABILITY, "Digs sand and clay from the ground (shovels; hands do it slowly).", ("gathering",))
_tag("cutting", TagKind.CAPABILITY, "Cuts hide, fibre and cord (knives).", ("crafting",))
_tag("hammering", TagKind.CAPABILITY, "Shapes and joins hard parts (hammers).", ("crafting",))
_tag("sharpening", TagKind.CAPABILITY, "Puts an edge on a dull tool (whetstones).", ("crafting",))
_tag("salvaging", TagKind.CAPABILITY, "Takes constructed things apart for their parts (salvage tool).", ("salvage",))
_tag("workbench", TagKind.CAPABILITY, "A workbench is within reach: lets you do careful assembly.", ("crafting",))
_tag("furnace", TagKind.CAPABILITY, "A fuelled furnace is within reach: refines ore, fires clay, melts sand.", ("crafting",))

# ── restrictions ──────────────────────────────────────────────────────────────────────────────────────
_tag("liquid_averse", TagKind.RESTRICTION,
     "Will not voluntarily enter liquid terrain. Forced movement (knockback, falling) is not voluntary and is "
     "allowed; `liquid_tolerant` cancels it.", ("movement",))
_tag("liquid_tolerant", TagKind.CAPABILITY, "Overcomes liquid aversion (sealed suit, boots, training).", ("movement",),
     cancels=("liquid_averse",))

# ── diet and body traits ──────────────────────────────────────────────────────────────────────────────
_tag("carnivore", TagKind.TRAIT, "Digests meat only.", ("food",))
_tag("herbivore", TagKind.TRAIT, "Digests plant matter only.", ("food",))
_tag("omnivore", TagKind.TRAIT, "Digests meat and plant matter.", ("food",))
_tag("requires_organic", TagKind.TRAIT, "Cannot live on inorganic substances (minerals, metal).", ("food",))


@dataclass(frozen=True)
class Grant:
    """One tag handed out by a source (race, background, species, equipment), optionally with its own magnitude."""

    tag: str
    magnitude: Optional[float] = None

    def __post_init__(self):
        if self.tag not in TAGS:
            raise KeyError(f"unknown tag {self.tag!r}")


def grants(*items) -> Tuple[Grant, ...]:
    """`grants("darkvision", ("increased_agility", 2.0))` -> a tuple of `Grant`."""
    out = []
    for item in items:
        out.append(item if isinstance(item, Grant) else Grant(*item) if isinstance(item, tuple) else Grant(item))
    return tuple(out)


class CapabilitySet:
    """The tags a unit has from all its sources, and the stats they produce. Immutable."""

    def __init__(self, sources: Iterable[Grant] = ()):
        self._grants: Tuple[Grant, ...] = tuple(sources)
        self._tags: Dict[str, float] = {}
        for grant in self._grants:
            tag = TAGS[grant.tag]
            magnitude = grant.magnitude if grant.magnitude is not None else tag.default_magnitude
            old = self._tags.get(grant.tag)
            self._tags[grant.tag] = magnitude if old is None else max(old, magnitude)
        cancelled = {c for key in self._tags for c in TAGS[key].cancels}
        self._active = {key: m for key, m in self._tags.items() if key not in cancelled}

    # ── queries ──────────────────────────────────────────────────────────────────────────────────
    def has(self, tag: str) -> bool:
        """True if the tag is granted and not cancelled by another."""
        if tag not in TAGS:
            raise KeyError(f"unknown tag {tag!r}")
        return tag in self._active

    def magnitude(self, tag: str, default: float = 0.0) -> float:
        return self._active.get(tag, default)

    @property
    def tags(self) -> Tuple[str, ...]:
        return tuple(sorted(self._active))

    def stat(self, name: str, **context: bool) -> float:
        """The value of a shared stat: ``(base + sum(add)) * product(mult)`` over the active modifier effects whose
        condition holds in `context`, clamped to the stat's range."""
        definition = STATS[name]
        added, factor = 0.0, 1.0
        for key, magnitude in self._active.items():
            tag = TAGS[key]
            for index, effect in enumerate(tag.effects):
                if effect.stat != name or (effect.when is not None and not context.get(effect.when, False)):
                    continue
                value = effect.value
                if index == 0 and self._override(key) is not None:
                    value = self._override(key)
                if effect.op is Op.ADD:
                    added += value
                else:
                    factor *= value
        return min(definition.high, max(definition.low, (definition.base + added) * factor))

    def _override(self, tag: str) -> Optional[float]:
        values = [g.magnitude for g in self._grants if g.tag == tag and g.magnitude is not None]
        return max(values) if values else None

    def describe(self) -> Tuple[Tuple[str, str], ...]:
        """(tag, description) for every active tag, for UI."""
        return tuple((key, TAGS[key].description) for key in self.tags)

    def with_grants(self, extra: Iterable[Grant]) -> "CapabilitySet":
        return CapabilitySet(self._grants + tuple(extra))


EMPTY = CapabilitySet()


def validate_content() -> None:
    """Raise AssertionError if the tag/stat registry is inconsistent."""
    for key, tag in TAGS.items():
        assert key == tag.key
        assert tag.description and tag.systems, f"tag {key!r} needs a description and the systems that use it"
        if tag.kind is TagKind.MODIFIER:
            assert tag.effects, f"modifier tag {key!r} has no effects"
        for effect in tag.effects:
            assert effect.stat in STATS, f"{key}: unknown stat {effect.stat!r}"
        for cancelled in tag.cancels:
            assert cancelled in TAGS and TAGS[cancelled].kind is TagKind.RESTRICTION, f"{key}: bad cancel {cancelled!r}"
    for key, stat in STATS.items():
        assert stat.low <= stat.base <= stat.high, f"stat {key!r} base outside its range"
