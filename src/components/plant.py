from __future__ import annotations

from entity import Entity
from render_order import RenderOrder

from typing import TypeVar, TYPE_CHECKING
import copy
import random
from components.consumable import Fruit
from components.inventory import Inventory
from components.ai import PlantAI
from tile_types import roots

from utilities import map_codepoints, clamp, get_random_color, get_gaussian_shade

if TYPE_CHECKING:
    from world import GameMap
    from components.unit import Unit

T = TypeVar("T", bound="Entity")

class Plant(Entity):
    def __init__(self):
        Entity.__init__(self)
        self.max_hp = 10
        self.hp = self.max_hp
        self.base_defense: int = 0
        self.growth: int = 0
        self.growth_cycle: int = 10
        avg_cycle = random.gauss(self.growth_cycle, 1)
        avg_cycle = clamp(avg_cycle, 0, self.growth_cycle * 2)
        self.avg_cycle: float = avg_cycle
        self.fruit: Fruit = Fruit
        self.ai = PlantAI(self)
        self.inventory = Inventory(self, capacity=10)

        self.color = get_random_color()

        self.blocks_movement: bool = False
        self.blocks_sight: bool = False
        self.render_order = RenderOrder.TREE

    def handle_growth(self):
        """
        Growth happens every `self.growth_cycle` with a gaussian deviation.

        Every cycle, `self.fruit` is added to `self.inventory`
        """
        self.growth += 1
        if self.growth > self.avg_cycle:
            self.growth = 0
            self.inventory.add(Fruit, True)

    def spawn(self: T, game_map: GameMap, x: int, y: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = game_map
        clone.shade = get_gaussian_shade(clone.color)#
        mirrored = bool(random.getrandbits(1))
        clone.mirrored = mirrored
        game_map.entities.add(clone)
        char = clone.char+1 if mirrored else clone.char
        tile = game_map.tiles[x, y]
        tile['transparent'] = not clone.blocks_sight
        tile['walkable'] = not clone.blocks_movement
        tile['dark'] = (char, tile['dark'][1], tile['dark'][2])
        return clone

    def die(self, killer: Unit) -> None:
        self.char = self.char_corpse
        self.blocks_movement = False
        self.blocks_sight = False
        self.ai = None
        self.render_order = RenderOrder.CORPSE
        tile = self.parent.tiles[self.x, self.y]
        tile['transparent'] = False
        tile['walkable'] = False
        tile['dark'] = (roots.codepoint, roots.dark_fg, roots.dark_bg)


class Tree(Plant):
    def __init__(self):
        Plant.__init__(self)
        self.growth_cycle: int = 10
        avg_cycle = random.gauss(self.growth_cycle, 1)
        avg_cycle = clamp(avg_cycle, 0, self.growth_cycle * 2)
        self.avg_cycle: float = avg_cycle
        self.kind = "Tree"

        self.blocks_movement: bool = True
        self.blocks_sight: bool = True

        self.possible_pos = [(0, 4), (1, 4), (2, 4), (3, 4), (4, 4)]
        self.sprite_pos = self.possible_pos[random.randint(0, len(self.possible_pos)-1)]
        self.corpse_sprite_pos=(13, 5)

        char_info = map_codepoints(self.kind, self.sprite_pos, True, self.corpse_sprite_pos)
        self.char = char_info["sprite"]
        self.char_left = char_info["sprite"]
        self.char_right = char_info["mirror"]
        self.char_corpse = char_info["corpse"]


class Shrub(Plant):
    def __init__(self):
        Plant.__init__(self)
        self.max_hp = 5
        self.hp = self.max_hp
        self.growth_cycle: int = 5
        avg_cycle = random.gauss(self.growth_cycle, 1)
        avg_cycle = clamp(avg_cycle, 0, self.growth_cycle * 2)
        self.avg_cycle: float = avg_cycle
        self.kind = "Shrub"
        self.ai = PlantAI(self)
        self.inventory = Inventory(self, capacity=10)

        self.blocks_movement: bool = False
        self.blocks_sight: bool = False
        self.render_order = RenderOrder.SHRUB

        self.sprite_pos = (5, 4)
        self.corpse_sprite_pos=(14, 4)

        char_info = map_codepoints(self.kind, self.sprite_pos, True, self.corpse_sprite_pos)
        self.char = char_info["sprite"]
        self.char_left = char_info["sprite"]
        self.char_right = char_info["mirror"]
        self.char_corpse = char_info["corpse"]