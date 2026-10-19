"""Liquids: what lakes are made of, how deep they are and what they do to whoever touches or drinks them.

Every lake tile has a `depth` (1 shallow, 2 and 3 deeper; deeper liquid is always ringed by shallower liquid, see
`worldgen`) and a `kind`. Shallow liquid can be waded through, deeper liquid cannot. The kind is a property of the
region (a lake is one kind, mostly) and is *not* visible: the colour of a lake is unrelated to what it is. Finding out
needs tests (science gear, later) or the brute-force way.

- `IMPURE`: unsafe to drink as it is; boiling it makes it safe.
- `TOXIC`: poisonous; boiling does not help.
- `ACIDIC`: burns whoever wades through it (and their clothes) and eats through a flask that is dipped into it.
"""
from __future__ import annotations

import enum
import random
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from entity import Unit
    from world import World


class LiquidKind(enum.IntEnum):
    NONE = 0
    IMPURE = 1
    TOXIC = 2
    ACIDIC = 3


DEPTH_NAMES = {1: "shallow", 2: "deep", 3: "very deep"}

POISON_RAW = 6
"""Turns of poison (1 damage each) from drinking unboiled impure liquid."""
POISON_TOXIC = 25
"""Turns of poison from toxic liquid, boiled or not: enough to kill an unlucky player."""
ACID_WADE_DAMAGE = 3
ARMOR_BURN_CHANCE = 0.4
SIP_THIRST = 40
FLASK_SIPS = 3


def describe(tile) -> Optional[str]:
    """What the player sees of a liquid tile ("Liquid, shallow"); never its kind."""
    depth = int(tile["depth"])
    return f"Liquid, {DEPTH_NAMES.get(depth, 'deep')}" if depth else None


def kind_at(world: World, x: int, y: int) -> LiquidKind:
    tile = world.tile_at(x, y)
    return LiquidKind(int(tile["liquid"])) if tile is not None else LiquidKind.NONE


def nearest_liquid(world: World, x: int, y: int, radius: int = 1) -> Optional[tuple]:
    """`(x, y, kind)` of a liquid tile within `radius` of (x, y) (the closest one), or None."""
    best = None
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            tile = world.tile_at(x + dx, y + dy)
            if tile is not None and int(tile["liquid"]):
                d = max(abs(dx), abs(dy))
                if best is None or d < best[0]:
                    best = (d, x + dx, y + dy, LiquidKind(int(tile["liquid"])))
    return None if best is None else best[1:]


def on_enter(unit: Unit, world: World) -> None:
    """Called after a unit stepped onto (x, y): acidic liquid burns it, and maybe what it wears."""
    tile = world.tile_at(unit.x, unit.y)
    if tile is None or int(tile["liquid"]) != LiquidKind.ACIDIC:
        return
    import debug
    if debug.protects(unit):
        return
    visible = world.is_visible(unit.x, unit.y)
    unit.hp = max(0, unit.hp - ACID_WADE_DAMAGE)
    if visible:
        world.engine.message_log.add_message(
            f"{'You are' if unit is world.engine.player else unit.get_title() + ' is'} burned by the liquid!", (255, 120, 0)
        )
    equipment = getattr(unit, "equipment", None)
    armor = getattr(equipment, "armor", None) if equipment is not None else None
    if armor is not None and random.random() < ARMOR_BURN_CHANCE:
        equipment.unequip_from_slot("armor", False)
        unit.inventory.remove(armor)
        if visible:
            world.engine.message_log.add_message("The liquid eats through the armor!", (255, 120, 0))
    if unit.hp == 0 and unit.is_alive:
        unit.die(None)
