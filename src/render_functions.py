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
    import liquids
    description = liquids.describe(game_map.tile_at(x, y))
    if description:
        names = f"{names}, {description}" if names else description

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
    from ui import Theme
    limit = canvas.chars(width) if width else 0
    if limit and len(names_at_mouse_location) > limit:
        names_at_mouse_location = names_at_mouse_location[: max(0, limit - 3)] + "..."

    canvas.print(x, y, names_at_mouse_location, fg=Theme.TITLE)


def tooltip_lines(entity) -> list:
    """What the hover tooltip says about one thing: its condition and attitude if it is a creature."""
    lines = []
    if getattr(entity, "category", None) is not None and entity.category.name == "UNIT":
        if not entity.is_alive:
            lines.append("dead")
        else:
            ratio = entity.hp / max(1, entity.max_hp)
            lines.append("unharmed" if ratio >= 0.99 else "wounded" if ratio > 0.4 else "badly wounded")
            ai = getattr(entity, "ai", None)
            if ai is not None and entity is not getattr(entity.engine, "player", None):
                lines.append("hostile" if getattr(ai, "is_hostile", False) else "keeps to itself")
    return lines


def render_tooltip(canvas: Canvas, engine: Engine) -> None:
    """A small framed box beside the cursor: the top thing's sprite and name centred, what else lies there, and any liquid."""
    import widgets
    from ui import Theme, CENTER
    x, y = engine.mouse_location
    game_map = engine.game_map
    if not game_map.in_bounds(x, y) or not game_map.is_visible(x, y):
        return
    things = [e for e in game_map.stack_at(x, y) if e is not engine.player]
    import liquids
    liquid = liquids.describe(game_map.tile_at(x, y))
    if not things and not liquid:
        return
    camera = engine.camera
    sx, sy = camera.to_screen(x, y)
    if not camera.on_screen(sx, sy):
        return
    width = 26
    top = things[0] if things else None
    lines = []
    if top is not None:
        lines.extend((line, Theme.DIM) for line in tooltip_lines(top))
        for other in things[1:5]:
            lines.append((other.get_title(), Theme.TEXT))
        if len(things) > 5:
            lines.append((f"and {len(things) - 5} more", Theme.DIM))
    if liquid:
        lines.append((liquid, Theme.TEXT))
    rows = sum(len(canvas.wrap(text, width - 2)) for text, _ in lines)
    height = 2 + (5 if top is not None else 1) + rows + 1
    bx = sx + 2 if sx + 2 + width <= 70 else sx - width - 1
    by = max(0, min(sy - 2, 40 - height))
    canvas.draw_frame(bx, by, width, height)
    row = by + 1
    if top is not None:
        widgets.sprite_slot(canvas, bx + (width - 4) // 2, row, top.sprite_id, top.color, getattr(top, "flipped", False))
        row += 4
        canvas.print(bx + width // 2, row, top.get_title()[: canvas.chars(width) - 4], fg=Theme.TITLE, alignment=CENTER)
        row += 1
    for text, fg in lines:
        for part in canvas.wrap(text, width - 2):
            canvas.print(bx + width // 2, row, part, fg=fg, alignment=CENTER)
            row += 1
