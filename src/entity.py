from __future__ import annotations

import itertools
import math
from enum import Enum, auto
from typing import Optional, List, Tuple, TypeVar, TYPE_CHECKING, Union

import color
from render_order import RenderOrder
from species import Definition, ItemKind

if TYPE_CHECKING:
    from components.ai import BaseAI
    from components.inventory import Inventory
    from components.unit import Unit
    from world import GameMap
    from engine import Engine

T = TypeVar("T", bound="Entity")

_uid_counter = itertools.count(1)


def new_uid() -> int:
    """A process-unique, monotonically increasing entity id."""
    return next(_uid_counter)


def bump_uid_counter(minimum_next: int) -> None:
    """Make sure future uids are >= `minimum_next` (called after loading a save)."""
    global _uid_counter
    current = next(_uid_counter)
    _uid_counter = itertools.count(max(current, minimum_next))


class EntityCategory(Enum):
    """Explicit entity type tag (replaces `hasattr` duck typing for the map's per-kind collections)."""
    OTHER = auto()
    UNIT = auto()
    PLANT = auto()
    ITEM = auto()


class SpatialContainer:
    """A container that owns entity positions (implemented by `GameMap`).

    Entities never mutate their position behind its back: `Entity.x/y`, `blocks_movement`, `render_order` and
    `ai` are properties that call back into the container so its indexes stay consistent.
    """

    def add_entity(self, entity: Entity, x: int, y: int) -> None:
        raise NotImplementedError

    def remove_entity(self, entity: Entity) -> None:
        raise NotImplementedError

    def move_entity(self, entity: Entity, x: int, y: int) -> None:
        raise NotImplementedError

    def _entity_changed(self, entity: Entity, attribute: str, old, new) -> None:
        raise NotImplementedError


class Entity:
    """
    A generic object to represent players, enemies, items, etc.

    Static data lives in `kind` (an immutable, shared definition from `species.py`); the instance stores only
    per-instance state. Position is read/written through `x`, `y`, `place()` and `move()`; while the entity is on
    a map the map's spatial index is updated automatically.
    """
    parent: Union[GameMap, Inventory, None]
    category: EntityCategory = EntityCategory.OTHER
    object_type: str = "Entity"
    has_inventory: bool = False

    def __init__(self, kind: Definition):
        self.kind = kind
        self.uid: int = new_uid()
        self.parent: Optional[GameMap] = None
        self._x: int = 0
        self._y: int = 0
        self.mirrored = False
        self.color: Tuple[int, int, int] = color.white
        self.shade: Tuple[int, int, int] = color.white
        self.name: Optional[str] = None
        self.attributes: List[str] = []
        self._blocks_movement: bool = getattr(kind, "blocks_movement", False)
        self.blocks_sight: bool = getattr(kind, "blocks_sight", False)
        self._render_order: RenderOrder = kind.render_order
        self._ai: Optional[BaseAI] = None
        self.on_init()

    # ── static data, read from the definition ─────────────────────────────────────────
    @property
    def species(self) -> Optional[str]:
        """The kind's name, or what it looks like while the player has not identified it (see `lore`)."""
        name = getattr(self.kind, "name", None)
        key = getattr(self.kind, "key", None)
        if isinstance(key, str) and key.startswith("planet:"):
            import lore
            return lore.species_name(lore.run_of(self), self.kind)
        return name

    @property
    def is_corpse(self) -> bool:
        return False

    @property
    def sprite_id(self) -> int:
        """Atlas id of the sprite to draw: the corpse sprite once dead, the live sprite otherwise."""
        kind = self.kind
        if self.is_corpse and self.category is not EntityCategory.UNIT:   # creatures lie on their side (`atlas.get_remains`)
            corpse = kind.corpse_sprite_id
            if corpse is not None:
                return corpse
        return kind.sprite_id

    @property
    def flipped(self) -> bool:
        """Draw the sprite mirrored? Mirroring is a render-time flag: only living, mirrorable kinds face left/right."""
        return self.mirrored and not self.is_corpse and getattr(self.kind, "mirror", False)

    # ── light ─────────────────────────────────────────────────────────────────────
    @property
    def light_radius(self) -> int:
        """How far this entity can light the world (0 = it gives no light); comes from its kind."""
        return getattr(self.kind, "light_radius", 0)

    @property
    def emits_light(self) -> bool:
        """Is it giving light right now? (A campfire can be put out, a glowing creature cannot.)"""
        return self.light_radius > 0

    # ── indexed properties ────────────────────────────────────────────────────────
    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        self.set_position(value, self._y)

    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        self.set_position(self._x, value)

    def set_position(self, x: int, y: int) -> None:
        if isinstance(self.parent, SpatialContainer):
            self.parent.move_entity(self, x, y)
        else:
            self._x, self._y = x, y

    def _set_indexed(self, attribute: str, value) -> None:
        old = getattr(self, "_" + attribute)
        if old == value:
            return
        setattr(self, "_" + attribute, value)
        if isinstance(self.parent, SpatialContainer):
            self.parent._entity_changed(self, attribute, old, value)

    @property
    def blocks_movement(self) -> bool:
        return self._blocks_movement

    @blocks_movement.setter
    def blocks_movement(self, value: bool) -> None:
        self._set_indexed("blocks_movement", value)

    @property
    def render_order(self) -> RenderOrder:
        return self._render_order

    @render_order.setter
    def render_order(self, value: RenderOrder) -> None:
        self._set_indexed("render_order", value)

    @property
    def ai(self) -> Optional[BaseAI]:
        return self._ai

    @ai.setter
    def ai(self, value: Optional[BaseAI]) -> None:
        old = self._ai
        self._ai = value
        if isinstance(self.parent, SpatialContainer) and bool(old) != bool(value):
            self.parent._entity_changed(self, "ai", old, value)

    # ── derived references (no stored pointers besides `parent`) ─────────────────────
    @property
    def game_map(self) -> GameMap:
        return self.parent.game_map

    @property
    def engine(self) -> Engine:
        return self.game_map.engine

    def on_init(self):
        """Gets called after initialization of the object."""
        pass

    def on_added_to_map(self, game_map: GameMap) -> None:
        """Hook: called by the map after this entity was added to it."""

    def place(self, x: int, y: int, game_map: Optional[GameMap] = None) -> None:
        """Place this entity at a new location. With `game_map`, (re)attach it to that map."""
        if game_map is None:
            self.set_position(x, y)
        else:
            game_map.add_entity(self, x, y)

    def distance(self, x: int, y: int) -> float:
        """
        Return the distance between the current entity and the given (x, y) coordinate.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def move(self, dest_x: int, dest_y: int) -> None:
        """Move the entity to (dest_x, dest_y), facing the direction of travel."""
        if self.x > dest_x:
            self.mirrored = False
        elif self.x < dest_x:
            self.mirrored = True
        self.set_position(dest_x, dest_y)
        if self.category is EntityCategory.UNIT and isinstance(self.parent, SpatialContainer):
            import liquids
            liquids.on_enter(self, self.parent)

    def set_name(self, name: str) -> str:
        """Sets the entity name."""
        self.name = name

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        description = f'{" ".join(attributes)} {self.species}' if attributes else self.species
        return f'{self.name}, the {description}' if self.name else description

    def add_attribute(self, attribute: str) -> None:
        """Adds attribute to list of attributes."""
        self.attributes.append(attribute)

    def remove_attribute(self, attribute: str) -> None:
        """Removes attribute from list of attributes."""
        self.attributes.remove(attribute)


class Item(Entity):
    category = EntityCategory.ITEM
    kind: ItemKind

    def __init__(self, kind: ItemKind):
        Entity.__init__(self, kind)
        self.material: Optional[str] = kind.material
        self.color = kind.color
        if kind.shade_sigma is not None:
            from utilities import get_gaussian_shade
            self.shade = get_gaussian_shade(self.color, kind.shade_sigma)

    @property
    def object_type(self) -> str:
        return self.kind.object_type

    @property
    def species(self) -> Optional[str]:
        return self.kind.species

    def activate(self, user: Unit) -> None:
        """Invoke this items ability.

        `action` is the context for this activation.
        """
        raise NotImplementedError()

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        material_type = f'{self.material} {self.object_type}' if self.material else self.object_type
        description = f'{" ".join(attributes)} {material_type}' if attributes else material_type
        return f'{self.name}, the {description}' if self.name else description

class Constructable(Item):
    """
    An Item that can be placed on the map as a structure.
    
    While in inventory, it behaves like any other Item.
    When activated, the player places it on the current or an adjacent tile.
    """
    def __init__(self, kind: ItemKind):
        Item.__init__(self, kind)
        self.is_placed: bool = False

    def activate(self, user: Unit) -> None:
        """Activating a constructable triggers placement."""
        # This will be handled by the input handler to let the player pick a tile
        from input_handlers import PlaceConstructableHandler
        engine = user.game_map.engine
        engine.session.push(PlaceConstructableHandler(engine, self))

    def place_on_map(self, x: int, y: int, game_map) -> None:
        """Remove from inventory and place on the game map."""
        from components.inventory import Inventory
        if isinstance(self.parent, Inventory):
            self.parent.remove(self)
        self.is_placed = True
        self.place(x, y, game_map)

    def get_title(self, exclude_attributes: bool = False) -> str:
        attributes = [] if exclude_attributes else self.attributes
        material_type = f'{self.material} {self.object_type}' if self.material else self.object_type
        description = f'{" ".join(attributes)} {material_type}' if attributes else material_type
        return f'{self.name}, the {description}' if self.name else description
