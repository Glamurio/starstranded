from __future__ import annotations

import lzma
import pickle

from typing import TYPE_CHECKING
import tcod

from tcod.console import Console
from tcod.map import compute_fov

import exceptions
from message_log import MessageLog
import render_functions
import color
import math

if TYPE_CHECKING:
    from entity import Unit
    from world import GameMap, GameWorld


def distance(p1, p2, diag=True, euclidean=False):
    if diag:
        return max(abs(p1.x - p2.x), abs(p1.y - p2.y))
    if euclidean:
        return math.sqrt(math.pow((p1.x - p2.x), 2) + math.pow((p1.y - p2.y), 2))
    
    return abs(p1.x - p2.x) + abs(p1.y - p2.y)

class Engine:
    game_map: GameMap
    game_world: GameWorld

    def __init__(self, player: Unit):
        self.message_log = MessageLog()
        self.mouse_location = (0, 0)
        self.player = player


    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)


    def handle_enemy_turns(self) -> None:
        for entity in set(self.game_map.units) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass  # Ignore impossible action exceptions from AI.

    def can_see(self, x1, y1, x2, y2, radius: int):

        if distance(tcod.event.Point(x1, y1), tcod.event.Point(x2, y2)) > radius:
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
            radius=8,
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