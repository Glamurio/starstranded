"""Acquisition-path validation: can every recipe actually be completed on a given planet?

`reachable(planet)` plays the whole crafting tree forward on paper: it starts from what the planet gives (the wood of its
trees, its stones, ores, coal, sand, clay, fibres and hides), then repeatedly applies every recipe whose needs are met by
the pieces, tools and stations obtained so far, adding what it produces (an ingot of each smeltable metal, bricks,
glass, wire, every tool's capabilities, every station). It returns the recipes that end up reachable. Gathered materials
and anything craftable count as unlimited, so only *properties* can block a recipe, never quantity. Skills are ignored on
purpose (they are earned by practice, see `Unit.practice`).
"""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

import crafting
import materials
import species as defs
from items import ABRASIVE, HARD_STONE
from materials import Family, Material
from recipes import RECIPES


def natural_pieces(planet) -> Dict[str, List[Material]]:
    """Form -> materials that can be gathered or mined on the planet."""
    pieces: Dict[str, List[Material]] = {"Branch": [], "Stone": [], "Ore": [], "Coal": [], "Sand": [], "Clay": [], "Fibre": [], "Hide": [], "Feather": [], "Chitin": [], "Scale": []}
    for species in planet.flora:
        if species.material is not None:
            pieces["Branch"].append(species.material)
        if species.fiber is not None:
            pieces["Fibre"].append(species.fiber)
    for species in planet.fauna:
        if species.hide is not None:
            pieces[defs.COVERINGS.get(species.covering, (defs.PIECE_HIDE,))[0].object_type].append(species.hide)
    for _, material in planet.materials:
        if material.family is Family.FUEL:
            pieces["Coal"].append(material)
        elif material.family is Family.SAND:
            pieces["Sand"].append(material)
        elif material.family is Family.CLAY:
            pieces["Clay"].append(material)
        elif material.id.startswith("ore:"):
            pieces["Ore"].append(material)
        elif material.family in (Family.STONE, Family.CRYSTAL):
            pieces["Stone"].append(material)
    return pieces


def _satisfied(need: crafting.Need, pieces: Dict[str, List[Material]]) -> List[Material]:
    found = []
    for form in need.forms:
        for material in pieces.get(form, ()):
            if need.families and material.family not in need.families:
                continue
            if all(material.get(p) >= v for p, v in need.minimum) and all(material.get(p) <= v for p, v in need.maximum):
                found.append(material)
    return found


def reachable(planet) -> Tuple[Set[str], Dict[str, List[Material]], Set[str]]:
    """(recipe keys that can be completed, all pieces obtainable by form, capabilities obtainable)."""
    pieces = natural_pieces(planet)
    tags: Set[str] = set()
    if any(m.hardness >= HARD_STONE for m in pieces["Stone"]):
        tags.add("firestarting")
    if any(m.abrasivity >= ABRASIVE for m in pieces["Stone"] + pieces["Sand"]):
        tags.add("sharpening")
    done: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for recipe in RECIPES:
            if recipe.key in done:
                continue
            roles = {need.role: _satisfied(need, pieces) for need in recipe.needs}
            if any(not options for options in roles.values()):
                continue
            if any(tag not in tags for tag in recipe.tools):
                continue
            if recipe.heat:
                fuels = [m for form in crafting.FUEL_FORMS for m in pieces.get(form, ()) if m.burn_yield > 0]
                if not fuels:
                    continue
                temperature = 450.0 + 125.0 * max(m.combustibility for m in fuels)
                needed = recipe.min_temp
                if recipe.process == "glass":
                    needed = max([needed] + [m.melting_point for m in roles["sand"]])
                if recipe.process == "smelt":
                    options = [m for m in roles["ore"] if m.refines_to and planet.material(m.refines_to).melting_point <= temperature]
                    if not options:
                        continue
                    roles["ore"] = options
                if temperature < needed and recipe.process != "smelt":
                    continue
                if recipe.process == "glass":
                    roles["sand"] = [m for m in roles["sand"] if m.melting_point <= temperature]
                    if not roles["sand"]:
                        continue
            done.add(recipe.key)
            changed = True
            _produce(recipe, roles, planet, pieces, tags)
    return done, pieces, tags


def _produce(recipe, roles, planet, pieces, tags) -> None:
    """Add what a completed recipe makes: new pieces, tool capabilities, stations."""
    def add(form: str, mats) -> None:
        bucket = pieces.setdefault(form, [])
        for m in mats:
            if m not in bucket:
                bucket.append(m)

    if recipe.builder == "process":
        form = recipe.result.object_type
        source = next(iter(roles.values()))
        if recipe.process == "cord":
            add(form, source)
        elif recipe.process == "smelt":
            add(form, [materials.melt_and_cool(planet.material(m.refines_to)) for m in source])
        elif recipe.process == "brick":
            add(form, [materials.fire_clay(m) for m in source])
        elif recipe.process == "glass":
            add(form, [materials.melt_and_cool(m) for m in source])
        elif recipe.process == "wire":
            add(form, source)
        return
    kind = recipe.result
    designation = roles.get(recipe.designation) or next(iter(roles.values()))
    if kind is not None:
        add(kind.object_type, designation[:1])
        tags.update(kind.tool_tags)
        if kind.station:
            tags.add(kind.station)
