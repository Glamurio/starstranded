from __future__ import annotations

from entity import Entity
from render_order import RenderOrder

from typing import TypeVar, TYPE_CHECKING
import color
import copy
import random
from components.consumable import Fruit
from components.inventory import Inventory
from components.ai import PlantAI

from utilities import map_codepoints, clamp, get_shade

if TYPE_CHECKING:
    from world import GameMap

T = TypeVar("T", bound="Entity")

class Tree(Entity):
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
        self.kind = "Tree"
        self.ai = PlantAI(self)
        self.inventory = Inventory(self, capacity=26)

        self.blocks_movement: bool = True
        self.blocks_sight: bool = True
        self.render_order = RenderOrder.TREE

        self.color = get_shade(color.green)
        self.sprite_pos = (0, 4)
        self.corpse_sprite_pos=(13, 5)

        self.mirrored = bool(random.getrandbits(1))
        char_info = map_codepoints(self.kind, self.sprite_pos, True, self.corpse_sprite_pos)
        self.char = char_info["sprite"]
        self.char_left = char_info["sprite"]
        self.char_right = char_info["mirror"]
        self.char_corpse = char_info["corpse"]

    def handle_growth(self):
        """
        Growth happens every `self.growth_cycle` with a gaussian deviation.

        Every cycle, `self.fruit` is added to `self.inventory`
        """
        self.growth += 1
        if self.growth > self.avg_cycle:
            self.growth = 0
            self.inventory.placeholders.append(Fruit)

    def spawn(self: T, game_map: GameMap, x: int, y: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = game_map
        game_map.entities.add(clone)
        game_map.tiles[x, y]['transparent'] = False
        game_map.tiles[x, y]['walkable'] = False
        return clone