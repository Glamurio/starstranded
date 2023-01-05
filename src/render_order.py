from enum import auto, Enum


class RenderOrder(Enum):
    CORPSE = auto()
    ITEM = auto()
    SHRUB = auto()
    UNIT = auto()
    TREE = auto()