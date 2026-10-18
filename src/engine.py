from __future__ import annotations

import lzma
import os
import pickle

from typing import TYPE_CHECKING, List, Optional, Tuple
from tcod import libtcodpy
import tcod
import numpy as np # type: ignore

import exceptions
from entity import EntityCategory
from events import Point
from config import DEFAULT_CONFIG, GameConfig
from message_log import MessageLog
import render_functions
import color
import lighting
import math

if TYPE_CHECKING:
    from components.ai import BaseAI
    from entity import Entity
    from entity import Unit
    from ui import Canvas
    from world import GameMap, GameWorld


from savegame import SAVE_VERSION  # noqa: E402,F401  (re-exported; the save format lives in savegame.py)


PATH_MARGIN = 8
"""Extra tiles around a trip that the path search may use (see `Engine.get_path_to`)."""


class Engine:
    game_map: GameMap
    game_world: GameWorld

    def __init__(self, player: Unit, config: Optional[GameConfig] = None, session=None):
        import session as session_module
        self.session = session or session_module.detached()
        self.config = config or DEFAULT_CONFIG
        self.message_log = MessageLog()
        self.mouse_location = Point(0, 0)
        self.player = player
        self.continued = False   # True when loaded from the active save slot (its death deletes that save)


    def save_as(self, directory: str) -> None:
        """Save the game into `directory` (manifest + chunk files, written atomically; see `savegame`)."""
        import savegame
        savegame.save_game(self, directory)


    def handle_enemy_turns(self) -> None:
        """Run one turn of the tiered simulation (ACTIVE chunk fully, NEAR chunks on their interval)."""
        from simulation import run_turn
        run_turn(self)

    def get_path_to(self, origin: Entity, dest_x: int, dest_y: int, ignore_obstacles: bool = False) -> List[Tuple[int, int]]:
        """
        Compute and return a path from `origin` to the target position (start excluded, destination included).

        If there is no valid path then returns an empty list.

        The search runs on the stitched view window, cropped to `config.path_radius` tiles around the origin;
        destinations outside that square (or outside the loaded world) get no path. Unexplored tiles count as
        walkable, so the path does not reveal hidden terrain. Tiles occupied by movement-blocking entities cost +10
        per blocker (a lower number means more enemies will crowd behind each other in hallways, a higher number
        means they take longer paths to surround the player).
        """
        world = origin.game_map
        if not world.in_bounds(dest_x, dest_y):
            return []
        window = world.window.ensure()
        if not window.contains(origin.x, origin.y):
            return []
        # Search only as far as the trip needs: a short trip crops to a small square (the search cost grows with its
        # area), a long one is capped at `path_radius`. The margin leaves room to walk around obstacles.
        trip = max(abs(dest_x - origin.x), abs(dest_y - origin.y))
        radius = min(self.config.path_radius, 2 * trip + PATH_MARGIN)
        wx0, wy0, ww, wh = window.rect
        x0, y0 = max(wx0, origin.x - radius), max(wy0, origin.y - radius)
        x1, y1 = min(wx0 + ww, origin.x + radius + 1), min(wy0 + wh, origin.y + radius + 1)
        if not (x0 <= dest_x < x1 and y0 <= dest_y < y1):
            return []
        rect = (x0, y0, x1 - x0, y1 - y0)
        crop = (slice(x0 - wx0, x1 - wx0), slice(y0 - wy0, y1 - wy0))
        explored = world.region("explored", rect)
        cost = (window.in_bounds[crop] & (window.walkable[crop] | ~explored)).astype(np.int32)
        if not ignore_obstacles:
            cost = np.where(cost > 0, cost + 10 * world.region("blocked", rect), 0).astype(np.int32)
        if origin is not self.player:  # creatures do not wade through acid (the player cannot tell it from other liquid)
            cost[world.region("liquid", rect) == 3] = 0

        if getattr(origin, "avoids_liquid", False):  # liquid-averse units path around every liquid tile
            cost[world.region("liquid", rect) != 0] = 0

        graph = tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3)
        pathfinder = tcod.path.Pathfinder(graph)
        pathfinder.add_root((origin.x - x0, origin.y - y0))
        path: List[List[int]] = pathfinder.path_to((dest_x - x0, dest_y - y0))[1:].tolist()
        return [(index[0] + x0, index[1] + y0) for index in path]

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
        if self.distance(Point(x1, y1), Point(x2, y2)) > radius-2:
            return False

        for x, y in tcod.los.bresenham((x1, y1), (x2, y2)).tolist():
            if not self.game_map.is_transparent(x, y):
                return False

        return True

    def can_move(self, dest_x: int, dest_y: int) -> bool:
        """Return True if actor can move to target location."""

        if not self.game_map.in_bounds(dest_x, dest_y):
            # Destination is out of bounds.
            return False
        if not self.game_map.is_walkable(dest_x, dest_y):
            # Destination is blocked by a tile.
            return False
        if self.game_map.get_entities_at_location(dest_x, dest_y, True):
            # Destination is blocked by an entity.
            return False

        return True

    def discover_recipes(self) -> None:
        """Standing next to things teaches what you could make from them (never lets a failure interrupt the turn)."""
        try:
            import crafting
            run = self.game_world.run
            found = crafting.discover(self.player, run)
            if found:
                names = ", ".join(r.name.lower() for r in found[:3]) + (f" and {len(found) - 3} more" if len(found) > 3 else "")
                self.message_log.add_message(f"You work out what you could make from this: {names} ('R').", color.menu_text)
        except Exception:
            pass

    def update_fov(self) -> None:
        """Recompute what the player sees (ambient light by time of day plus light sources, see `lighting`)
        on the stitched view window; then mark it explored."""
        world = self.game_map
        window = world.window.ensure()

        visible, lit = lighting.compute_visibility(self)
        window.visible[:] = visible
        window.lit[:] = lit

        # what was seen stays explored
        world.mark_explored()
        self.discover_recipes()

    @property
    def camera(self):
        """The map viewport's camera: centred on the player (clamped for bounded maps)."""
        from view import Camera
        return Camera.follow(self.game_map, self.player.x, self.player.y)

    def render(self, canvas: Canvas) -> None:
        """Draw the map, the bottom panel (status bars, names under the cursor, message log) and the side panel."""
        self.game_map.render(canvas)

        player = self.player
        for row, (value, maximum, full, empty, label) in zip((40, 42, 44), (
            (player.hp, player.max_hp, color.hp_bar_filled, color.hp_bar_empty, "HP"),
            (player.hunger, player.max_hunger, color.hunger_bar_filled, color.hunger_bar_empty, "Hunger"),
            (player.thirst, player.max_thirst, color.thirst_bar_filled, color.thirst_bar_empty, "Thirst"),
        )):
            render_functions.render_bar(
                canvas, current_value=value, maximum_value=maximum, x=0, y=row, total_width=20,
                bg_full=full, bg_empty=empty, fg_color=color.bar_text, fg_text=label,
            )

        render_functions.render_names_at_mouse_location(canvas, x=21, y=40, engine=self, width=canvas.width - 21)
        self.message_log.render(canvas, x=21, y=41, width=canvas.width - 21, height=4)

        render_functions.render_dungeon_level(canvas, self.game_world.current_z, (71, 1))
        day, time = lighting.clock_text(self.game_world.current_time, self.config).split(", ")
        canvas.print(71, 2, day)
        canvas.print(71, 3, time)
        canvas.print(71, 4, f"X {player.x}")
        canvas.print(71, 5, f"Y {player.y}")
        row = 6
        if player.poison > 0:
            canvas.print(71, row, "Poisoned", fg=color.enemy_atk)
            row += 1
        import survival
        for text, shade in survival.status_lines(self):
            canvas.print(71, row, text[:9], fg=shade)
            row += 1