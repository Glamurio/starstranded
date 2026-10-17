from __future__ import annotations

import lzma
import os
import pickle
import g

from typing import TYPE_CHECKING, List, Optional, Tuple
from tcod import libtcodpy
import tcod
import numpy as np # type: ignore

import exceptions
from config import DEFAULT_CONFIG, GameConfig
from message_log import MessageLog
import render_functions
import color
import math

if TYPE_CHECKING:
    from components.ai import BaseAI
    from entity import Entity
    from entity import Unit
    from world import GameMap, GameWorld


SAVE_VERSION = 2
"""Bump whenever the pickled object layout changes incompatibly. Version 1 = the pre-Phase-2 raw Engine pickle."""


class Engine:
    game_map: GameMap
    game_world: GameWorld

    def __init__(self, player: Unit, config: Optional[GameConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.message_log = MessageLog()
        self.mouse_location = tcod.event.Point(0, 0)
        self.player = player


    def save_as(self, filename: str) -> None:
        """Save this Engine as a versioned, compressed file (written to a temp file, then renamed: atomic)."""
        save_data = lzma.compress(pickle.dumps({"version": SAVE_VERSION, "engine": self}))
        tmp = f"{filename}.tmp"
        with open(tmp, "wb") as f:
            f.write(save_data)
        os.replace(tmp, filename)


    def handle_enemy_turns(self) -> None:
        for entity in list(self.game_map.actors):  # snapshot: AIs may add/remove entities
            if entity is not self.player and entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass  # Ignore impossible action exceptions from AI.

    def get_path_to(self, origin: Entity, dest_x: int, dest_y: int, ignore_obstacles: bool = False) -> List[Tuple[int, int]]:
        """
        Compute and return a path from `origin` to the target position (start excluded, destination included).

        If there is no valid path then returns an empty list.

        Unexplored tiles count as walkable, so the path does not reveal hidden terrain. Tiles occupied by
        movement-blocking entities cost +10 per blocker (a lower number means more enemies will crowd behind
        each other in hallways, a higher number means they take longer paths to surround the player).
        """
        game_map = origin.game_map
        if not game_map.in_bounds(dest_x, dest_y):
            return []

        cost = game_map.path_base_cost()
        if not ignore_obstacles:
            cost = np.where(cost > 0, cost + 10 * game_map.blocked, 0).astype(np.int32)

        graph = tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3)
        pathfinder = tcod.path.Pathfinder(graph)
        pathfinder.add_root((origin.x, origin.y))
        path: List[List[int]] = pathfinder.path_to((dest_x, dest_y))[1:].tolist()
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
        """Recompute the visible area based on the player's point of view,
        extended by any lit campfires whose light reaches into the player's vision."""
        from crafting import Campfire
        import numpy as np

        # Step 1: Compute base player FOV
        player_fov = tcod.map.compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=self.config.fov_radius,
            algorithm=libtcodpy.FOV_SYMMETRIC_SHADOWCAST
        )

        self.game_map.visible[:] = player_fov

        # Step 2: For each lit campfire, check if its light connects to player vision
        for entity in self.game_map.items:
            if not isinstance(entity, Campfire) or not entity.is_lit or not entity.is_placed:
                continue

            # Compute what the campfire illuminates
            campfire_fov = tcod.map.compute_fov(
                self.game_map.tiles["transparent"],
                (entity.x, entity.y),
                radius=entity.light_radius,
                algorithm=libtcodpy.FOV_SYMMETRIC_SHADOWCAST
            )

            # Check overlap: does ANY tile lit by the campfire fall within 
            # the player's current vision?
            overlap = np.logical_and(self.game_map.visible, campfire_fov)

            if overlap.any():
                # The campfire light connects to what the player sees.
                # Extend vision with campfire-lit tiles, but only those
                # that are reachable from the overlap zone.
                # 
                # Simple approach: merge the entire campfire FOV.
                # This works because compute_fov already limits the campfire
                # to tiles it can actually illuminate (respects walls).
                # The overlap check ensures we only do this when the player
                # can see at least part of the campfire's light.
                self.game_map.visible |= campfire_fov

        # Step 3: Explored tracking
        self.game_map.explored |= self.game_map.visible


    def render(self, console: tcod.console.Console) -> None:
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