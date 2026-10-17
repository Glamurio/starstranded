from enum import auto, Enum
from typing import Tuple


class RenderOrder(Enum):
    """Draw layers of a tile, bottom to top. The member's value is its position in the stack.

    terrain (the tile itself) < CORPSE < ITEM < SHRUB < UNIT < TREE

    Every entity on a visible tile is drawn, each as its own sprite with its own tint and mirroring, so a unit
    standing on an item standing on a corpse shows all three (sprites are transparent between their strokes).
    """
    CORPSE = auto()
    ITEM = auto()
    SHRUB = auto()
    UNIT = auto()
    TREE = auto()


LAYERS: Tuple[RenderOrder, ...] = tuple(RenderOrder)
"""All layers, bottom to top."""

GROUND_LAYERS: Tuple[RenderOrder, ...] = (RenderOrder.CORPSE, RenderOrder.ITEM)
"""Layers whose objects pile up on one tile (loot, remains) and are subject to the clutter safeguard."""

MAX_GROUND_OBJECTS_PER_TILE = 2
"""With `GameConfig.clutter_safeguard` on, only this many ground objects (the top ones) are drawn per tile; a stack
marker shows that more lie beneath. Units, shrubs and trees are never hidden."""
