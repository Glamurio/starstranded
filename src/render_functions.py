from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Engine
    from ui import Canvas
    from world import GameMap


def get_names_at_location(x: int, y: int, game_map: GameMap) -> str:
    if not game_map.is_visible(x, y):
        return ""
    # Topmost first: the order the stack is seen in (hidden clutter is listed too).
    names = ", ".join(entity.get_title() for entity in game_map.stack_at(x, y))

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
    canvas: Canvas, x: int, y: int, engine: Engine, width: int = 0
) -> None:
    """Names of everything on the tile under the cursor, topmost first; cut with "..." if wider than `width` cells."""
    mouse_x, mouse_y = engine.mouse_location

    names_at_mouse_location = get_names_at_location(
        x=mouse_x, y=mouse_y, game_map=engine.game_map
    )
    if width and len(names_at_mouse_location) > width:
        names_at_mouse_location = names_at_mouse_location[: max(0, width - 3)] + "..."

    canvas.print(x, y, names_at_mouse_location)
