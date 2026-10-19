from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Engine
    from ui import Canvas
    from world import GameMap


def rock_face_at(engine, x: int, y: int):
    """The material of the solid rock face at (x, y), or None if that tile is not one. Rock is mined, so it is a thing to look at."""
    import actions
    import resources
    game_map = engine.game_map
    game_world = engine.game_world
    if game_world.planet is None or not actions.is_rock_face(game_map, x, y):
        return None
    biome = resources.biome_key_at(game_world, game_map.z, x, y)
    return resources.wall_material(game_world.planet, game_world.master_seed, game_map.z, x, y, biome)


def rock_face_title(engine, rock) -> str:
    import lore
    return f"{lore.material_name(engine.game_world.run, rock)} wall"


def get_names_at_location(x: int, y: int, game_map: GameMap) -> str:
    if not game_map.is_visible(x, y):
        return ""
    # Topmost first: the order the stack is seen in (hidden clutter is listed too).
    names = ", ".join(entity.get_title() for entity in game_map.stack_at(x, y))
    import liquids
    description = liquids.describe(game_map.tile_at(x, y))
    if description:
        names = f"{names}, {description}" if names else description
    if not names and getattr(game_map, "engine", None) is not None:
        rock = rock_face_at(game_map.engine, x, y)
        if rock is not None:
            names = rock_face_title(game_map.engine, rock)

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
    canvas: Canvas, x: int, y: int, engine: Engine, width: int = 0, rows: int = 1
) -> None:
    """Names of everything on the tile under the cursor, topmost first; cut with "..." if wider than `width` cells."""
    mouse_x, mouse_y = engine.mouse_location

    names_at_mouse_location = get_names_at_location(
        x=mouse_x, y=mouse_y, game_map=engine.game_map
    )
    from ui import Theme
    limit = canvas.chars(width) if width else 0
    if rows > 1 and limit:
        lines = canvas.wrap(names_at_mouse_location, width)[:rows]
        if len(canvas.wrap(names_at_mouse_location, width)) > rows and lines:
            lines[-1] = lines[-1][: max(0, limit - 3)] + "..."
        for k, line in enumerate(lines):
            canvas.print(x, y + k, line, fg=Theme.TITLE)
        return
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
    rock = None if (things or liquid) else rock_face_at(engine, x, y)
    if not things and not liquid and rock is None:
        return
    camera = engine.camera
    sx, sy = camera.to_screen(x, y)
    if not camera.on_screen(sx, sy):
        return
    width = 26
    if rock is not None:
        tile = game_map.tile_at(x, y)["light"]
        bx = sx + 2 if sx + 2 + width <= camera.width else sx - width - 1
        by = max(0, min(sy - 2, camera.height - 11))
        canvas.draw_frame(bx, by, width, 11)
        widgets.sprite_slot(canvas, bx + (width - 4) // 2, by + 1, int(tile["sprite"]), tuple(int(c) for c in tile["fg"]))
        canvas.print(bx + width // 2, by + 5, rock_face_title(engine, rock)[: canvas.chars(width) - 4], fg=Theme.TITLE, alignment=CENTER)
        for k, text in enumerate(("Solid rock.", "Break it with a pickaxe.")):
            canvas.print(bx + width // 2, by + 6 + k, text, fg=Theme.DIM if k == 0 else Theme.TEXT, alignment=CENTER)
        return
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
    import lore
    english = lore.english_name(engine.game_world.planet, top.get_title()) if top is not None else None
    rows = sum(len(canvas.wrap(text, width - 2)) for text, _ in lines)
    height = 2 + (5 if top is not None else 1) + (1 if english else 0) + rows + 1
    bx = sx + 2 if sx + 2 + width <= camera.width else sx - width - 1
    by = max(0, min(sy - 2, camera.height - height))
    canvas.draw_frame(bx, by, width, height)
    row = by + 1
    if top is not None:
        widgets.sprite_slot(canvas, bx + (width - 4) // 2, row, top.sprite_id, top.color, getattr(top, "flipped", False))
        row += 4
        title = top.get_title()
        canvas.print(bx + width // 2, row, title[: canvas.chars(width) - 4], fg=Theme.TITLE, alignment=CENTER)
        row += 1
        if english:
            canvas.print(bx + width // 2, row, english[: canvas.chars(width) - 4], fg=Theme.DIM, alignment=CENTER, italic=True)
            row += 1
    for text, fg in lines:
        for part in canvas.wrap(text, width - 2):
            canvas.print(bx + width // 2, row, part, fg=fg, alignment=CENTER)
            row += 1
