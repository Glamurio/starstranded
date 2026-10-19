from __future__ import annotations

from entity import Entity, EntityCategory
from render_order import RenderOrder

from typing import Optional, TYPE_CHECKING
import random

from components.consumable import Fruit
from components.inventory import Inventory
from crafting import Branch
from items import Stuff
import species as defs
from species import ItemKind, PlantCategory, PlantSpecies, STUMP, STUMP_SPRITES, make_plant_species


from utilities import clamp, get_gaussian_shade

if TYPE_CHECKING:
    from world import GameMap
    from components.unit import Unit
    from entity import Item


class Plant(Entity):
    """A rooted plant. Static data (sprite, name, fruit, growth cycle) lives in `kind: PlantSpecies`."""

    category = EntityCategory.PLANT
    has_inventory = True
    kind: PlantSpecies

    def __init__(self, species: PlantSpecies):
        Entity.__init__(self, species)
        self.max_hp = species.max_hp
        self.hp = self.max_hp
        self.base_defense: int = 0
        self.growth: int = 0
        avg_cycle = random.gauss(species.growth_cycle, 1)
        self.avg_cycle: float = clamp(avg_cycle, 0, species.growth_cycle * 2)
        self.inventory = Inventory(self, capacity=species.inventory_capacity)
        self.color = species.color
        self.shade = get_gaussian_shade(self.color)
        self.mirrored = bool(random.getrandbits(1))
        self.dead = False
        self._ground = None  # (walkable, transparent, dark) of the tile before this plant shaped it
        self.due: Optional[int] = None  # game time of the next completed growth cycle (simulation.PlantQueue)
        self.last_upkeep: Optional[int] = None  # game time of the last growth update (simulation.upkeep)
        self.ai = None  # plants have no per-turn behaviour: growth is event-driven (`simulation.PlantQueue`)

    @property
    def growth_cycle(self) -> int:
        return self.kind.growth_cycle

    @property
    def fruit(self) -> Optional[ItemKind]:
        return self.kind.fruit

    @property
    def prominence(self) -> int:
        """How loudly it is drawn: 2 something to pick right now, 1 a tree or fruit-bearer, 0 decoration (see `atlas.FOLIAGE_LEVELS`)."""
        if not self.dead and self.inventory is not None and (self.inventory.items or self.inventory.placeholders):
            return 2
        return 1 if self.fruit or self.kind.category is defs.PlantCategory.TREE else 0

    @property
    def is_corpse(self) -> bool:
        return self.dead

    def on_added_to_map(self, game_map: GameMap) -> None:
        """Plants shape their tile: blocking/opaque flags, and the plant sprite in the remembered (dark) view."""
        tile = game_map.tile_at(self.x, self.y)
        dark = tile['dark']
        if self._ground is None:  # remembered so a felled plant can give the tile back
            self._ground = (bool(tile['walkable']), bool(tile['transparent']), dark.item())
        game_map.modify_tile(
            self.x, self.y,
            transparent=not self.blocks_sight,
            walkable=not self.blocks_movement,
            dark=(self.sprite_id, self.flipped, dark['fg'], dark['bg']),
        )

    def steps_to_harvest(self) -> int:
        """Growth steps (one per `simulation.GROWTH_PERIOD` turns) until the next cycle completes."""
        return int(self.avg_cycle) + 1 - self.growth

    growth_bonus = 0.0  # extra growth per step once a `crop_growth` unit has tended (harvested) this plant
    growth_carry = 0.0

    def handle_growth(self):
        """One growth step; when the cycle completes a branch and a fruit are added (see `complete_cycle`)."""
        if not self.fruit:
            return
        self.growth += 1
        self.growth_carry += self.growth_bonus
        if self.growth_carry >= 1.0:
            self.growth_carry -= 1.0
            self.growth += 1
        if self.growth > self.avg_cycle:
            self.growth = 0
            self.complete_cycle()

    SHEDS = False
    """Plants do not let fruit fall by themselves for now (it piled up on the ground and hid everything else). The route stays: set
    this True (or call `shed`) when fruit dropping, seeds and regrowth become a feature."""

    SHED_CHANCE = 0.03
    """A full plant has this chance per growth cycle to let one of its items fall (so a tree holds its fruit and branches until
    somebody takes them: it practically never sheds)."""

    def complete_cycle(self) -> None:
        """A growth cycle finished: a plant that is full may (rarely) drop one of its items on a free, dry, walkable
        neighbouring tile, then it grows a branch and a fruit (if there is room)."""
        if self.SHEDS and self.inventory.is_full() and random.random() < self.SHED_CHANCE:
            self.shed()
        # `Inventory.add` throws away what does not fit, so do not build (and colour-jitter) items for nothing
        if not self.inventory.is_full():
            self.inventory.add(self.yield_piece())
        if self.fruit and not self.inventory.is_full():
            self.inventory.add(Fruit(self.inventory, self.fruit))

    def shed(self) -> None:
        """Let one held item fall on a free, dry, walkable neighbouring tile (the future route for seeds and fallen fruit)."""
        world = self.parent
        if world is not None and self.inventory.items:
            item: Item = random.choice(self.inventory.items)
            adjacent_tiles = self.engine.get_adjacent_tiles(self.x, self.y)
            random.shuffle(adjacent_tiles)  # so it doesn't drop everything on the same tile
            for tile in adjacent_tiles:
                ground = world.tile_at(tile[0], tile[1])
                if ground is None or not ground["walkable"] or ground["liquid"] or ground["stairs"]:
                    continue                   # never into solid rock, water or a staircase
                entities = world.get_entities_at_location(tile[0], tile[1])
                if len(entities) >= 3 or any(e.blocks_movement for e in entities):
                    continue
                self.inventory.drop(item, tile)
                break

    def yield_piece(self):
        """What this plant gives when cut or when its cycle completes: fibre for fibrous shrubs, else a piece of its wood."""
        fiber = getattr(self.kind, "fiber", None)
        if fiber is not None:
            return Stuff(defs.PIECE_FIBER, fiber)
        return Branch(self)

    def resistances(self):
        return self.kind.resistances

    def handle_health(self, amount: int, attacker: Optional[Entity] = None) -> None:
        self.hp = clamp(self.hp + amount, 0, self.max_hp)
        if self.hp == 0 and not self.dead:
            self.die(attacker)

    def die(self, killer: Optional[Unit] = None) -> None:
        """Felled: the plant leaves the world, its fruit and branches fall to the ground and the tile opens up."""
        world = self.parent
        self.dead = True
        self.due = None
        if world is None:
            return
        x, y = self.x, self.y
        loot = list(self.inventory.items) + [self.yield_piece() for _ in range(2)]
        world.remove_entity(self)
        if self._ground is not None:
            walkable, transparent, dark = self._ground
            world.modify_tile(x, y, walkable=walkable, transparent=transparent, dark=dark)
        if self.kind.sprite in STUMP_SPRITES:
            stump = Stump(self)
            world.add_entity(stump, x, y)
        for item in loot:
            if item.parent is self.inventory:
                self.inventory.items.remove(item)
            item.parent = None
            world.add_entity(item, x, y)
        self.inventory.contents = self.inventory.items + self.inventory.placeholders
        player = getattr(world.engine, "player", None)
        if player is not None and world.is_visible(x, y):
            world.engine.message_log.add_message(f"The {self.get_title()} is cut down.")


class Stump(Entity):
    """What a felled tree leaves behind: scenery, walked over freely, not pickable."""

    object_type = "Stump"

    def __init__(self, tree: Optional[Plant] = None):
        Entity.__init__(self, STUMP)
        if tree is not None:
            self.color = self.shade = tree.shade
            self.mirrored = tree.mirrored

    def get_title(self, exclude_attributes: bool = False) -> str:
        return "Stump"


class Flower(Plant):
    """A small ground plant that bears one bloom: grab it with G, and a new one opens each growth cycle. Walked over freely."""

    def __init__(self, species: PlantSpecies):
        Plant.__init__(self, species)
        self.inventory.add(Fruit(self.inventory, species.fruit))   # it starts in bloom

    def yield_piece(self):
        return Fruit(self.inventory, self.kind.fruit)

    def complete_cycle(self) -> None:
        if not self.inventory.is_full():
            self.inventory.add(Fruit(self.inventory, self.kind.fruit))


class Tree(Plant):
    def __init__(self, species: Optional[PlantSpecies] = None):
        Plant.__init__(self, species or make_plant_species(PlantCategory.TREE))


class Shrub(Plant):
    def __init__(self, species: Optional[PlantSpecies] = None):
        Plant.__init__(self, species or make_plant_species(PlantCategory.SHRUB))
