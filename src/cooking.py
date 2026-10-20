"""Food and cooking.

Every food has a few **flavours** (sweet, spicy, salty, sour, savory, bitter): never all of them, rolled once when the planet is made
(fruit and blooms from the plant that bears them, meat from the animal). Eaten **raw** food gives only `RAW_FRACTION` of its worth; cooked
into a **dish** at a lit campfire it gives all of it and more. Some raw food is unsafe: a plant that is poisonous only raw (`raw_toxic`),
and, for people, all meat (`cooks_meat`). Something poisonous by nature stays poisonous however it is cooked.

A dish is one of `DISHES` (stew: meat and liquid; soup: fruit and liquid; skewer: meat or fruit on a stick), with flowers as seasoning. It
takes the flavours of what went in and is named after the strongest (`flavour_name`: "sweet and sour stew")."""
from __future__ import annotations

import random
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import seeds

FLAVOURS = ("sweet", "spicy", "salty", "sour", "savory", "bitter")
FRUIT_WEIGHTS = {"sweet": 4.0, "sour": 3.0, "bitter": 1.5, "salty": 0.7, "spicy": 1.0, "savory": 0.8}
HERB_WEIGHTS = {"spicy": 3.0, "bitter": 2.0, "sour": 1.5, "savory": 2.0, "salty": 0.8, "sweet": 1.0}
MEAT_WEIGHTS = {"savory": 4.0, "salty": 2.0, "sweet": 0.7, "bitter": 0.8, "spicy": 0.5, "sour": 0.5}
MAX_FLAVOURS = 2
"""A food has one or two flavours: none has everything."""

RAW_FRACTION = 0.3
"""The share of its worth that raw food gives."""
RAW_MEAT_POISON = 12
"""Turns of poison from raw meat for a people who must cook it, and from a plant that is poisonous raw."""
LIQUID_SIPS = 2
BROTH_THIRST = 14
COOK_TURNS = 4


def roll_flavours(key: str, colour: Sequence[int], kind: str) -> Tuple[str, ...]:
    """The flavours of one food, a pure function of what it is (so rolling them leaves the planet's own random numbers alone)."""
    rng = random.Random(seeds.mix_seed(zlib.crc32(key.encode()), *[int(c) for c in colour], zlib.crc32(kind.encode())))
    weights = {"fruit": FRUIT_WEIGHTS, "herb": HERB_WEIGHTS, "meat": MEAT_WEIGHTS}[kind]
    pool = dict(weights)
    count = 1 if rng.random() < 0.55 else MAX_FLAVOURS
    found = []
    for _ in range(count):
        choice = rng.choices(list(pool), weights=list(pool.values()))[0]
        found.append(choice)
        del pool[choice]
    return tuple(sorted(found, key=FLAVOURS.index))


def roll_raw_toxicity(key: str, colour: Sequence[int], chance: float) -> int:
    """Poison (0: none) of a plant food that is poisonous only raw: a pure function of what it is, like `roll_flavours`."""
    rng = random.Random(seeds.mix_seed(zlib.crc32(key.encode()), *[int(c) for c in colour], 7331))
    return rng.randint(8, 20) if rng.random() < chance else 0


# ── dish names ─────────────────────────────────────────────────────────────────────────────────────────────
PAIR_NAMES = {
    frozenset(("sweet", "sour")): "sweet and sour", frozenset(("salty", "savory")): "hearty", frozenset(("spicy", "savory")): "peppery",
    frozenset(("sweet", "bitter")): "bittersweet", frozenset(("sweet", "spicy")): "spiced", frozenset(("sour", "bitter")): "tart",
    frozenset(("salty", "sour")): "briny", frozenset(("sweet", "savory")): "glazed", frozenset(("spicy", "sour")): "hot and sour",
    frozenset(("savory", "bitter")): "smoky", frozenset(("salty", "bitter")): "dark salted", frozenset(("sweet", "salty")): "salted sweet",
    frozenset(("spicy", "bitter")): "fiery", frozenset(("spicy", "salty")): "peppered", frozenset(("sour", "savory")): "tangy",
}


def dominant(weights: Dict[str, float]) -> Tuple[str, ...]:
    """The one or two flavours that carry a dish: the strongest, plus the second if it is at least half as strong."""
    ranked = sorted(weights.items(), key=lambda kv: (-kv[1], FLAVOURS.index(kv[0])))
    if not ranked:
        return ()
    if len(ranked) > 1 and ranked[1][1] * 2 >= ranked[0][1]:
        return tuple(sorted((ranked[0][0], ranked[1][0]), key=FLAVOURS.index))
    return (ranked[0][0],)


def flavour_name(flavours: Tuple[str, ...]) -> str:
    if len(flavours) == 2:
        return PAIR_NAMES[frozenset(flavours)]
    return flavours[0] if flavours else "plain"


# ── what is food ───────────────────────────────────────────────────────────────────────────────────────────
def role(item) -> Optional[str]:
    """How an item can go into a dish: meat, fruit, herb (a flower's bloom: seasoning), liquid (a flask of it) or stick (a branch)."""
    from components.consumable import Fruit, Meat
    from crafting import Flask
    if isinstance(item, Meat):
        return "meat"
    if isinstance(item, Fruit):
        return "herb" if getattr(item.kind, "bloom", False) else "fruit"
    if isinstance(item, Flask):
        return "liquid" if item.sips else None
    if getattr(item, "form", None) == "Branch":
        return "stick"
    return None


def flavours_of(item) -> Tuple[str, ...]:
    if hasattr(item, "flavours"):
        return tuple(item.flavours)
    return tuple(getattr(item.kind, "flavours", ()) or ())


@dataclass(frozen=True)
class DishType:
    key: str
    name: str
    kind_key: str
    main: Tuple[str, ...]          # roles of the main ingredients
    liquid: bool
    stick: bool
    multiplier: float
    summary: str


DISHES: Dict[str, DishType] = {d.key: d for d in (
    DishType("stew", "Stew", "stew", ("meat",), True, False, 1.15, "meat simmered in liquid"),
    DishType("soup", "Soup", "soup", ("fruit",), True, False, 1.0, "fruit boiled in liquid"),
    DishType("skewer", "Skewer", "skewer", ("meat", "fruit"), False, True, 1.1, "meat or fruit roasted on a branch"),
)}
MAX_MAIN, MAX_HERBS = 3, 2
STEW_EXTRA_FRUIT = 1
"""A stew may take this much fruit besides its meat; a soup a piece of meat."""


@dataclass
class Plan:
    """What cooking a chosen set of ingredients would make, or why it cannot."""
    dish: DishType
    ok: bool = False
    problem: str = ""
    flavours: Tuple[str, ...] = ()
    name: str = ""
    hunger: int = 0
    thirst: int = 0
    toxic: int = 0
    nutrition: str = "plant"
    used: List = field(default_factory=list)


def base_hunger(item) -> float:
    """What an ingredient is worth when cooked (the full value; eaten raw it gives `RAW_FRACTION` of it)."""
    if role(item) == "meat":
        return item.base_hunger
    return float(item.kind.hunger_amount)


def plan(dish: DishType, items: Sequence) -> Plan:
    """Check `items` (inventory things) against the dish and work out what it would be."""
    from crafting import Flask
    import liquids
    result = Plan(dish)
    by_role: Dict[str, List] = {}
    for item in items:
        by_role.setdefault(role(item), []).append(item)
    mains = [i for r in dish.main for i in by_role.get(r, [])]
    extra_ok = {"stew": ("fruit", STEW_EXTRA_FRUIT), "soup": ("meat", 1)}.get(dish.key)
    extras = by_role.get(extra_ok[0], []) if extra_ok and extra_ok[0] not in dish.main else []
    herbs = by_role.get("herb", [])
    flasks = by_role.get("liquid", [])
    sticks = by_role.get("stick", [])
    stray = [i for i in items if role(i) not in (*dish.main, "herb", "liquid", "stick") and i not in extras]
    if any(role(i) is None for i in items):
        result.problem = "That cannot go into a dish."
    elif not mains:
        result.problem = f"A {dish.name.lower()} needs {' or '.join(dish.main)}."
    elif len(mains) > MAX_MAIN:
        result.problem = f"At most {MAX_MAIN} main ingredients."
    elif extras and len(extras) > extra_ok[1]:
        result.problem = f"At most {extra_ok[1]} {extra_ok[0]} besides the main ingredient."
    elif len(herbs) > MAX_HERBS:
        result.problem = f"At most {MAX_HERBS} flowers for seasoning."
    elif dish.liquid and len(flasks) != 1:
        result.problem = "It needs one flask of liquid."
    elif not dish.liquid and flasks:
        result.problem = f"A {dish.name.lower()} takes no liquid."
    elif dish.stick and len(sticks) != 1:
        result.problem = "It needs a branch to roast it on."
    elif not dish.stick and sticks:
        result.problem = f"A {dish.name.lower()} takes no branch."
    elif stray:
        result.problem = "That does not suit this dish."
    elif flasks and liquids.LiquidKind(flasks[0].liquid) in (liquids.LiquidKind.TOXIC, liquids.LiquidKind.ACIDIC, liquids.LiquidKind.LAVA):
        result.problem = "That liquid would ruin it."
    elif flasks and flasks[0].sips < LIQUID_SIPS:
        result.problem = "The flask holds too little liquid."
    else:
        result.ok = True
    if not result.ok:
        return result
    foods = mains + extras + herbs
    weights: Dict[str, float] = {}
    for item in foods:
        for flavour in flavours_of(item):
            weights[flavour] = weights.get(flavour, 0.0) + (1.5 if role(item) == "herb" else 1.0)
    result.flavours = dominant(weights)
    kind_name = flavour_name(result.flavours)
    result.name = f"{kind_name} {dish.name.lower()}"
    worth = sum(base_hunger(i) for i in foods)
    harmony = 1.0 + 0.1 * min(2, max(0, len(weights) - 1))
    result.hunger = max(1, round(worth * dish.multiplier * harmony)) + (4 if dish.liquid else 0)
    result.thirst = BROTH_THIRST if dish.liquid else round(sum(i.kind.thirst_amount for i in foods))
    result.toxic = max([int(getattr(i.kind, "toxicity", 0) or 0) for i in foods if not getattr(i.kind, "raw_toxic", False)] or [0])
    result.nutrition = "mixed" if by_role.get("meat") and (by_role.get("fruit") or by_role.get("herb")) else "meat" if by_role.get("meat") else "plant"
    result.used = list(foods) + flasks + sticks
    return result


def lit_fire_near(world, x: int, y: int):
    """A lit campfire (not a torch) on or next to a tile."""
    from crafting import Campfire, Torch
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for thing in world.get_entities_at_location(x + dx, y + dy):
                if isinstance(thing, Campfire) and not isinstance(thing, Torch) and thing.is_placed and thing.emits_light:
                    return thing
    return None


def cookable(unit) -> list:
    """Everything the unit carries that may go into a dish."""
    return [i for i in unit.inventory.items if role(i) is not None]


def has_food(unit) -> bool:
    """Does the unit carry anything to cook (meat, fruit or herbs: a branch or a flask alone is no meal)?"""
    return any(role(i) in ("meat", "fruit", "herb") for i in unit.inventory.items)


def cook(engine, unit, dish: DishType, items: Sequence):
    """Cook the chosen items into a dish in the unit's pack (the ingredients are used up; a flask gives `LIQUID_SIPS` sips). Raises
    `Impossible` when it cannot be done."""
    import exceptions
    from components.consumable import Dish
    import species as defs
    outcome = plan(dish, items)
    if not outcome.ok:
        raise exceptions.Impossible(outcome.problem)
    if lit_fire_near(unit.game_map, unit.x, unit.y) is None:
        raise exceptions.Impossible("You need a lit campfire beside you to cook.")
    for item in outcome.used:
        if role(item) == "liquid":
            if item.sips < LIQUID_SIPS:
                raise exceptions.Impossible("The flask holds too little liquid.")
            item.sips -= LIQUID_SIPS
            if not item.sips:
                item.liquid, item.boiled = 0, False
        else:
            unit.inventory.remove(item)
    made = Dish(getattr(defs, dish.kind_key.upper()), outcome.name, outcome.flavours, outcome.hunger, outcome.thirst, outcome.toxic,
                outcome.nutrition, parent=unit.inventory)
    unit.inventory.add(made)
    engine.game_world.pass_time(unit=unit, time=COOK_TURNS)
    return made
