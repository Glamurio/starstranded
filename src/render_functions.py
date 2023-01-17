from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from tcod import Console
    from engine import Engine
    from world import GameMap


def get_names_at_location(x: int, y: int, game_map: GameMap) -> str:
    if not game_map.in_bounds(x, y) or not game_map.visible[x, y]:
        return ""
    names = ", ".join(
        entity.get_title() for entity in game_map.entities if entity.x == x and entity.y == y
    )

    return names

def render_bar(
    console: Console,
    current_value: int,
    maximum_value: int,
    x: int, y: int,
    total_width: int,
    bg_full: Optional[Tuple[int, int, int]],
    bg_empty: Optional[Tuple[int, int, int]],
    fg_color: Optional[Tuple[int, int, int]],
    fg_text: str
) -> None:
    bar_width = int(float(current_value) / maximum_value * total_width)

    console.draw_rect(x=x, y=y, width=total_width, height=1, ch=1, bg=bg_empty)

    if bar_width > 0:
        console.draw_rect(
            x=x, y=y, width=bar_width, height=1, ch=1, bg=bg_full
        )

    console.print(
        x=x+1, y=y, string=f"{fg_text}: {current_value}/{maximum_value}", fg=fg_color
    )

def render_dungeon_level(
    console: Console, dungeon_level: int, location: Tuple[int, int]
) -> None:
    """
    Render the level the player is currently on, at the given location.
    """
    x, y = location

    console.print(x=x, y=y, string=f"Dungeon level: {dungeon_level}")

def render_names_at_mouse_location(
    console: Console, x: int, y: int, engine: Engine
) -> None:
    mouse_x, mouse_y = engine.mouse_location

    names_at_mouse_location = get_names_at_location(
        x=mouse_x, y=mouse_y, game_map=engine.game_map
    )

    console.print(x=x, y=y, string=names_at_mouse_location)