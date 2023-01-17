from __future__ import annotations

from typing import Dict, Iterator, List, Tuple, TYPE_CHECKING, Callable
from world import GameMap, GameWorld

import tile_types
import random
import tcod
import g

import numpy as np  # type: ignore
import matplotlib.pyplot as plt #just for visual

import components.unit as units
import components.consumable as consumables
import components.plant

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

max_items_by_floor = [
    (1, 4),
    (4, 8),
]
max_monsters_by_floor = [
    (1, 10),
    (4, 12),
    (6, 18),
]


item_chances: Dict[int, List[Tuple[Callable[[], Entity], int]]] = {
    0: [(consumables.HealthPotion, 35)],
    # 2: [(entity_funities.confusion_scroll, 10)],
    # 4: [(entity_funities.lightning_scroll, 25), (entity_funities.sword, 5)],
    # 6: [(entity_funities.fireball_scroll, 25), (entity_funities.chain_mail, 15)],
}
enemy_chances: Dict[int, List[Tuple[Callable[[], Entity], int]]] = {
    0: [(units.Animal, 100)],
    # 3: [(entity_funities.troll, 15)],
    # 5: [(entity_funities.troll, 30)],
    # 7: [(entity_funities.troll, 60)],
}
plant_chances: Dict[int, List[Tuple[Callable[[], Entity], int]]] = {
    0: [(components.plant.Tree, 100)],
    # 3: [(entity_funities.troll, 15)],
    # 5: [(entity_funities.troll, 30)],
    # 7: [(entity_funities.troll, 60)],
}


def get_max_value_for_floor(
    max_value_by_floor: List[Tuple[int, int]], floor: int
) -> int:
    current_value = 0

    for floor_minimum, value in max_value_by_floor:
        if floor_minimum > floor:
            break
        else:
            current_value = value

    return current_value


def get_entities_at_random(
    weighted_chances_by_floor: Dict[int, List[Tuple[Callable[[], Entity], int]]],
    number_of_entities: int,
    cur_floor: int,
) -> List[Entity]:
    entity_weighted_chances = {}

    for floor_id, values in weighted_chances_by_floor.items():
        if floor_id > cur_floor:
            break
        else:
            for value in values:
                entity = value[0]
                weighted_chance = value[1]

                entity_weighted_chances[entity] = weighted_chance
    
    entities = list(entity_weighted_chances.keys())
    entity_weighted_chance_values = list(entity_weighted_chances.values())

    chosen_entities = random.choices(
        entities, weights=entity_weighted_chance_values, k=number_of_entities
    )
    # TODO: Change spawning of enemies to not be clones and remove this
    chosen_entities = [e() for e in chosen_entities]
    return chosen_entities


class RectangularRoom:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)

        return center_x, center_y

    @property
    def inner(self) -> Tuple[slice, slice]:
        """Return the inner area of this room as a 2D array index."""
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: RectangularRoom) -> bool:
        """Return True if this room overlaps with another RectangularRoom."""
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )


def place_entities(map: GameMap, floor_number: int, room: RectangularRoom = None) -> None:
    number_of_monsters = random.randint(
        0, get_max_value_for_floor(max_monsters_by_floor, floor_number)
    )
    number_of_items = random.randint(
        0, get_max_value_for_floor(max_items_by_floor, floor_number)
    )

    monsters: List[Entity] = get_entities_at_random(
        enemy_chances, number_of_monsters, floor_number
    )
    items: List[Entity] = get_entities_at_random(
        item_chances, number_of_items, floor_number
    )
    for entity in monsters + items:
        if room:
            x = random.randint(room.x1 + 1, room.x2 - 1)
            y = random.randint(room.y1 + 1, room.y2 - 1)
        else:
            x = random.randint(0, map.width - 1)
            y = random.randint(0, map.height - 1)

        unwalkable = np.logical_not(map.tiles[x, y]["walkable"])
        if not any(unwalkable and entity.x == x and entity.y == y for entity in map.entities):
            entity.spawn(map, x, y)


def tunnel_between(
    start: Tuple[int, int], end: Tuple[int, int]
) -> Iterator[Tuple[int, int]]:
    """Return an L-shaped tunnel between these two points."""
    x1, y1 = start
    x2, y2 = end
    if random.random() < 0.5:  # 50% chance.
        # Move horizontally, then vertically.
        corner_x, corner_y = x2, y1
    else:
        # Move vertically, then horizontally.
        corner_x, corner_y = x1, y2

    # Generate the coordinates for this tunnel.
    for x, y in tcod.los.bresenham((x1, y1), (corner_x, corner_y)).tolist():
        yield x, y
    for x, y in tcod.los.bresenham((corner_x, corner_y), (x2, y2)).tolist():
        yield x, y


def generate_map(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    engine: Engine,
    world: GameWorld,
) -> GameMap:
    """Generate a new dungeon map."""
    player = engine.player
    landscape = np.full((map_width, map_height), fill_value=tile_types.wall, order="F")
    dungeon = GameMap(world, landscape, engine, width=map_width, height=map_height, entities=[player])

    rooms: List[RectangularRoom] = []
    center_of_last_room = (0, 0)

    for r in range(max_rooms):
        room_width = random.randint(room_min_size, room_max_size)
        room_height = random.randint(room_min_size, room_max_size)

        x = random.randint(0, dungeon.width - room_width - 1)
        y = random.randint(0, dungeon.height - room_height - 1)

        # "RectangularRoom" class makes rectangles easier to work with
        new_room = RectangularRoom(x, y, room_width, room_height)

        # Run through the other rooms and see if they intersect with this one.
        if any(new_room.intersects(other_room) for other_room in rooms):
            continue  # This room intersects, so go to the next attempt.
        # If there are no intersections then the room is valid.

        # Dig out this rooms inner area.
        dungeon.tiles[new_room.inner] = tile_types.floor

        if len(rooms) == 0:
            # The first room, where the player starts.
            player.place(*new_room.center, dungeon)
        else:  # All rooms after the first.
            # Dig out a tunnel between this room and the previous one.
            for x, y in tunnel_between(rooms[-1].center, new_room.center):
                dungeon.tiles[x, y] = tile_types.floor

            center_of_last_room = new_room.center

        place_entities(dungeon, engine.game_world.current_floor, room = new_room)

        dungeon.tiles[center_of_last_room] = tile_types.down_stairs
        dungeon.downstairs_location = center_of_last_room

        # Finally, append the new room to the list.
        rooms.append(new_room)

    return dungeon

def replace_variations(tile: tile_types.Tile, landscape: np.ndarray, width: int, height: int):
    """
    Replaces all tiles of type `tile` within given `landscape` with the appropriate variations
    
    Returns changed `landscape`
    """
    tile_map = landscape == tile.get_array()
    char_info = g.char_dict[tile.object_type]
    default = char_info['sprite']
    for x, row in enumerate(tile_map):
        for y, is_tile in enumerate(row):
            if not is_tile:
                continue
            coords: List[List] = [[x-1, y, "left", False], [x+1, y, "right", False], [x, y-1, "up", False], [x, y+1, "down", False]]
            for coord in coords:
                if 0 <= coord[0] < width and 0 <= coord[1] < height and tile_map[coord[0]][coord[1]]:
                    coord[3] = True

            cases = [case[3] for case in coords]
            match cases:
                case [False, False, False, False]:
                    tile_char = char_info['solo'] if char_info['solo'] else default
                case [False, False, False, True]:
                    tile_char = char_info['north'] if char_info['north'] else default
                case [False, False, True, False]:
                    tile_char = char_info['south'] if char_info['south'] else default
                case [False, False, True, True]:
                    tile_char = default
                case [False, True, False, False]:
                    tile_char = char_info['west'] if char_info['west'] else default
                case [False, True, False, True]:
                    tile_char = char_info['north_west'] if char_info['north_west'] else default
                case [False, True, True, False]:
                    tile_char = char_info['south_west'] if char_info['south_west'] else default
                case [False, True, True, True]:
                    tile_char = char_info['west'] if char_info['west'] else default
                case [True, False, False, False]:
                    tile_char = char_info['east'] if char_info['east'] else default
                case [True, False, False, True]:
                    tile_char = char_info['north_east'] if char_info['north_east'] else default
                case [True, False, True, False]:
                    tile_char = char_info['south_east'] if char_info['south_east'] else default
                case [True, False, True, True]:
                    tile_char = char_info['east'] if char_info['east'] else default
                case [True, True, False, False]:
                    tile_char = default
                case [True, True, False, True]:
                    tile_char = char_info['north'] if char_info['north'] else default
                case [True, True, True, False]:
                    tile_char = char_info['south'] if char_info['south'] else default
                case [True, True, True, True]:
                    tile_char = char_info['wave'] if char_info['wave'] and bool(random.getrandbits(1)) else default

            tile_dark = (tile_char, tile.dark_fg, tile.dark_bg)
            tile_light = (tile_char, tile.light_fg, tile.light_bg)
            tile_result = (tile.walkable, tile.transparent, tile_dark, tile_light)
            
            landscape[x][y] = tile_result
    return landscape

def spawn_vegetation(tree: components.plant.Tree, shrub: components.plant.Shrub, map: GameMap, tree_map: np.ndarray):
    """Spawns trees and shrubs `map` via `tree_map`"""
    for x, row in enumerate(tree_map):
        for y, tile in enumerate(row):
            if tile:
                plant = tree if random.random() > 0.2 else shrub
                plant.spawn(map, x, y)

def generate_noise(
    map_width: int,
    map_height: int,
    engine: Engine,
    world: GameWorld,
) -> GameMap:

    height_noise = tcod.noise.Noise(
        dimensions=2,
        algorithm=tcod.noise.Algorithm.PERLIN,
    )
    height_samples = height_noise[tcod.noise.grid(shape=(map_height, map_width), scale=0.05, origin=(0, 0))]
    height_noise = tcod.noise.Noise(
            dimensions=2,
            algorithm=tcod.noise.Algorithm.PERLIN,
    )
    height_samples = (height_samples + height_noise[tcod.noise.grid(shape=(map_height, map_width), scale=0.25, origin=(0, 0))])/2

    vegetation_noise = tcod.noise.Noise(
        dimensions=2,
        algorithm=tcod.noise.Algorithm.PERLIN,
    )
    vegetation_samples = vegetation_noise[tcod.noise.grid(shape=(map_height, map_width), scale=0.05, origin=(0, 0))]
    vegetation_noise = tcod.noise.Noise(
        dimensions=2,
        algorithm=tcod.noise.Algorithm.PERLIN,
    )
    vegetation_samples = vegetation_noise[tcod.noise.grid(shape=(map_height, map_width), scale=0.1, origin=(0, 0))]

    def value_range(a, low, high):
        return np.logical_and(a>low , a<=high)

    def construct_landscape(limits, tiles, samples: np.ndarray):
        """Function to generate height map"""
        assert(len(limits) == len(tiles)+1)
        out_shape = list(samples.shape)
        landscape = np.full(out_shape, fill_value=tile_types.wall.get_array(), order="F", dtype=tile_types.tile_dt)
        for i in range(len(limits)-1):
            landscape[value_range(samples, limits[i], limits[i+1])] = tiles[i]
        return landscape

    def plant_trees(samples: np.ndarray, landscape: np.ndarray, adjust: float = 0.1):
        """Function to generate map for vegetation"""
        out_shape = list(samples.shape)
        random_map = np.random.rand(out_shape[0], out_shape[1])
        lake_map = landscape == tile_types.water.get_array()
        tree_map = samples > random_map + adjust
        tree_map = np.logical_and(tree_map, np.logical_not(lake_map))
        landscape[tree_map] = tile_types.roots.get_array()
        return landscape

    def plant_trees_old(samples: np.ndarray, landscape: np.ndarray, adjust: float = 0.1):
        """Function to generate map for vegetation"""
        out_shape = list(samples.shape) + [3]
        if not landscape:
            landscape = np.zeros(out_shape, order="F")
        random_map = np.random.rand(out_shape[0], out_shape[1])
        tree_map = samples > random_map + adjust
        landscape[tree_map] = np.array([0, 0.8, 0])
        return landscape

    def construct_old(limits, tiles, samples: np.ndarray):
        assert(len(limits) == len(tiles)+1)
        out_shape = list(samples.shape) + [3]
        landscape = np.zeros(out_shape, order="F")
        for i in range(len(limits)-1):
            landscape[value_range(samples, limits[i], limits[i+1])] = tiles[i]
        return landscape

    # color_limits = [-1.1, 0, 1.1]
    # colors = [np.array([0, 0, 0.5]), np.array([0, 0, 1])]

    height_limits = [-1.1, -0.3, 0.3, 1.1]
    height_tiles = [tile_types.water.get_array(), tile_types.floor.get_array(), tile_types.wall.get_array()]
    landscape = construct_landscape(height_limits, height_tiles, height_samples)
            
    # Add variations
    landscape = replace_variations(tile_types.water, landscape, map_width, map_height)

    # Add vegetation
    landscape = plant_trees(vegetation_samples, landscape)

    player = engine.player
    map = GameMap(world, landscape, engine, width=map_width, height=map_height, entities=[player])

    tree_map: np.ndarray = landscape == tile_types.roots.get_array()
    spawn_vegetation(components.plant.Tree(), components.plant.Shrub(), map, tree_map)


    # Get random player position
    x = random.randint(0, map.width - 1)
    y = random.randint(0, map.height - 1)
    walkable = map.tiles[x, y]["walkable"]
    while not walkable:
        x = random.randint(0, map.width - 1)
        y = random.randint(0, map.height - 1)
        walkable = map.tiles[x, y]["walkable"]
        
    player.place(x, y, map)
    place_entities(map, engine.game_world.current_floor)
    
    # plt.imshow(vegetation, vmin=0, vmax=255)
    # plt.savefig('figure.jpg')

    return map
