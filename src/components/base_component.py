from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity
    from world import GameMap


class BaseComponent:
    parent: Entity  # Owning entity instance.

    @property
    def game_map(self) -> GameMap:
        return self.parent.game_map

    @property
    def engine(self) -> Engine:
        return self.game_map.engine