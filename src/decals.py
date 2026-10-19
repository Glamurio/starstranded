"""Stains on the ground (blood, later oil or slime): scenery drawn under everything else, not an item, never picked up."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from entity import Entity
from render_order import RenderOrder

RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class DecalKind:
    key: str = "decal"
    name: str = "puddle"
    render_order: RenderOrder = RenderOrder.DECAL
    blocks_movement: bool = False
    blocks_sight: bool = False
    mirror: bool = False


PUDDLE = DecalKind("puddle", "puddle")


class Puddle(Entity):
    """A pool of `fluid` ("blood") of one colour, in one of eight shapes picked from its position."""
    object_type = "Puddle"
    decal = True

    def __init__(self, color: RGB, fluid: str = "blood"):
        Entity.__init__(self, PUDDLE)
        self.color = self.shade = tuple(color)
        self.fluid = fluid
        self.variant = 0

    @property
    def species(self) -> str:
        return f"puddle of {self.fluid}"

    @property
    def sprite_id(self) -> int:       # drawn procedurally (`atlas.get_puddle`), not from the sheet
        return -1


def is_decal(entity) -> bool:
    return getattr(entity, "decal", False)


def spill(game_map, x: int, y: int, color: RGB, fluid: str = "blood") -> None:
    """Leave a puddle at (x, y) unless one (of any fluid) is already there."""
    if any(is_decal(e) for e in game_map.stack_at(x, y)):
        return
    puddle = Puddle(color, fluid)
    puddle.variant = (x * 7 + y * 13) % 8
    puddle.place(x, y, game_map)
