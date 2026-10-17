from __future__ import annotations

from entity import Entity, EntityCategory
from render_order import RenderOrder

from typing import Optional, TYPE_CHECKING
import random

from components.consumable import Fruit
from components.inventory import Inventory
from components.ai import PlantAI
from crafting import Branch
from species import ItemKind, PlantCategory, PlantSpecies, make_plant_species

from tile_types import roots

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
        self.last_upkeep: Optional[int] = None  # game time of the last growth update (simulation.upkeep)
        self.ai = PlantAI(self) if species.fruit else None  # only fruiting plants do anything per turn

    @property
    def growth_cycle(self) -> int:
        return self.kind.growth_cycle

    @property
    def fruit(self) -> Optional[ItemKind]:
        return self.kind.fruit

    @property
    def is_corpse(self) -> bool:
        return self.dead

    def on_added_to_map(self, game_map: GameMap) -> None:
        """Plants shape their tile: blocking/opaque flags, and the plant sprite in the remembered (dark) view."""
        dark = game_map.tile_at(self.x, self.y)['dark']
        game_map.modify_tile(
            self.x, self.y,
            transparent=not self.blocks_sight,
            walkable=not self.blocks_movement,
            dark=(self.sprite_id, self.flipped, dark['fg'], dark['bg']),
        )

    def handle_growth(self):
        """
        Growth happens every `self.growth_cycle` with a gaussian deviation.

        Every cycle, a fruit (and a branch) is added to `self.inventory`
        """
        if not self.fruit:
            return

        self.growth += 1
        if self.growth > self.avg_cycle:
            self.growth = 0

            # Drop some branches or fruit on the floor
            if self.inventory.is_full():
                item: Item = random.choice(self.inventory.items)
                adjacent_tiles = self.engine.get_adjacent_tiles(self.x, self.y)

                # Shuffle, so it doesn't drop everything on the same tile
                random.shuffle(adjacent_tiles)

                for tile in adjacent_tiles:
                    entities: list[Entity] = self.engine.game_map.get_entities_at_location(tile[0], tile[1])

                    if len(entities) >= 3:
                        continue

                    for entity in entities:
                        if entity.blocks_movement:
                            return
                    
                    self.inventory.drop(item, tile)
                    break
                
            self.inventory.add(Branch(self))
            if self.fruit:
                self.inventory.add(Fruit(self.inventory, self.fruit))

    def die(self, killer: Unit) -> None:
        self.dead = True
        self.blocks_movement = False
        self.blocks_sight = False
        self.ai = None
        self.render_order = RenderOrder.CORPSE
        self.parent.modify_tile(self.x, self.y, transparent=False, walkable=False, dark=roots.dark)


class Tree(Plant):
    def __init__(self, species: Optional[PlantSpecies] = None):
        Plant.__init__(self, species or make_plant_species(PlantCategory.TREE))


class Shrub(Plant):
    def __init__(self, species: Optional[PlantSpecies] = None):
        Plant.__init__(self, species or make_plant_species(PlantCategory.SHRUB))
