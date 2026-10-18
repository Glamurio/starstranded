"""Damage types and how a hit is resolved.

Weapons (and creatures' natural attacks) deal one `DamageType`; whatever is hit has a multiplier per type
(`resistances`, absent = 1.0, 0.0 = immune). Elemental types are meant to be added here later: they are just more
members of `DamageType`, nothing else needs to know the list.
"""
from __future__ import annotations

from enum import Enum
from typing import Iterable, Mapping, Tuple, Union

Resistances = Tuple[Tuple["DamageType", float], ...]
"""Immutable (type, multiplier) pairs, so species definitions stay hashable."""


class DamageType(Enum):
    BLUNT = "blunt"
    SHARP = "sharp"
    PIERCE = "pierce"

    def __str__(self) -> str:
        return self.value


def resolve(power: int, defense: int, damage_type: DamageType,
            resistances: Union[Resistances, Mapping[DamageType, float], Iterable] = ()) -> int:
    """Hit points lost by a target with `defense` and `resistances` when hit with `power` of `damage_type`.

    Flat defense comes off first; the type multiplier scales what is left. Anything that gets through at all does
    at least 1; an immune target (multiplier 0) takes none.
    """
    multiplier = dict(resistances).get(damage_type, 1.0)
    raw = power - defense
    if multiplier <= 0 or raw <= 0:
        return 0
    return max(1, round(raw * multiplier))
