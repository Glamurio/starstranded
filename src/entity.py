from __future__ import annotations

import copy
import math
from typing import Optional, List, Tuple, Type, TypeVar, TYPE_CHECKING, Union

from render_order import RenderOrder

if TYPE_CHECKING:
    from components.ai import BaseAI
    from components.consumable import Consumable
    from components.equipment import Equipment
    from components.equippable import Equippable
    from components.unit import Unit
    from components.inventory import Inventory
    from components.level import Level
    from world import GameMap

T = TypeVar("T", bound="Entity")


class Entity:
    """
    A generic object to represent players, enemies, items, etc.
    """
    parent: Union[GameMap, Inventory]

    def __init__(
        self,
        parent: Optional[GameMap] = None,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: Optional[str] = None,
        type: str = "<Unnamed>",
        attributes: List[str] = [],
        inventory: Inventory = None,
        blocks_movement: bool = False,
        render_order: RenderOrder = RenderOrder.CORPSE,
    ):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.type = type
        self.attributes = attributes
        self.inventory = inventory
        self.blocks_movement = blocks_movement
        self.render_order = render_order
        if parent:
            # If parent isn't provided now then it will be set later.
            self.parent = parent
            parent.entities.add(self)

    @property
    def gamemap(self) -> GameMap:
        return self.parent.gamemap


    def spawn(self: T, gamemap: GameMap, x: int, y: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = gamemap
        gamemap.entities.add(clone)
        return clone


    def place(self, x: int, y: int, gamemap: Optional[GameMap] = None) -> None:
        """Place this entity at a new location.  Handles moving across GameMaps."""
        self.x = x
        self.y = y

        if not gamemap:
            return
            
        if hasattr(self, "parent"):  # Possibly uninitialized.
            if self.parent is self.gamemap:
                self.gamemap.entities.remove(self)

        self.parent = gamemap
        self.parent.entities.add(self)


    def distance(self, x: int, y: int) -> float:
        """
        Return the distance between the current entity and the given (x, y) coordinate.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)


    def move(self, dest_x: int, dest_y: int) -> None:
        """Move the entity by a given amount.""" 
        self.x = dest_x
        self.y = dest_y


    def set_name(self, name: str) -> str:
        """Sets the entity name."""
        self.name = name


    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        description = f'{" ".join(attributes)} {self.type}' if attributes else self.type
        return f'{self.name}, the {description}' if self.name else description


    def add_attribute(self, attribute: str) -> None:
        """Adds attribute to list of attributes."""
        self.attributes.append(attribute)


    def remove_attribute(self, attribute: str) -> None:
        """Removes attribute from list of attributes."""
        self.attributes.remove(attribute)


class Actor(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: Optional[str] = None,
        type: str = "<Unnamed>",
        ai_cls: Type[BaseAI],
        equipment: Equipment,
        attributes: List[str] = [],
        inventory: Inventory = None,
        unit: Unit,
        level: Level,
        is_alive: bool = True,
    ):
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            type=type,
            inventory=inventory,
            attributes=attributes,
            blocks_movement=True,
            render_order=RenderOrder.ACTOR,
        )

        self.ai: Optional[BaseAI] = ai_cls(self)

        self.equipment: Equipment = equipment
        self.equipment.parent = self

        self.unit = unit
        self.unit.parent = self

        self.inventory = inventory
        self.inventory.parent = self

        self.level = level
        self.level.parent = self

        self.is_alive = is_alive

    @property
    def has_ai(self) -> bool:
        """Returns True as long as this actor can perform actions."""
        return bool(self.ai)

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        description = f'{" ".join(attributes)} {self.type}' if attributes else self.type
        if not self.is_alive:
            return f'remains of {self.name}' if self.name else f'{self.type} remains'
        return f'{self.name}, the {description}' if self.name else description

class Item(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: Optional[str] = None,
        type: str = "<Unnamed>",
        inventory: Inventory = None,
        attributes: List[str] = [],
        material: str = None,
        consumable: Optional[Consumable] = None,
        equippable: Optional[Equippable] = None,
    ):
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            type=type,
            attributes=attributes,
            inventory=inventory,
            blocks_movement=False,
            render_order=RenderOrder.ITEM,
        )

        self.material = material
        self.consumable = consumable

        if self.consumable:
            self.consumable.parent = self

        self.equippable = equippable

        if self.equippable:
            self.equippable.parent = self

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        material_type = f'{self.material} {self.type}' if self.material else  self.type
        description = f'{" ".join(attributes)} {material_type}' if attributes else material_type
        return f'{self.name}, the {description}' if self.name else description
