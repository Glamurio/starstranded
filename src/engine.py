from __future__ import annotations

import lzma
import pickle
import g

from typing import TYPE_CHECKING, List, Tuple
import tcod
import numpy as np # type: ignore

from tcod.console import Console
from tcod.map import compute_fov

import exceptions
from message_log import MessageLog
import render_functions
import color
import math

if TYPE_CHECKING:
    from components.ai import BaseAI
    from entity import Unit
    from world import GameMap, GameWorld


class Engine:
    game_map: GameMap
    game_world: GameWorld

    def __init__(self, player: Unit):
        self.message_log = MessageLog()
        self.mouse_location = tcod.event.Point(0, 0)
        self.player = player


    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)


    def handle_enemy_turns(self) -> None:
        for entity in set(self.game_map.entities) - {self.player}:
            if hasattr(entity, "ai") and entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass  # Ignore impossible action exceptions from AI.

    def get_path_to(self, ai: BaseAI, dest_x: int, dest_y: int, ignore_obstacles = False) -> List[Tuple[int, int]]:
        """
        Compute and return a path to the target position.

        If there is no valid path then returns an empty list.
        """
        if not self.game_map.in_bounds(dest_x, dest_y):
            return

        # Copy the walkable array.
        walkable = np.array(ai.entity.game_map.tiles["walkable"])
        # Copy an array of all unexplored tile
        unexplored = np.logical_not(ai.entity.game_map.explored)

        # Set up the cost so that unexplored tiles do not factor in the terrain that they have
        # This prevents the player from knowing if an unexplored terrain is walkable or not
        cost = np.logical_or(walkable, unexplored, dtype=np.int8).astype(int)

        for entity in ai.entity.game_map.entities:
            # Check that an entity blocks movement and the cost isn't zero (blocking.)
            if not ignore_obstacles and entity.blocks_movement and cost[entity.x, entity.y]:
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

    def distance(self, p1: tuple[int, int], p2: tuple[int, int], diag=True, euclidean=False):
        if diag:
            return max(abs(p1[0] - p2[0]), abs(p1[1] - p2[1]))
        if euclidean:
            return math.sqrt(math.pow((p1[0] - p2[0]), 2) + math.pow((p1[1] - p2[1]), 2))
        
        return abs(p1[0] - p1[0]) + abs(p2[1] - p2[1])

    def get_adjacent_tiles(self, x: int, y: int):
        """Returns adjacent tiles to coordinates, so long as they are within map bounds."""
        adjacent_tiles = [(x-1, y-1), (x, y-1), (x+1, y-1), (x-1, y), (x+1, y), (x-1, y+1), (x, y+1), (x+1, y+1)]
        return [tile for tile in adjacent_tiles if self.game_map.in_bounds(tile[0], tile[1])]

    def get_closest_tile(self, coordinates: List[tuple[int, int, int]], x: int , y: int):
        closest_coordinate = coordinates[0]
        closest_distance = math.sqrt((x - closest_coordinate[0])**2 + (y - closest_coordinate[1])**2)
        
        for coord in coordinates:
            distance = math.sqrt((x - coord[0])**2 + (y - coord[1])**2)
            if distance < closest_distance:
                closest_coordinate = coord
                closest_distance = distance
                
        return closest_coordinate

    def can_see(self, x1, y1, x2, y2, radius: int = 8):
        if self.distance(tcod.event.Point(x1, y1), tcod.event.Point(x2, y2)) > radius-2:
            return False

        for x, y in tcod.los.bresenham((x1, y1), (x2, y2)).tolist():
            if not self.game_map.tiles["transparent"][x][y]:
                return False

        return True

    def can_move(self, dest_x: int, dest_y: int) -> bool:
        """Return True if actor can move to target location."""

        if not self.game_map.in_bounds(dest_x, dest_y):
            # Destination is out of bounds.
            return False
        if not self.game_map.tiles["walkable"][dest_x, dest_y]:
            # Destination is blocked by a tile.
            return False
        if self.game_map.get_entities_at_location(dest_x, dest_y, True):
            # Destination is blocked by an entity.
            return False

        return True

    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        self.game_map.visible[:] = compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=100,
            algorithm=tcod.FOV_SYMMETRIC_SHADOWCAST
        )
        # If a tile is "visible" it should be added to "explored".
        self.game_map.explored |= self.game_map.visible


    def render(self, console: Console) -> None:
        self.game_map.render(console)

        self.message_log.render(console=console, x=21, y=49, width=40, height=5)
        
        # HP
        render_functions.render_bar(
            console=console,
            current_value=self.player.hp,
            maximum_value=self.player.max_hp,
            x=0, y=40,
            total_width=20,
            bg_full=color.hp_bar_filled,
            bg_empty=color.hp_bar_empty,
            fg_color=color.bar_text,
            fg_text="HP"
        )

        # Hunger
        render_functions.render_bar(
            console=console,
            current_value=self.player.hunger,
            maximum_value=self.player.max_hunger,
            x=0, y=42,
            total_width=20,
            bg_full=color.hunger_bar_filled,
            bg_empty=color.hunger_bar_empty,
            fg_color=color.bar_text,
            fg_text="Hunger"
        )

        # Thirst
        render_functions.render_bar(
            console=console,
            current_value=self.player.thirst,
            maximum_value=self.player.max_thirst,
            x=0, y=44,
            total_width=20,
            bg_full=color.thirst_bar_filled,
            bg_empty=color.thirst_bar_empty,
            fg_color=color.bar_text,
            fg_text="Thirst"
        )

        render_functions.render_dungeon_level(
            console=console,
            dungeon_level=self.game_world.current_floor,
            location=(0, 47),
        )

        render_functions.render_names_at_mouse_location(
            console=console, x=21, y=42, engine=self
        )