from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Engine
    from ui import Canvas
    from world import GameMap


def get_names_at_location(x: int, y: int, game_map: GameMap) -> str:
    if not game_map.in_bounds(x, y) or not game_map.visible[x, y]:
        return ""
    names = ", ".join(entity.get_title() for entity in game_map.get_entities_at_location(x, y))

    return names

def render_bar(
    canvas: Canvas,
    current_value: int,
    maximum_value: int,
    x: int, y: int,
    total_width: int,
    bg_full: Optional[Tuple[int, int, int]],
    bg_empty: Optional[Tuple[int, int, int]],
    fg_color: Optional[Tuple[int, int, int]],
    fg_text: str
) -> None:
    canvas.draw_bar(x, y, total_width, current_value, maximum_value, bg_full, bg_empty, fg_color, fg_text)

def render_dungeon_level(
    canvas: Canvas, dungeon_level: int, location: Tuple[int, int]
) -> None:
    """
    Render the level the player is currently on, at the given location.
    """
    x, y = location

    canvas.print(x, y, f"Floor: {dungeon_level}")

def render_names_at_mouse_location(
    canvas: Canvas, x: int, y: int, engine: Engine
) -> None:
    mouse_x, mouse_y = engine.mouse_location

    names_at_mouse_location = get_names_at_location(
        x=mouse_x, y=mouse_y, game_map=engine.game_map
    )

    canvas.print(x, y, names_at_mouse_location)
