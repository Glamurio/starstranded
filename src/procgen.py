from __future__ import annotations

from typing import Dict, Iterator, List, Tuple, TYPE_CHECKING
from world import GameMap, GameWorld

import tile_types
import random
import tcod

import numpy as np  # type: ignore
import matplotlib.pyplot as plt #just for visual

import color
import entity_factories

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

max_items_by_floor = [
    (1, 4),
    (4, 8),
]


max_monsters_by_floor = [
    (1, 6),
    (4, 12),
    (6, 18),
]


item_chances: Dict[int, List[Tuple[Entity, int]]] = {
    0: [(entity_factories.health_potion, 35)],
    2: [(entity_factories.confusion_scroll, 10)],
    4: [(entity_factories.lightning_scroll, 25), (entity_factories.sword, 5)],
    6: [(entity_factories.fireball_scroll, 25), (entity_factories.chain_mail, 15)],
}

enemy_chances: Dict[int, List[Tuple[Entity, int]]] = {
    0: [(entity_factories.orc, 80)],
    3: [(entity_factories.troll, 15)],
    5: [(entity_factories.troll, 30)],
    7: [(entity_factories.troll, 60)],
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
    weighted_chances_by_floor: Dict[int, List[Tuple[Entity, int]]],
    number_of_entities: int,
    floor: int,
) -> List[Entity]:
    entity_weighted_chances = {}

    for key, values in weighted_chances_by_floor.items():
        if key > floor:
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

        if not any(entity.x == x and entity.y == y for entity in map.entities):
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
    dungeon = GameMap(world, landscape, engine, map_width, map_height, entities=[player])

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


def generate_noise(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    engine: Engine,
    world: GameWorld,
) -> GameMap:

    noise = tcod.noise.Noise(
        dimensions=2,
        algorithm=tcod.noise.Algorithm.PERLIN,
    )
    samples = noise[tcod.noise.grid(shape=(map_width, map_height), scale=0.05, origin=(0, 0))]
    noise = tcod.noise.Noise(
            dimensions=2,
            algorithm=tcod.noise.Algorithm.PERLIN,
    )
    samples = (samples + noise[tcod.noise.grid(shape=(map_width, map_height), scale=0.25, origin=(0, 0))])/2

    def value_range(a, low, high):
        return np.logical_and(a>low , a<=high)

    def construct_landscape(limits, tiles, samples: np.ndarray):
        assert(len(limits) == len(tiles)+1)
        out_shape = list(samples.shape)
        landscape = np.full(out_shape, fill_value=tile_types.wall, order="F", dtype=tile_types.tile_dt)
        for i in range(len(limits)-1):
            landscape[value_range(samples, limits[i], limits[i+1])] = tiles[i]
        return landscape

    colors = [np.array([0, 0, 0.5]), np.array([0, 0, 1]), np.array([0, 1., 0]), np.array([0.5, 0.5, 0.5]), np.array([1., 1., 1.])]
    color_limits = [-1.1, -0.4, -0.2, 0.1, 0.3, 1.1]
    tiles = [tile_types.water, tile_types.floor, tile_types.wall]
    tile_limits = [-1.1, -0.2, 0.3, 1.1]
    
    # landscape = construct_landscape(color_limits, colors, samples)
    landscape = construct_landscape(tile_limits, tiles, samples)

    player = engine.player
    map = GameMap(world, landscape, engine, map_width, map_height, entities=[player])

    player.place(0, 0, map)
    place_entities(map, engine.game_world.current_floor)

    return map
    
    plt.imshow(landscape, vmin=0, vmax=255)
    plt.savefig('figure.jpg')
