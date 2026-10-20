"""Decay: a dead creature lies as a corpse (meat, hide, a pool of blood), then after a few days is a skeleton (the loot and the
blood gone, a few bones left to take), and after longer it is gone altogether.

Times are in game time (`config.day_length` per day). A chunk is looked at about eight times a day while it is loaded, and the days
it was away are caught up when it is restored (`settle`), so the same things happen whether or not you watched."""
from __future__ import annotations

import random
from typing import Optional

from entity import EntityCategory

SKELETON_AFTER = 3.0      # days from death to a skeleton
GONE_AFTER = 12.0         # days from death until nothing is left
LOOKS_PER_DAY = 8
HUMAN_KEYS = ("human", "selenite_people", "mau", "selenite", "settler")
SKELETON_SPRITES = {"animal": (3, 26), "human": (22, 16)}      # a ribcage; a standing skeleton
BONE_COLOR = (214, 207, 190)


def skeleton_kind(unit) -> str:
    """"human" for the people (and settlers), "animal" for every creature."""
    return "human" if getattr(unit.kind, "key", "") in HUMAN_KEYS else "animal"


BONE_RANGES = {"hardness": (3, 6.5), "toughness": (2, 5.5), "tenacity": (2, 5), "density": (2, 5)}
"""The ranges of the properties a bone is rolled with (the rest of its properties are small and also vary)."""


def roll_bone(rng: Optional[random.Random] = None):
    """A bone with properties of its own: they do not follow from the creature it came from."""
    from materials import Family, Material
    rng = rng or random
    tint = rng.randint(-14, 10)
    return Material(
        f"bone:{rng.getrandbits(32)}", "bone", Family.BONE, tuple(max(0, min(255, c + tint)) for c in BONE_COLOR),
        hardness=round(rng.uniform(*BONE_RANGES["hardness"]), 1), toughness=round(rng.uniform(*BONE_RANGES["toughness"]), 1),
        tenacity=round(rng.uniform(*BONE_RANGES["tenacity"]), 1), density=round(rng.uniform(*BONE_RANGES["density"]), 1), elasticity=round(rng.uniform(0.5, 3), 1), insulation=round(rng.uniform(0.5, 2), 1),
        thermal_conductivity=round(rng.uniform(0.5, 2), 1), flammability=round(rng.uniform(0.5, 2), 1))


def skeletonize(unit) -> None:
    """Turn a corpse into a skeleton: its loot and the blood under it are gone and it holds a few bones."""
    import species as defs
    from items import Stuff
    world = unit.game_map
    inventory = unit.inventory
    for item in list(inventory.items):
        inventory.remove(item)
    unit.skeleton = skeleton_kind(unit)
    for _ in range(random.randint(1, 3) if unit.skeleton == "animal" else random.randint(2, 4)):
        inventory.add(Stuff(defs.PIECE_BONE, roll_bone(), inventory), force=True)
    if world is not None:
        for other in list(world.get_entities_at_location(unit.x, unit.y)):
            if getattr(other, "decal", False) and getattr(other, "fluid", None):
                world.remove_entity(other)


def vanish(unit) -> None:
    world = unit.game_map
    if world is not None:
        world.remove_entity(unit)


def corpses(chunk):
    return [e for e in chunk.by_category[EntityCategory.UNIT] if getattr(e, "is_alive", True) is False]


def settle(world, chunk, now: int) -> None:
    """Age the corpses and skeletons of a chunk to time `now`."""
    day = world.engine.config.day_length
    for unit in corpses(chunk):
        if getattr(unit, "died_at", None) is None:
            unit.died_at = now
            continue
        age = (now - unit.died_at) / day
        if age >= GONE_AFTER:
            vanish(unit)
        elif age >= SKELETON_AFTER and getattr(unit, "skeleton", None) is None:
            skeletonize(unit)
    chunk.decay_stamp = now


def tick(world, chunks, now: int) -> None:
    """Called each turn: settle the loaded chunks that have not been looked at for an eighth of a day."""
    step = world.engine.config.day_length / LOOKS_PER_DAY
    for chunk in chunks:
        stamp = chunk.decay_stamp
        if stamp is None or now - stamp >= step:
            settle(world, chunk, now)
