from __future__ import annotations

from typing import Dict, Iterator, List, Tuple, TYPE_CHECKING, Callable

import tile_types
import random

import numpy as np  # type: ignore

import components.unit as units
import components.consumable as consumables

if TYPE_CHECKING:
    from world import World
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

    # Returns the factories (classes); callers construct one fresh instance per placement.
    return random.choices(
        entities, weights=entity_weighted_chance_values, k=number_of_entities
    )


def place_entities(world: World, floor_number: int, area: Tuple[int, int, int, int], reserved=()) -> None:
    """Spawn this floor's monsters and items at random tiles of `area` (a world rectangle, normally one chunk).

    Uses the global RNGs (chunk generation wraps this in `worldgen.seeded_rng`). A spawn is skipped (no retry, as
    before) unless the tile is walkable, free of blocking entities and not `reserved` (the player's start).
    """
    x0, y0, width, height = area
    number_of_monsters = random.randint(
        0, get_max_value_for_floor(max_monsters_by_floor, floor_number)
    )
    number_of_items = random.randint(
        0, get_max_value_for_floor(max_items_by_floor, floor_number)
    )

    monsters: List[Callable[[], Entity]] = get_entities_at_random(
        enemy_chances, number_of_monsters, floor_number
    )
    items: List[Callable[[], Entity]] = get_entities_at_random(
        item_chances, number_of_items, floor_number
    )
    for factory in monsters + items:
        x = random.randint(x0, x0 + width - 1)
        y = random.randint(y0, y0 + height - 1)
        if (x, y) in reserved:
            continue
        if world.is_walkable(x, y) and not world.is_blocked(x, y):
            world.add_entity(factory(), x, y)


# (left, right, up, down) neighbour pattern, as a 4-bit index l*8 + r*4 + u*2 + d -> variation name.
# Index 15 (surrounded) is special: randomly 'center' or the default sprite.
_VARIATION_NAMES = (
    "center_solo", "north_solo", "south_solo", "east_west",
    "west_solo", "north_west", "south_west", "west",
    "east_solo", "north_east", "south_east", "east",
    "north_south", "north", "south", None,
)


def neighbour_masks(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """For a [x, y] bool array: is the left/right/up/down neighbour True (outside the map counts as False)."""
    left = np.zeros_like(mask)
    right = np.zeros_like(mask)
    up = np.zeros_like(mask)
    down = np.zeros_like(mask)
    left[1:, :] = mask[:-1, :]
    right[:-1, :] = mask[1:, :]
    up[:, 1:] = mask[:, :-1]
    down[:, :-1] = mask[:, 1:]
    return left, right, up, down


def dilate(mask: np.ndarray) -> np.ndarray:
    """4-neighbour binary dilation (numpy only)."""
    left, right, up, down = neighbour_masks(mask)
    return mask | left | right | up | down


def replace_variations(tile: tile_types.Tile, landscape: np.ndarray, width: int, height: int):
    """
    Replaces all tiles of type `tile` within given `landscape` with the appropriate edge variations,
    chosen from which of the 4 neighbours are the same tile. Vectorised; same result as the old per-cell loop.

    Returns changed `landscape`
    """
    tile_map = landscape == tile.get_array()
    char_info: dict = tile.variation_ids
    default = tile.sprite
    left, right, up, down = neighbour_masks(tile_map)
    case = left.astype(np.uint8) * 8 + right * 4 + up * 2 + down
    lookup = np.array([char_info.get(name, default) if name else default for name in _VARIATION_NAMES], dtype=np.int32)
    chars = lookup[case]
    center = char_info.get('center', None)
    if center:
        surrounded = case == 15
        chars[surrounded & (np.random.random(case.shape) < 0.5)] = center
    landscape["dark"]["sprite"][tile_map] = chars[tile_map]
    landscape["light"]["sprite"][tile_map] = chars[tile_map]
    return landscape
