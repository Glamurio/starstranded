# Utility functions
from __future__ import annotations

import os
import tcod
import numpy as np # type: ignore
import g
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from components.ai import BaseAI
    from engine import Engine

def get_data(path: str) -> str:
    """Return the path to a resource in the libtcod data directory,"""
    SCRIPT_DIR = os.path.dirname(__file__)
    DATA_DIR = os.path.join(SCRIPT_DIR, "../libtcod/data")
    assert os.path.exists(DATA_DIR), (
        "Data directory is missing," " did you forget to run `git submodule update --init`?"
    )
    return os.path.join(DATA_DIR, path)

def clamp(n, smallest, largest): return max(smallest, min(n, largest))

def is_mouse_in_rectangle(mouse: tcod.event.MouseState, point: tcod.event.Point, width: int, height: int) -> bool:
    """
    Check if current mouse position is within a rectangle of given `width` and `height` and return True or False.

    `point` indicates the center of the rectangle.
    """
    mouse_pt = mouse.tile

    return (point.x - width // 2) < (mouse_pt.x) and (point.x + width // 2) > (mouse_pt.x) \
        and (point.y - height // 2) < (mouse_pt.y) and (point.y + height // 2) > (mouse_pt.y)

def get_path_to(engine: Engine, ai: BaseAI, dest_x: int, dest_y: int) -> List[Tuple[int, int]]:
    """
    Compute and return a path to the target position.

    If there is no valid path then returns an empty list.
    """
    if not engine.game_map.in_bounds(dest_x, dest_y):
        return

    # Copy the walkable array.
    cost = np.array(ai.entity.gamemap.tiles["walkable"], dtype=np.int8)

    for entity in ai.entity.gamemap.entities:
        # Check that an entity blocks movement and the cost isn't zero (blocking.)
        if entity.blocks_movement and cost[entity.x, entity.y]:
            # Add to the cost of a blocked position.
            # A lower number means more enemies will crowd behind each other in
            # hallways.  A higher number means enemies will take longer paths in
            # order to surround the player.
            cost[entity.x, entity.y] += 10

    # Create a graph from the cost array and pass that graph to a new pathfinder.
    graph = tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3)
    pathfinder = tcod.path.Pathfinder(graph)

    pathfinder.add_root((ai.entity.x, ai.entity.y))  # Start position.

    # Compute the path to the destination and remove the starting point.
    path: List[List[int]] = pathfinder.path_to((dest_x, dest_y))[1:].tolist()
    # Convert from List[List[int]] to List[Tuple[int, int]].
    return [(index[0], index[1]) for index in path]

def can_move(engine: Engine, dest_x: int, dest_y: int) -> bool:
    """Return True if actor can move to target location."""

    if not engine.game_map.in_bounds(dest_x, dest_y):
        # Destination is out of bounds.
        return False
    if not engine.game_map.tiles["walkable"][dest_x, dest_y]:
        # Destination is blocked by a tile.
        return False
    if engine.game_map.get_blocking_entity_at_location(dest_x, dest_y):
        # Destination is blocked by an entity.
        return False

    return True

def text_input(buffer: str = "") -> str:
    for event in tcod.event.wait():
        match event:
            case tcod.event.KeyDown(sym=tcod.eventKeySym.KeySym.RETURN):
                return buffer
            case tcod.event.KeyDown(sym=tcod.eventKeySym.BACKSPACE):
                buffer = buffer[:-1]
            case tcod.event.TextInput(text=text):
                buffer += text

def generate_name(origin: str):
    path = Path("./data/namegen").resolve()
    file_names = []
    for file in os.listdir(path):
        file_names.append(file)
        if file.find(".cfg") > 0:
            tcod.namegen_parse(os.path.join(path, file))

    # get the sets list
    name_sets = tcod.namegen_get_sets()
    for name_set in name_sets:
        if not origin.casefold() in name_set.casefold():
            continue

        return tcod.namegen_generate(name_set)
    return tcod.namegen_generate(name_sets[0])

def map_sprite(x: int, y: int) -> int:
    """
    Function, which remaps entity to sprite.
    Returns the first vacant codepoint inside.
    """
    for i in range(0xE001, 0xF8FF+1):
        if i in g.mapped_chars:
            continue

        g.mapped_chars.append(i)
        g.global_tileset.remap(i, x, y)

        return i