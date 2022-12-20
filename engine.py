from __future__ import annotations

import lzma
import pickle

from typing import TYPE_CHECKING
from collections import namedtuple
import tcod

import numpy as np  # type: ignore

from tcod.console import Console
from tcod.map import compute_fov

import exceptions
from message_log import MessageLog
import render_functions
import color
from world import Point, distance

if TYPE_CHECKING:
    from entity import Actor
    from world import GameMap, GameWorld

# Global convenience methods borrows from Rift Wizard
Point = namedtuple("Point", "x y")

class Engine:
    game_map: GameMap
    game_world: GameWorld

    def __init__(self, player: Actor):
        self.message_log = MessageLog()
        self.mouse_location = (0, 0)
        self.player = player


    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)


    def handle_enemy_turns(self) -> None:
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass  # Ignore impossible action exceptions from AI.


    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height


    def can_see(self, x1, y1, x2, y2, radius: int):

        if distance(Point(x1, y1), Point(x2, y2)) > radius:
            return False

        for x, y in tcod.los.bresenham((x1, y1), (x2, y2)).tolist():
            if not self.game_map.tiles["transparent"][x][y]:
                return False

        return True


    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        self.game_map.visible[:] = compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=100,
        )
        # If a tile is "visible" it should be added to "explored".
        self.game_map.explored |= self.game_map.visible


    def render(self, console: Console) -> None:
        self.game_map.render(console)

        self.message_log.render(console=console, x=21, y=89, width=40, height=5)
        
        # HP
        render_functions.render_bar(
            console=console,
            current_value=self.player.unit.hp,
            maximum_value=self.player.unit.max_hp,
            x=0, y=89,
            total_width=20,
            bg_full=color.hp_bar_filled,
            bg_empty=color.hp_bar_empty,
            fg_color=color.bar_text,
            fg_text="HP"
        )

        # Hunger
        render_functions.render_bar(
            console=console,
            current_value=self.player.unit.hunger,
            maximum_value=self.player.unit.max_hunger,
            x=0, y=91,
            total_width=20,
            bg_full=color.hunger_bar_filled,
            bg_empty=color.hunger_bar_empty,
            fg_color=color.bar_text,
            fg_text="Hunger"
        )

        # Thirst
        render_functions.render_bar(
            console=console,
            current_value=self.player.unit.thirst,
            maximum_value=self.player.unit.max_thirst,
            x=0, y=93,
            total_width=20,
            bg_full=color.thirst_bar_filled,
            bg_empty=color.thirst_bar_empty,
            fg_color=color.bar_text,
            fg_text="Thirst"
        )


        render_functions.render_dungeon_level(
            console=console,
            dungeon_level=self.game_world.current_floor,
            location=(0, 87),
        )

        render_functions.render_names_at_mouse_location(
            console=console, x=21, y=85, engine=self
        )