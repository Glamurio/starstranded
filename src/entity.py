from __future__ import annotations

import copy
import math
from typing import Optional, List, Tuple, TypeVar, TYPE_CHECKING, Union

from render_order import RenderOrder

if TYPE_CHECKING:
    from components.inventory import Inventory
    from components.unit import Unit
    from world import GameMap
    from engine import Engine

T = TypeVar("T", bound="Entity")

class Entity:
    """
    A generic object to represent players, enemies, items, etc.
    """
    parent: Union[GameMap, Inventory]

    def __init__(self):
        self.parent: Optional[GameMap] = None
        self.x: int = 0
        self.y: int = 0
        self.sprite_pos: Tuple[int, int] = (0, 0)
        self.corpse_sprite_pos: Tuple[int, int] = (0, 0)
        self.mirrored = False
        self.char: int = 0xE000
        self.char_left: int = 0xE000
        self.char_right: int = 0xE000
        self.char_corpse: int  = 0xE000
        self.color: Tuple[int, int, int] = (255, 255, 255)
        self.shade: Tuple[int, int, int] = (255, 255, 255)
        self.name: Optional[str] = None
        self.kind: str = None
        self.attributes: List[str] = []
        self.inventory: Inventory = None
        self.blocks_movement: bool = False
        self.blocks_sight: bool = False
        self.render_order: RenderOrder = RenderOrder.CORPSE

        if self.parent:
            # If parent isn't provided now then it will be set later.
            self.parent.entities.add(self)
        self.on_init()

    @property
    def game_map(self) -> GameMap:
        return self.parent.game_map

    @property
    def engine(self) -> Engine:
        return self.game_map.engine

    def on_init(self):
        """Gets called after initialization of the object."""
        pass

    def spawn(self: T, game_map: GameMap, x: int, y: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = game_map
        game_map.entities.add(clone)
        return clone

    def place(self, x: int, y: int, game_map: Optional[GameMap] = None) -> None:
        """Place this entity at a new location.  Handles moving across GameMaps."""
        self.x = x
        self.y = y

        if not game_map:
            return
            
        if hasattr(self, "parent"):  # Possibly uninitialized.
            if self.parent and self.parent is self.game_map:
                self.game_map.entities.remove(self)

        self.parent = game_map
        self.parent.entities.add(self)

    def distance(self, x: int, y: int) -> float:
        """
        Return the distance between the current entity and the given (x, y) coordinate.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def redirect_char(self, face_right: bool = False):
        """Redirects unit sprite"""
        if face_right:
            self.char = self.char_right
        else:
            self.char = self.char_left

    def move(self, dest_x: int, dest_y: int) -> None:
        """Move the entity by a given amount."""
        if self.x > dest_x:
            self.redirect_char()
        elif self.x < dest_x:
            self.redirect_char(True)
        self.x = dest_x
        self.y = dest_y

    def set_name(self, name: str) -> str:
        """Sets the entity name."""
        self.name = name

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        description = f'{" ".join(attributes)} {self.kind}' if attributes else self.kind
        return f'{self.name}, the {description}' if self.name else description

    def add_attribute(self, attribute: str) -> None:
        """Adds attribute to list of attributes."""
        self.attributes.append(attribute)

    def remove_attribute(self, attribute: str) -> None:
        """Removes attribute from list of attributes."""
        self.attributes.remove(attribute)


class Item(Entity):
    def __init__(self):
        Entity.__init__(self)
        self.render_order = RenderOrder.ITEM
        self.material = None

    def activate(self, user: Unit) -> None:
        """Invoke this items ability.

        `action` is the context for this activation.
        """
        raise NotImplementedError()

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        material_type = f'{self.material} {self.kind}' if self.material else  self.kind
        description = f'{" ".join(attributes)} {material_type}' if attributes else material_type
        return f'{self.name}, the {description}' if self.name else description
