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
    canvas: Canvas, z: int, location: Tuple[int, int]
) -> None:
    """
    Render the layer the player is currently on (0 surface, below it caves, above it building floors), at the given location.
    """
    x, y = location

    canvas.print(x, y, layer_name(z))


def layer_name(z: int) -> str:
    """"Surface", "Cave 2" (two layers down) or "Floor 1" (the first storey above the ground)."""
    if z == 0:
        return "Surface"
    return f"Cave {-z}" if z < 0 else f"Floor {z}"

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
