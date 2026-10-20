from __future__ import annotations

import os

from typing import Callable, List, Optional, Tuple, TYPE_CHECKING, Union

import layout
import events
import pygame

from events import Key, Mod, MouseButton, Point
from ui import CENTER

import actions
import color
import exceptions
from utilities import is_mouse_in_rectangle
from entity import Item, Entity
from components.equippable import Equippable

if TYPE_CHECKING:
    from ui import Canvas
    from engine import Engine
    from session import Session
    from components.unit import Unit
    from components.inventory import Inventory
    from crafting import Recipe

MOVE_KEYS = {
    # Arrow keys.
    Key.UP: (0, -1),
    Key.DOWN: (0, 1),
    Key.LEFT: (-1, 0),
    Key.RIGHT: (1, 0),
    Key.HOME: (-1, -1),
    Key.END: (-1, 1),
    Key.PAGEUP: (1, -1),
    Key.PAGEDOWN: (1, 1),
    # Numpad keys.
    Key.KP_1: (-1, 1),
    Key.KP_2: (0, 1),
    Key.KP_3: (1, 1),
    Key.KP_4: (-1, 0),
    Key.KP_6: (1, 0),
    Key.KP_7: (-1, -1),
    Key.KP_8: (0, -1),
    Key.KP_9: (1, -1),
    # Vi keys.
    # Key.h: (-1, 0),
    # Key.j: (0, 1),
    # Key.k: (0, -1),
    # Key.l: (1, 0),
    # Key.y: (-1, -1),
    # Key.u: (1, -1),
    # Key.b: (-1, 1),
    # Key.n: (1, 1),
}

CONFIRM_KEYS = {
    Key.RETURN,
    Key.KP_ENTER,
}

WAIT_KEYS = {
    Key.SPACE,
    Key.KP_5,
    Key.CLEAR,
}

def screen_to_world(engine: Engine, position) -> Optional[Tuple[int, int]]:
    """World tile under screen cell `position`, or None outside the map viewport."""
    camera = engine.camera
    sx, sy = int(position[0]), int(position[1])
    if not camera.on_screen(sx, sy):
        return None
    return camera.to_world(sx, sy)


def edge_exit(camera, x: int, y: int) -> Tuple[int, int]:
    """Outward direction (-1/0/1 per axis) when world tile (x, y) lies on the outermost ring of the viewport, else (0, 0)."""
    sx, sy = camera.to_screen(x, y)
    dx = -1 if sx == 0 else 1 if sx == camera.width - 1 else 0
    dy = -1 if sy == 0 else 1 if sy == camera.height - 1 else 0
    return dx, dy


def walk_cancelled() -> bool:
    """Has the player pressed a key or clicked since the last step? Any of them stops a walk that repeats (a click to walk, a long
    path); the key or click that stops it is used up, so it does not also start something."""
    stop = False
    for event in pygame.event.get((pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN)):
        if event.type == pygame.MOUSEBUTTONDOWN or event.key not in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LALT, pygame.K_RALT):
            stop = True
    return stop


def travel_target(engine: Engine, x: int, y: int) -> Tuple[int, int]:
    """Where a left click on tile (x, y) sends the player. A click on the edge ring of the view means "leave this
    screen that way": the goal is the tile just past the edge, so mouse-only play walks into the next chunk, which
    then loads and scrolls into view. Falls back to the clicked tile when the tile beyond cannot be reached."""
    dx, dy = edge_exit(engine.camera, x, y)
    if (dx, dy) == (0, 0):
        return x, y
    beyond = (x + dx, y + dy)
    player = engine.player
    if engine.game_map.in_bounds(*beyond) and engine.get_path_to(player, *beyond):
        return beyond
    return x, y


def highlight_world(engine: Engine, canvas: Canvas, x: int, y: int, wash=color.white, alpha: int = 110) -> None:
    """Highlight world tile (x, y) if it is in the map viewport."""
    camera = engine.camera
    sx, sy = camera.to_screen(x, y)
    if camera.on_screen(sx, sy):
        canvas.highlight(sx, sy, wash, alpha)


def draw_entity_icon(canvas: Canvas, x: int, y: int, entity: Entity) -> None:
    """Draw the entity's sprite, tinted with its own colour, into cell (x, y) (menus use this as a list icon)."""
    canvas.sprite(x, y, entity.sprite_id, entity.color, entity.flipped)


ActionOrHandler = Union[actions.Action, "BaseEventHandler"]
"""An event handler return value which can trigger an action or switch active handlers.

If a handler is returned then it will become the active handler for future events.
If an action is returned it will be attempted and if it's valid then
MainGameEventHandler will become the active handler.
"""


class BaseEventHandler(events.EventDispatch):

    def __init__(self, session: Optional[Session] = None) -> None:
        super().__init__()
        import session as session_module
        self._session = session or session_module.detached()
        self.on_init()

    @property
    def session(self) -> Session:
        """The UI session (window, canvas, handler stack); engine handlers use their engine's."""
        return self._session

    def on_init(self):
        """Function that runs after init"""
        pass

    def handle_events(self, event: events.Event) -> BaseEventHandler:
        """Handle an event and return the next active event handler."""
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        assert not isinstance(state, actions.Action), f"{self!r} can not handle actions."
        return self

    def on_render(self, canvas: Canvas) -> None:
        raise NotImplementedError()

    def ev_quit(self, event: events.Quit) -> Optional[actions.Action]:
        raise SystemExit()

class PopupMessage(BaseEventHandler):
    """Display a popup text window."""

    def __init__(self, parent_handler: BaseEventHandler, text: str):
        self.parent = parent_handler
        self.text = text

    def on_render(self, canvas: Canvas) -> None:
        """Render the parent and dim the result, then a small window with the message on top."""
        from ui import Theme
        self.parent.on_render(canvas)
        canvas.dim()
        lines = canvas.wrap(self.text, 36)
        height = len(lines) + 6
        x, y = (canvas.width - 40) // 2, (canvas.height - height) // 2
        ix, iy, iw, ih = canvas.window(x, y, 40, height, hints=[("any key", "continue")])
        for k, line in enumerate(lines):
            canvas.print(ix + iw // 2, iy + 1 + k, line, fg=Theme.TEXT, alignment=CENTER)

    def ev_keydown(self, event: events.KeyDown) -> Optional[BaseEventHandler]:
        """Any key returns to the parent handler."""
        return self.parent

    def ev_mousebuttondown(self, event: events.MouseButtonDown) -> Optional[BaseEventHandler]:
        return self.parent   # so does any click


class EventHandler(BaseEventHandler):
    def __init__(self, engine: Engine):
        self.engine = engine

    @property
    def session(self) -> Session:
        return self.engine.session

    def reset_to_handler(self, handler: EventHandler):
        """Resets active handler to handler provided"""
        self.session.reset(handler)

    def resolve_handler(self) -> EventHandler:
        """Resolves and returns current handler and switches to the next in stack"""
        handler = self.session.handlers.pop()

        if not len(self.session.handlers):
            self.reset_to_handler(MainGameEventHandler(self.engine))

        return handler
            

    def handle_events(self, event: events.Event) -> BaseEventHandler:
        """Handle events for input handlers with an engine."""
        try:
            action_or_state = self.dispatch(event)
        except exceptions.Impossible as exc:   # e.g. using a crafting material from the inventory menu
            self.engine.message_log.add_message(exc.args[0] if exc.args else "You cannot do that.", color.impossible)
            action_or_state = None

        if isinstance(action_or_state, BaseEventHandler):
            self.session.push(action_or_state) # Add handler to stack

        if isinstance(action_or_state, actions.Action) and (
                self.handle_action(action_or_state)
                or not self.engine.player.is_alive or self.engine.game_world.run.ending is not None):
            # A valid action was performed (or it failed half-way after time had passed and the run ended).
            if self.engine.game_world.run.ending is not None:
                import screens
                return self._take_over(screens.EndingHandler(self.engine))
            if not self.engine.player.is_alive:
                # The player was killed sometime during or after the action.
                return self._take_over(GameOverEventHandler(self.engine))
            elif self.engine.player.level.requires_level_up:
                return self._take_over(LevelUpEventHandler(self.engine))

            if isinstance(self, SelectIndexHandler) and self in self.session.handlers:
                # a targeting screen that has just done its job (place, scan, fire ...) is finished: back to the map
                self.reset_to_handler(MainGameEventHandler(self.engine))
            if not len(self.session.handlers):
                self.reset_to_handler(MainGameEventHandler(self.engine)) # Return to the main handler.

        if len(self.session.handlers):
            return self.session.handlers[-1] # Switch to most recent handler in stack

        return self

    def _take_over(self, handler):
        """Make `handler` the only screen: until it is done the map handler below it must not see another key."""
        self.session.reset(handler)
        return handler

    def handle_action(self, action: Optional[actions.Action]) -> bool:
        """Handle actions returned from event methods.

        Returns True if the action will advance a turn.
        """
        if action is None:
            return None

        try:
            # Actions return `True` for repeat
            repeat = action.perform()
            while repeat and self.engine.player.is_alive and self.engine.game_world.run.ending is None:
                if walk_cancelled():
                    self.engine.message_log.add_message("You stop.")
                    break
                repeat = action.perform()
                # time.sleep(0.05)
                self.session.render(self)
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
            return False  # Skip enemy turn on exceptions.

        return True

    def ev_mousemotion(self, event: events.MouseMotion) -> None:
        world_xy = screen_to_world(self.engine, event.position)
        if world_xy is not None and self.engine.game_map.in_bounds(*world_xy):
            self.engine.mouse_location = Point(*world_xy)

    def on_render(self, canvas: Canvas) -> None:
        self.engine.render(canvas)


class AskUserEventHandler(EventHandler):
    """Handles user input for actions which require special input."""

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        """By default any key exits this input handler."""
        if event.sym in {  # Ignore specific keys
            Key.LSHIFT,
            Key.RSHIFT,
            Key.LCTRL,
            Key.RCTRL,
            Key.LALT,
            Key.RALT,
            Key.UP,
            Key.DOWN
        }:
            return None
        if event.sym in CONFIRM_KEYS:
            return None
        return self.on_exit()

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """By default a right click cancels (a left click is left to the screen: windows are clickable now)."""
        if event.button == MouseButton.RIGHT:
            return self.on_exit()
        return None

    def on_exit(self) -> Optional[ActionOrHandler]:
        """Called when the user is trying to exit or cancel an action.

        By default this simply resolves the current active handler
        """
        self.resolve_handler()
        

class Panel(AskUserEventHandler):
    """Base of the windowed screens: draws the game behind, then a framed window (optionally with the shared tab row), and
    switches to the next screen with TAB. Subclasses draw their content into the area `frame()` returns."""

    TITLE = ""
    WIDTH = 58      # (the map view's width: the side panel with the log stays visible)
    HEIGHT = 36
    TABBED = False
    HINTS: list = [("Esc", "close")]
    X = 0
    Y = 2

    def frame(self, canvas: Canvas, hints=None, title: Optional[str] = None):
        import widgets
        prev = self.session.handlers.index(self) - 1 if self in self.session.handlers else -1
        parent = self.session.handlers[prev] if prev >= 0 else None
        (parent or super()).on_render(canvas)
        tabs = widgets.tab_titles() if self.TABBED else None
        hints = list(hints if hints is not None else self.HINTS)
        if self.TABBED:
            hints.insert(-1, ("Tab", "next screen"))
        return canvas.window(self.X, self.Y, self.WIDTH, self.HEIGHT, title=title or self.TITLE, hints=hints, tabs=tabs,
                             active=widgets.tab_index(self) if self.TABBED else 0)

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        if self.TABBED and event.sym == Key.TAB:
            import widgets
            return widgets.next_screen(self, -1 if event.mod & (Mod.LSHIFT | Mod.RSHIFT) else 1)
        return super().ev_keydown(event)

    def ev_mousebuttondown(self, event: events.MouseButtonDown) -> Optional[ActionOrHandler]:
        """A click on an entry of the screen's list (`self.list`) selects it; elsewhere it does nothing."""
        view = getattr(self, "list", None)
        if view is not None and event.button == MouseButton.LEFT:
            index = view.row_at(int(event.position[0]) * 24 + 12, int(event.position[1]) * 24 + 12)
            if index is not None and not view.rows[index].header:
                view.selected = index
        return super().ev_mousebuttondown(event)


class CodexHandler(Panel):
    """The codex (a journal): everything the scanner and your work have taught you, by category, with what is known on the
    right. Up/down chooses an entry."""

    TITLE = "Codex"
    TABBED = True
    HINTS = [("a-z", "choose"), ("Up/Down", "browse"), ("Esc", "close")]

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.page = 0
        self.list = None

    def pages(self):
        import lore
        entries = lore.codex_entries(self.engine)
        run = self.engine.game_world.run
        out = []
        for category, items in entries.items():
            lines = []
            for subject, title, facts in items:
                lines.append(title)
                lines.extend("  " + l for l in lore.describe_lines(run, subject, facts))
            out.append((category, lines or ["Nothing learned yet."]))
        return out

    def _rows(self):
        import lore
        import widgets
        entries = lore.codex_entries(self.engine)
        pictures = lore.codex_pictures(self.engine)
        rows = []
        for category, items in entries.items():
            if not items:
                continue
            rows.append(widgets.Row(category, header=True))
            for subject, title, facts in items:
                picture = pictures.get(subject)
                rows.append(widgets.Row(title, icon=(picture[0], picture[1], False) if picture else None, data=(subject, title, facts)))
        return rows

    def on_render(self, canvas: Canvas) -> None:
        import lore
        import widgets
        from ui import Theme
        ix, iy, iw, ih = self.frame(canvas)
        rows = self._rows()
        if not rows:
            canvas.print(ix, iy + 1, "Nothing learned yet.", fg=Theme.TITLE)
            widgets.text_block(canvas, ix, iy + 3, iw, 5, ["Scan things with S, or work with materials, to learn about them."])
            return
        if self.list is None:
            self.list = widgets.ListView(rows)
        else:
            self.list.set_rows(rows)
        list_w = 26
        self.list.draw(canvas, ix, iy, list_w, ih)
        dx = ix + list_w + 1
        pygame.draw.line(canvas.surface, Theme.BORDER_DIM, (dx * 24 - 12, iy * 24), (dx * 24 - 12, (iy + ih) * 24), 1)
        current = self.list.current
        if current is not None:
            subject, title, facts = current.data
            picture = lore.codex_pictures(self.engine).get(subject)
            top = iy
            if picture is not None:                                  # the thing itself, large, above its name
                widgets.sprite_slot(canvas, dx, iy, picture[0], picture[1], size=6)
                top = iy + 7
            canvas.print(dx + (7 if picture is not None else 0), iy + (2 if picture is not None else 0), title, fg=Theme.TITLE)
            lines = []
            description = lore.description_of(self.engine, subject)
            if description:
                lines += [(description, Theme.TEXT), ("", Theme.TEXT)]
            lines += [(l, Theme.DIM if "???" in l else Theme.TEXT) for l in lore.describe_lines(self.engine.game_world.run, subject, facts)]
            drops = lore.drops_of(self.engine, subject)
            if drops:
                lines += [("", Theme.TEXT), ("Drops", Theme.TITLE)] + [(text, Theme.TEXT if known else Theme.DIM) for text, known in drops]
            widgets.text_block(canvas, dx, top + (0 if picture is not None else 2), iw - list_w - 1, ih - (top - iy) - (0 if picture is not None else 2), lines)

    def ev_keydown(self, event):
        if self.list is not None:
            if event.sym == Key.UP:
                self.list.move(-1)
                return None
            if event.sym == Key.DOWN:
                self.list.move(1)
                return None
            if Key.A <= event.sym <= Key.Z:
                self.list.select_key(chr(event.sym - Key.A + ord("a")))
                return None
        if event.sym in (Key.LEFT, Key.RIGHT):
            return None
        return super().ev_keydown(event)


class PickupHandler(AskUserEventHandler):

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.target_location = Point(0, 0)

    def on_render(self, canvas: Canvas) -> None:
        super().on_render(canvas)

        player = self.engine.player
        mouse_x, mouse_y = self.engine.mouse_location
        distance = self.engine.distance((player.x, player.y), (mouse_x, mouse_y))
        path = self.engine.get_path_to(player, mouse_x, mouse_y)
        tile = path.pop(0) if path else (player.x, player.y)
        if distance <= 1:
            self.target_location = Point(mouse_x, mouse_y)
            highlight_world(self.engine, canvas, mouse_x, mouse_y, color.white)
        else:
            self.target_location = Point(tile[0], tile[1])
            highlight_world(self.engine, canvas, tile[0], tile[1], color.white)

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """By default any mouse click exits this input handler."""
        if event.button == MouseButton.LEFT:
            targets = self.engine.game_map.stack_at(self.target_location.x, self.target_location.y)
            return self.on_tile_selected(targets)

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        if event.sym == Key.G or event.sym == Key.RETURN:
            targets = self.engine.game_map.stack_at(self.target_location.x, self.target_location.y)
            return self.on_tile_selected(targets)

    def on_tile_selected(self, targets: List[Entity]) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item."""

        targets = [t for t in targets if t is not self.engine.player and not getattr(t, "decal", False)]
        if not targets:
            return self.on_exit()
        if len(targets) == 1:
            target = targets[0]
            if isinstance(target, Item):
                self.resolve_handler()   # the pick-up prompt is done
                return actions.PickupAction(self.engine.player, target)

        self.resolve_handler()
        return InventoryLootHandler(self.engine, self.engine.player, entities=targets)
        


class CharacterScreenEventHandler(Panel):
    """The character sheet: who you are, how you are doing, what you are trained in and what your people can do."""

    TITLE = "Character"
    TABBED = True
    hover_row = None
    skill_rows = None

    def ev_mousemotion(self, event: events.MouseMotion) -> None:
        cx, cy = int(event.position[0]), int(event.position[1])
        self.hover_row = None
        if self.skill_rows:
            dx, width, top, count = self.skill_rows
            if dx <= cx < dx + width and top <= cy < top + count:
                self.hover_row = cy

    def _draw_skill_tip(self, canvas: Canvas, x: int, y: int, width: int, hovered) -> None:
        import widgets
        from ui import Theme
        canvas.print(x, y, "Skill", fg=Theme.TITLE)
        if hovered is None:
            widgets.text_block(canvas, x, y + 1, width, 6, [("Hover a skill to see what it does and how to raise it.", Theme.DIM)])
            return
        skill, level = hovered
        what, how, progress = _skill_tip_lines(skill, level, self.engine.player.skill_practice.get(skill, 0))
        widgets.text_block(canvas, x, y + 1, width, 14, [(what, Theme.TEXT), ("", Theme.TEXT), (how, Theme.TEXT), ("", Theme.TEXT), (progress, Theme.DIM)])

    def on_render(self, canvas: Canvas) -> None:
        import widgets
        import capabilities
        from ui import Theme
        ix, iy, iw, ih = self.frame(canvas)
        p = self.engine.player
        run = self.engine.game_world.run
        widgets.sprite_slot(canvas, ix, iy, p.sprite_id, p.color, getattr(p, "flipped", False))
        canvas.print(ix + 5, iy, p.name or "Survivor", fg=Theme.TITLE)
        canvas.print(ix + 5, iy + 1, str(p.species), fg=Theme.TEXT)
        canvas.print(ix + 5, iy + 2, (getattr(p, "background", None) or "").replace("_", " "), fg=Theme.DIM)
        sponsor = getattr(run, "sponsor", None)
        if sponsor:
            canvas.print(ix + 5, iy + 3, f"sponsor: {sponsor.replace('_', ' ')}", fg=Theme.DIM)
        stats = [
            ("Level", f"{p.level.current_level}"),
            ("Experience", f"{p.level.current_xp} / {p.level.experience_to_next_level}"),
            ("Hit points", f"{p.hp} / {p.max_hp}"),
            ("Attack", f"{p.power}"),
            ("Defence", f"{p.defense}"),
            ("Hunger", f"{p.hunger} / 100"),
            ("Thirst", f"{p.thirst} / 100"),
            ("Credits", f"{run.credits}"),
        ]
        canvas.print(ix, iy + 5, "Statistics", fg=Theme.TITLE)
        for k, (name, value) in enumerate(stats):
            canvas.print(ix, iy + 6 + k, name, fg=Theme.TEXT)
            canvas.print(ix + 24, iy + 6 + k, value, fg=Theme.HILITE_TEXT, alignment=ui_right())
        dx = ix + 28
        pygame.draw.line(canvas.surface, Theme.BORDER_DIM, (dx * 24 - 12, iy * 24), (dx * 24 - 12, (iy + ih) * 24), 1)
        width = iw - 29
        canvas.print(dx, iy, "Skills", fg=Theme.TITLE)
        row = iy + 1
        skills = list(p.skills.items())
        if not skills:
            canvas.print(dx, row, "untrained", fg=Theme.DIM)
            row += 1
        hovered = None
        for skill, level in skills:
            over = self.hover_row == row
            canvas.print(dx, row, skill.value, fg=Theme.HILITE_TEXT if over else Theme.TEXT)
            canvas.print(dx + width - 1, row, str(level), fg=Theme.HILITE_TEXT, alignment=ui_right())
            if over:
                hovered = (skill, level)
            row += 1
        self.skill_rows = (dx, width, iy + 1, len(skills))
        self._draw_skill_tip(canvas, ix, iy + 15, dx - ix - 2, hovered)
        row += 1
        canvas.print(dx, row, "Traits and abilities", fg=Theme.TITLE)
        row += 1
        for tag in p.capabilities.tags:
            row += widgets.text_block(canvas, dx, row, width, ih - (row - iy), [(f"{tag.replace('_', ' ')}: {capabilities.TAGS[tag].description}", Theme.TEXT)])
            if row >= iy + ih:
                break


def _skill_tip_lines(skill, level, practice):
    """(what it does, how to raise it, progress) for one skill."""
    import skills as skill_defs
    what, how = skill_defs.SKILL_INFO[skill]
    if level >= skill_defs.MAX_LEVEL:
        progress = "Fully trained."
    else:
        progress = f"Practice {practice}/{skill_defs.PRACTICE_NEEDED[level]} towards level {level + 1}."
    return what, f"Raise it: {how}", progress


def ui_right() -> int:
    import ui
    return ui.RIGHT


class LevelUpEventHandler(Panel):
    TITLE = "Level up"
    WIDTH = 44
    HEIGHT = 14
    X = 13
    Y = 12
    HINTS = [("a-c", "choose")]

    def on_render(self, canvas: Canvas) -> None:
        import widgets
        from ui import Theme
        ix, iy, iw, ih = self.frame(canvas)
        p = self.engine.player
        canvas.print(ix, iy, "You grow stronger. Choose what to improve.", fg=Theme.TITLE)
        for k, text in enumerate((f"Constitution  +20 hit points (now {p.max_hp})", f"Strength      +1 attack (now {p.power})",
                                  f"Agility       +1 defence (now {p.defense})")):
            canvas.print(ix, iy + 2 + k * 2, "abc"[k] + ")", fg=Theme.KEY)
            canvas.print(ix + 2, iy + 2 + k * 2, text, fg=Theme.TEXT)

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - Key.A

        if 0 <= index <= 2:
            if index == 0:
                player.level.increase_max_hp()
            elif index == 1:
                player.level.increase_power()
            else:
                player.level.increase_defense()
        else:
            self.engine.message_log.add_message("Invalid entry.", color.invalid)

            return None

        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """
        Don't allow the player to click to exit the menu, like normal.
        """
        return None

class InventoryEventHandler(AskUserEventHandler):
    """
    This handler lets the user select an item.

    What happens then depends on the subclass.
    """

    TITLE = "<missing title>"#
    
    console_height: int
    console_width: int
    menu_width: int = 0
    menu_i: int = None
    height_per_item: int = 2

    console_x: int
    console_y: int
    offset: int

    inventory: Inventory
    inventory_entries: List[Item]
    entries_amount: int = 0

    buttons: dict
    button_height: int = 2
    button_highlight: str = None

    def __init__(self, engine: Engine, inventory: Inventory = None, entities: List[Entity] = None, canvas: Canvas = None, offset: int = 0):
        super().__init__(engine)
        self.inventory_entries = []
        self.buttons = {}
        # If there's only one entity at target location, treat it as single inventory
        entity: Entity = entities[0] if entities and len(entities) == 1 else None
        self.inventory = getattr(entity, "inventory", None) if entity and not inventory else inventory
        
        self.entities = entities
        self.offset = offset
        self.canvas = canvas

    WIDTH = 58      # (the map view's width: the side panel with the log stays visible)
    HEIGHT = 36
    DETAIL = 24
    RESERVED = ""        # hotkey letters an inventory screen keeps for itself
    TABBED = False       # the main inventory shares the tab row with the other screens

    def _source(self) -> list:
        """The things listed, in the order they are shown (grouped under category headings)."""
        import widgets
        source = list(self.inventory.items) if self.inventory else list(self.entities or [])
        source = [e for e in source if not getattr(e, "decal", False)]   # a stain on the ground is not loot
        order = {name: i for i, name in enumerate(widgets.CATEGORY_ORDER)}
        return sorted(source, key=lambda item: order.get(widgets.item_category(item), len(order)))

    def _parent_handler(self):
        prev_index = self.session.handlers.index(self) - 1 if self in self.session.handlers else -1
        return self.session.handlers[prev_index] if prev_index >= 0 else None

    def on_render(self, canvas: Canvas) -> None:
        """Draw the screen behind, then the window: a list with letter hotkeys on the left, the highlighted thing on the right."""
        import widgets
        from ui import Theme
        parent = self._parent_handler()
        if parent:
            parent.on_render(canvas)
        else:
            super().on_render(canvas)

        player = self.engine.player
        is_player = bool(self.inventory) and self.inventory.parent == player
        if self.inventory:
            self.inventory.instantiate_placeholders()
            self.TITLE = "Inventory" if is_player else f"{self.inventory.parent.get_title()}"
            self.COUNT = f"{len(self.inventory.items)}/{self.inventory.capacity}"
        self.inventory_entries = self._source()
        self.entries_amount = len(self.inventory_entries)
        if not self.inventory and self.entries_amount:
            self.TITLE = f"Objects at {(self.inventory_entries[0].x, self.inventory_entries[0].y)}"

        x0, y0 = 3 * self.offset, 2 + self.offset
        self.console_x, self.console_y = x0, y0
        self.menu_width, self.menu_height = self.WIDTH, self.HEIGHT
        hints = [("a-z", "choose"), ("Enter", "select"), ("s", "scan")]
        if is_player:
            hints.append(("d", "drop"))
        if self.TABBED and is_player:
            hints.append(("Tab", "next screen"))
        if not is_player and self.entries_amount and hasattr(self, "on_items_selected"):
            hints.append(("g", "grab all"))
        hints.append(("Esc", "close"))
        tabs = widgets.tab_titles() if self.TABBED and is_player else None
        ix, iy, iw, ih = canvas.window(x0, y0, self.WIDTH, self.HEIGHT, title=f"{self.TITLE} ({self.COUNT})" if getattr(self, "COUNT", None) and self.inventory else self.TITLE, hints=hints, tabs=tabs, active=0)

        list_w = iw - self.DETAIL - 1
        if not self.entries_amount:
            canvas.print(ix, iy + 1, "(nothing here)", fg=Theme.DIM)
            return
        equipped = lambda item: isinstance(item, Equippable) and item.equipped  # noqa: E731
        keep = self.RESERVED + "s" + ("d" if is_player else "")    # (the letters of the scan and drop keys)
        self.list = widgets.ListView(widgets.item_rows(self.inventory_entries, equipped), reserved=keep)
        shown = self.menu_i if self.menu_i is not None and 0 <= self.menu_i < self.entries_amount else None
        if shown is not None:
            for index, row in enumerate(self.list.rows):
                if row.data is self.inventory_entries[shown]:
                    self.list.selected = index
        self.list.draw(canvas, ix, iy, list_w, ih)
        self.buttons = {}
        for rect, index in self.list.hits:
            data = self.list.rows[index].data
            if data in self.inventory_entries:
                self.buttons[self.inventory_entries.index(data)] = {"x": rect.x // 24, "y": rect.y // 24}

        # the highlighted item, in a framed slot with what you may read about it
        dx = ix + list_w + 1
        pygame.draw.line(canvas.surface, Theme.BORDER_DIM, (dx * 24 - 12, iy * 24), (dx * 24 - 12, (iy + ih) * 24), 1)
        row = self.list.current
        item = row.data if row is not None else None
        if item is not None:
            widgets.sprite_slot(canvas, dx + (self.DETAIL - 4) // 2, iy, item.sprite_id, item.color, getattr(item, "flipped", False))
            widgets.text_block(canvas, dx, iy + 5, self.DETAIL, ih - 5, widgets.item_details(self.engine, item))

    def on_entity_selected(self, entity: Entity) -> Optional[ActionOrHandler]:
        if entity.has_inventory:
            return InventoryLootHandler(self.engine, self.engine.player, entity.inventory, canvas=self.canvas, offset=1)

    def _activate(self, index: int) -> Optional[ActionOrHandler]:
        item = self.inventory_entries[index]
        if isinstance(item, Item) or getattr(item, "scenery", False):     # (bones and pebbles may be picked up, and put down again)
            return self.on_item_selected(item)
        return self.on_entity_selected(item)

    def ev_keydown(
        self, event: events.KeyDown
    ) -> Optional[BaseEventHandler]:

        if event.sym == Key.UP:
            self.menu_i = 0 if self.menu_i is None else self.menu_i
            self.menu_i = self.menu_i-1 if self.menu_i > 0 else self.entries_amount - 1
        elif event.sym == Key.DOWN:
            self.menu_i = -1 if self.menu_i is None else self.menu_i
            self.menu_i = self.menu_i+1 if not self.menu_i >= self.entries_amount - 1 else 0

        self.button_highlight = self.menu_i if self.menu_i is not None else self.button_highlight

        if self.TABBED and event.sym in (Key.TAB, Key.LEFT, Key.RIGHT) and self.inventory and self.inventory.parent == self.engine.player:
            import widgets
            return widgets.next_screen(self, -1 if event.sym == Key.LEFT or event.mod & (Mod.LSHIFT | Mod.RSHIFT) else 1)

        if event.sym == Key.G and hasattr(self, "on_items_selected"):
            return self.on_items_selected(self.inventory_entries)

        if event.sym in (Key.S, Key.D) and self.entries_amount:
            return self._scan_or_drop(event.sym == Key.S)

        if Key.A <= event.sym <= Key.Z and self.entries_amount:   # a letter chooses the entry shown with it
            import widgets
            lv = getattr(self, "list", None)
            if lv is not None:
                index = lv.keys.get(chr(event.sym - Key.A + ord("a")))
                if index is not None and lv.rows[index].data in self.inventory_entries:
                    self.menu_i = self.button_highlight = self.inventory_entries.index(lv.rows[index].data)
                    return self._activate(self.menu_i)

        if event.sym in CONFIRM_KEYS and (self.menu_i is None or not self.inventory_entries
                                          or not 0 <= self.menu_i < len(self.inventory_entries)):
            return None   # nothing selected (or nothing to select)
        if event.sym in CONFIRM_KEYS:
            return self._activate(self.menu_i)

        if event.sym in (Key.UP, Key.DOWN):
            return None
        return super().ev_keydown(event)

    def _highlighted(self):
        """The entry under the cursor (or the one the list has selected)."""
        if self.menu_i is not None and 0 <= self.menu_i < len(self.inventory_entries):
            return self.inventory_entries[self.menu_i]
        row = self.list.current if getattr(self, "list", None) is not None else None
        return row.data if row is not None else None

    def _scan_or_drop(self, scan: bool) -> Optional[ActionOrHandler]:
        """The S and D keys (and their hints, which can be clicked): scan the highlighted thing, or drop it from your own pack."""
        thing = self._highlighted()
        player = self.engine.player
        if thing is None:
            return None
        if scan:
            return actions.ScanThingAction(player, thing)
        if self.inventory is not None and self.inventory.parent == player and (isinstance(thing, Item) or getattr(thing, "scenery", False)):
            rows = getattr(getattr(self, "list", None), "rows", ())
            group = next((row.group for row in rows if row.data is thing), ())
            if len(group) > 1:
                return actions.DropStack(player, group)           # a stack goes down together
            return actions.DropItem(player, thing)
        return None

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item."""
        raise NotImplementedError()

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Left click on an entry selects it; anywhere else (or another button) closes."""
        if not event.button == MouseButton.LEFT:
            return self.resolve_handler()
        lv = getattr(self, "list", None)
        if lv is not None:
            index = lv.row_at(event.position[0] * 24 + 1, event.position[1] * 24 + 1)
            if index is not None and lv.rows[index].data in self.inventory_entries:
                self.menu_i = self.button_highlight = self.inventory_entries.index(lv.rows[index].data)
                return self._activate(self.menu_i)
        return self.resolve_handler()

    def ev_mousemotion(
        self, event: events.MouseMotion
    ) -> Optional[ActionOrHandler]:
        """Tracks mouse movement"""
        lv = getattr(self, "list", None)
        if lv is None:
            return None
        index = lv.row_at(event.position[0] * 24 + 1, event.position[1] * 24 + 1)
        if index is not None and lv.rows[index].data in self.inventory_entries:
            self.menu_i = self.button_highlight = self.inventory_entries.index(lv.rows[index].data)


class CraftingMenuHandler(AskUserEventHandler):
    """The crafting screen: recipes on the left; on the right what the selected one needs, line by line (met or not), and
    which of your materials it would use. TAB picks a role, LEFT/RIGHT changes the material used for it."""

    TITLE = "Crafting"
    LIST_ROWS = 30

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.show_all: bool = False  # A: also list the recipes you have worked out but cannot do right here
        self.recipes = self._listed()
        self.menu_i: int = 0
        self.button_highlight: int = 0
        self.role_i: int = 0
        self.choices: dict = {}  # recipe key -> {role: material id}

    def _listed(self):
        import crafting
        return crafting.available(self.engine.player, self.engine.game_world.run, everything=self.show_all)

    @property
    def recipe(self):
        return self.recipes[self.button_highlight]

    def plan(self, recipe=None):
        import crafting
        recipe = recipe or self.recipe
        return crafting.check(recipe, self.engine.player, self.choices.get(recipe.key))

    WIDTH = 58      # (the map view's width: the side panel with the log stays visible)
    HEIGHT = 36
    LIST_W = 28

    def on_render(self, canvas: Canvas) -> None:
        import lore
        import widgets
        from ui import Theme
        parent = self.session.handlers[self.session.handlers.index(self) - 1] if self in self.session.handlers and self.session.handlers.index(self) > 0 else None
        (parent or super()).on_render(canvas)
        hints = [("a-z", "choose"), ("Enter", "make"), ("Space", "all known" if not self.show_all else "only doable"),
                 ("Left/Right", "material"), (",/.", "part"), ("Tab", "next screen"), ("Esc", "close")]
        ix, iy, iw, ih = canvas.window(0, 2, self.WIDTH, self.HEIGHT, title="Recipes", hints=hints, tabs=widgets.tab_titles(), active=widgets.tab_index(self))
        if not self.recipes:
            canvas.print(ix, iy + 1, "Nothing you can make here and now.", fg=Theme.TITLE)
            widgets.text_block(canvas, ix, iy + 3, iw, 6, [
                "Gather pieces and stand next to things to work out what you could make from them.",
                "Space lists the recipes you already know.",
            ])
            return
        # the list: grouped by stage, only recipes that can be made here (or every known one)
        rows, last = [], None
        for recipe in self.recipes:
            if recipe.stage != last:
                rows.append(widgets.Row(f"Stage {recipe.stage}", header=True))
                last = recipe.stage
            result = recipe.result
            icon = (result.sprite_id, (255, 255, 255), False) if result is not None else None      # (white: it takes a colour once materials are chosen)
            ok = self.plan(recipe).ok
            rows.append(widgets.Row(recipe.name, icon=icon, color=None if ok else Theme.DIM, data=recipe))
        self.list = widgets.ListView(rows)
        for index, row in enumerate(self.list.rows):
            if row.data is self.recipe:
                self.list.selected = index
        self.list.draw(canvas, ix, iy, self.LIST_W, ih)
        dx = ix + self.LIST_W + 1
        dw = iw - self.LIST_W - 1
        pygame.draw.line(canvas.surface, Theme.BORDER_DIM, (dx * 24 - 12, iy * 24), (dx * 24 - 12, (iy + ih) * 24), 1)
        recipe = self.recipe
        plan = self.plan()
        result = recipe.result
        if result is not None:
            chosen = plan.parts.get(recipe.designation)         # the material that colours the tool; white until one is chosen
            widgets.sprite_slot(canvas, dx, iy, result.sprite_id, tuple(chosen.color) if chosen is not None else (255, 255, 255))
        canvas.print(dx + 5, iy, recipe.name, fg=Theme.TITLE)
        canvas.print(dx + 5, iy + 1, f"stage {recipe.stage}   takes {recipe.time} turn{'s' if recipe.time != 1 else ''}", fg=Theme.DIM)
        row = iy + 5
        row += widgets.text_block(canvas, dx, row, dw, 4, [recipe.description])
        row += 1
        canvas.print(dx, row, "Needs", fg=Theme.TITLE)
        row += 1
        for line in plan.lines:
            wrapped = canvas.wrap(("+ " if line.ok else "- ") + line.text, dw)
            for k, text in enumerate(wrapped):
                canvas.print(dx, row, text if k == 0 else "  " + text.lstrip(), fg=Theme.GOOD if line.ok else Theme.BAD)
                row += 1
        roles = [n.role for n in recipe.needs]
        run = self.engine.game_world.run
        if roles:
            row += 1
            canvas.print(dx, row, "Materials", fg=Theme.TITLE)
            row += 1
            for i, need in enumerate(recipe.needs):
                mats = __import__("crafting").options(recipe, self.engine.player, need.role)
                chosen = (self.choices.get(recipe.key) or {}).get(need.role)
                if chosen is None and plan.parts.get(need.role) is not None:
                    chosen = plan.parts[need.role].id
                name = next((lore.material_name(run, m) for m in mats if m.id == chosen), "-")
                current = i == self.role_i % len(roles)
                text = f"{'>' if current else ' '} {need.label}: {name}" + (f"  ({len(mats)})" if len(mats) > 1 else "")
                canvas.print(dx, row, text, fg=Theme.HILITE_TEXT if current else Theme.TEXT, bg=Theme.HILITE if current else None)
                row += 1
        if plan.ok and recipe.needs:
            props = self._preview(recipe, plan)
            if props:
                row += 1
                widgets.text_block(canvas, dx, row, dw, 3, [(props, Theme.TEXT)])

    @staticmethod
    def _wrap(text: str, width: int):
        import textwrap
        return textwrap.wrap(text, width) or [""]

    def _preview(self, recipe, plan) -> str:
        import materials
        if not plan.parts:
            return ""
        rules = dict(recipe.rules)
        keys = [k for k in rules][:3] or ["hardness", "toughness"]
        try:
            props = materials.derive_properties(plan.parts, rules, plan.quality, keys=keys)
        except Exception:
            return ""
        import lore
        run = self.engine.game_world.run
        shown = ", ".join(f"{k} {v:.1f}" if all(lore.property_known(run, m, k) for m in plan.parts.values()) else f"{k} ?"
                          for k, v in props.items())
        return "Result: " + shown + f"  quality {plan.quality:.1f}"

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        import widgets
        key = event.sym
        count = len(self.recipes)
        if key in (Key.TAB, Key.SPACE) and key == Key.TAB:
            return widgets.next_screen(self, -1 if event.mod & (Mod.LSHIFT | Mod.RSHIFT) else 1)
        if key == Key.SPACE:
            self.show_all = not self.show_all
            self.recipes = self._listed()
            self.button_highlight = self.role_i = 0
            return None
        if not count:
            return super().ev_keydown(event)
        if key == Key.UP:
            self.button_highlight = (self.button_highlight - 1) % count
            self.role_i = 0
            return None
        elif key == Key.DOWN:
            self.button_highlight = (self.button_highlight + 1) % count
            self.role_i = 0
            return None
        elif key == Key.PAGEUP:
            self.button_highlight = max(0, self.button_highlight - 10)
            return None
        elif key == Key.PAGEDOWN:
            self.button_highlight = min(count - 1, self.button_highlight + 10)
            return None
        elif key in (Key.PERIOD, Key.COMMA):
            self.role_i += 1 if key == Key.PERIOD else -1
            return None
        elif key in (Key.LEFT, Key.RIGHT):
            self._cycle(1 if key == Key.RIGHT else -1)
            return None
        elif Key.A <= key <= Key.Z and getattr(self, "list", None) is not None:
            index = self.list.keys.get(chr(key - Key.A + ord("a")))
            if index is not None:
                self.button_highlight = self.recipes.index(self.list.rows[index].data)
                self.role_i = 0
            return None
        elif key in CONFIRM_KEYS:
            recipe = self.recipe
            plan = self.plan()
            if plan.ok:
                return actions.CraftAction(self.engine.player, recipe, self.choices.get(recipe.key))
            self.engine.message_log.add_message(f"You can't make that yet: {plan.reasons[0]}", color.impossible)
            return None
        return super().ev_keydown(event)

    def _cycle(self, step: int) -> None:
        import crafting
        recipe = self.recipe
        role = recipe.needs[self.role_i % len(recipe.needs)].role
        mats = crafting.options(recipe, self.engine.player, role)
        if not mats:
            return
        current = (self.choices.get(recipe.key) or {}).get(role)
        ids = [m.id for m in mats]
        index = (ids.index(current) + step) % len(ids) if current in ids else (0 if step > 0 else len(ids) - 1)
        self.choices.setdefault(recipe.key, {})[role] = ids[index]

    def ev_mousebuttondown(self, event: events.MouseButtonDown) -> Optional[ActionOrHandler]:
        return None


class InventoryActivateHandler(InventoryEventHandler):
    """Handle using an inventory item."""

    TITLE = "Inventory"
    TABBED = True

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        if getattr(item, "scenery", False):
            raise exceptions.Impossible(f"{item.get_title()} is only for show: put it down with D.")
        if isinstance(item, Equippable):
            return actions.EquipAction(self.inventory.parent, item)
        from components.consumable import FoodConsumable
        if isinstance(item, FoodConsumable):
            return actions.EatAction(self.inventory.parent, item)   # eating takes a turn
        return item.activate(self.inventory.parent)


class InventoryDropHandler(InventoryEventHandler):
    """Handle dropping an inventory item."""

    TITLE = "Select an item to drop"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Drop this item."""
        return actions.DropItem(self.inventory.parent, item)


class InventoryLootHandler(InventoryEventHandler):
    """Handle looting an item."""

    RESERVED = "g"

    def __init__(self, engine: Engine, looter: Entity, inventory: Inventory = None, entities: Optional[List[Entity]] = None, canvas: Canvas = None, offset: int = 0):
        entities = [] if entities is None else entities
        super().__init__(engine, inventory, entities, canvas, offset)

        self.looter = looter
        self.entities = entities

    def on_render(self, canvas: Canvas) -> None:
        """
        Render an inventory menu, which displays the items in the inventory.
        """
        self.canvas = canvas if not self.canvas else self.canvas
        super().on_render(self.canvas)
    
    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        rows = getattr(getattr(self, "list", None), "rows", ())
        group = next((row.group for row in rows if row.data is item), ())
        if len(group) > 1:
            return self.on_items_selected(group)               # a stack (one row of identical things) comes up together
        if not self.inventory and item in self.entities:
            self.entities.remove(item)
        return actions.PickupAction(self.looter, item)

    def on_items_selected(self, items: List[Item]) -> Optional[ActionOrHandler]:
        """Called when the user attempts to grab multiple items at once."""
        #TODO Fix bug when too many items are grabbed?
        items = list(items)
        if not self.inventory:
            for item in items:
                if item in self.entities:
                    self.entities.remove(item)
        return actions.MassPickupAction(self.looter, items)

class SelectIndexHandler(AskUserEventHandler):
    """Handles asking the user for an index on the map."""

    def __init__(self, engine: Engine):
        """Sets the cursor to the player when this handler is constructed."""
        super().__init__(engine)
        player = self.engine.player
        engine.mouse_location = player.x, player.y

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        """Check for key movement or confirmation keys."""
        key = event.sym
        if key in MOVE_KEYS:
            modifier = 1  # Holding modifier keys will speed up key movement.
            if event.mod & (Mod.LSHIFT | Mod.RSHIFT):
                 modifier *= 5
            if event.mod & (Mod.LCTRL | Mod.RCTRL):
                 modifier *= 10
            if event.mod & (Mod.LALT | Mod.RALT):
                 modifier *= 20

            x, y = self.engine.mouse_location
            dest_x, dest_y = MOVE_KEYS[key]
            x += dest_x * modifier
            y += dest_y * modifier
            # Clamp the cursor index to the map size.
            camera = self.engine.camera  # the cursor stays on screen
            x = max(camera.x0, min(x, camera.x0 + camera.width - 1))
            y = max(camera.y0, min(y, camera.y0 + camera.height - 1))
            self.engine.mouse_location = x, y
            return None
        elif key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Left click confirms a selection."""
        world_xy = screen_to_world(self.engine, event.position)
        if world_xy is not None and self.engine.game_map.in_bounds(*world_xy):
            if event.button == 1:
                return self.on_index_selected(*world_xy)
        return super().ev_mousebuttondown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        """Called when an index is selected."""
        raise NotImplementedError()


class LookHandler(SelectIndexHandler):
    """Lets the player look around using the keyboard."""

    def on_index_selected(self, x: int, y: int) -> MainGameEventHandler:
        """Return to main handler."""
        player = self.engine.player
        x, y = self.engine.mouse_location

        return actions.BumpAction(player, x, y)

class SingleRangedAttackHandler(SelectIndexHandler):
    """Handles targeting a single enemy. Only the enemy selected will be affected."""

    def __init__(
        self, engine: Engine, callback: Callable[[Tuple[int, int]], Optional[actions.Action]]
    ):
        super().__init__(engine)

        self.callback = callback

    def on_index_selected(self, x: int, y: int) -> Optional[actions.Action]:
        return self.callback((x, y))


def area_frame_rect(x: int, y: int, radius: int) -> Tuple[int, int, int, int]:
    """Return `(x, y, width, height)` of a frame that encloses the area affected around `(x, y)`.

    The affected area spans `2 * radius + 1` tiles per axis (`x - radius` .. `x + radius`); the frame
    is drawn on the ring of tiles just outside it, so it is `2 * radius + 3` wide/high.
    """
    size = 2 * radius + 3
    return x - radius - 1, y - radius - 1, size, size


class AreaRangedAttackHandler(SelectIndexHandler):
    """Handles targeting an area within a given radius. Any entity within the area will be affected."""

    def __init__(
        self,
        engine: Engine,
        radius: int,
        callback: Callable[[Tuple[int, int]], Optional[actions.Action]],
    ):
        super().__init__(engine)

        self.radius = radius
        self.callback = callback

    def on_render(self, canvas: Canvas) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(canvas)

        x, y = self.engine.camera.to_screen(*self.engine.mouse_location)

        # Draw a rectangle around the targeted area, so the player can see the affected tiles.
        frame_x, frame_y, width, height = area_frame_rect(x, y, self.radius)
        canvas.draw_outline(frame_x, frame_y, width, height, color.red)

    def on_index_selected(self, x: int, y: int) -> Optional[actions.Action]:
        return self.callback((x, y))

class MainGameEventHandler(EventHandler):

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.mouse_motion = False

    def on_render(self, canvas: Canvas) -> None:
        """The map; with the mouse over open ground, the way there (faint) and the target cell."""
        player = self.engine.player
        if self.mouse_motion and player.is_alive:
            self.engine.hover_overlay = lambda: self._draw_path(canvas)
        super().on_render(canvas)

    def _draw_path(self, canvas: Canvas) -> None:
        import render_functions
        engine, player = self.engine, self.engine.player
        x, y = engine.mouse_location
        game_map = engine.game_map
        if not game_map.in_bounds(x, y) or not game_map.is_visible(x, y):
            return
        if any(e is not player and not getattr(e, "decal", False) for e in game_map.stack_at(x, y)):
            return   # pointing at something: the tooltip is about that, not about walking
        if render_functions.rock_face_at(engine, x, y) is not None:
            return
        x, y = travel_target(engine, x, y)
        path: List[Tuple] = engine.get_path_to(player, x, y)
        for step in path:
            highlight_world(engine, canvas, step[0], step[1], (140, 220, 230), alpha=45)
        if path:
            highlight_world(engine, canvas, path[-1][0], path[-1][1], (140, 220, 230), alpha=90)

    def ev_mousemotion(self, event: events.MouseMotion) -> None:
        super().ev_mousemotion(event)
        self.mouse_motion = True if event else False
        

    def ev_mousebuttondown(self, event: events.MouseMotion) -> Optional[ActionOrHandler]:
        if event.button == MouseButton.LEFT:
            player = self.engine.player
            x, y = self.engine.mouse_location
            if not any(e is not player and not getattr(e, "decal", False) for e in self.engine.game_map.stack_at(x, y)):
                x, y = travel_target(self.engine, x, y)
            return actions.BumpAction(player, x, y)
        if event.button == MouseButton.RIGHT and self.engine.player.is_alive:
            xy = screen_to_world(self.engine, event.position)
            if xy is not None and self.engine.game_map.in_bounds(*xy) and self.engine.game_map.is_explored(*xy):
                import screens
                return screens.ContextMenu(self.engine, xy[0], xy[1], event.position)

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        action: Optional[actions.Action] = None

        key = event.sym
        modifier = event.mod

        player = self.engine.player

        # modifier checks if button is held down
        if key == Key.PERIOD and modifier & (
            Mod.LSHIFT | Mod.RSHIFT
        ):
            pass

        import debug
        if key == Key.F10 and debug.enabled():
            debug.toggle_god(self.engine)
        elif key in MOVE_KEYS and debug.is_god(self.engine) and modifier & (Mod.CTRL | Mod.ALT):
            debug.jump(self.engine, *MOVE_KEYS[key], whole_chunk=bool(modifier & Mod.ALT))
        elif key in MOVE_KEYS:
            dest_x, dest_y = MOVE_KEYS[key][0] + player.x, MOVE_KEYS[key][1] + player.y
            action = actions.BumpAction(player, dest_x, dest_y)
        elif key in WAIT_KEYS:
            action = actions.WaitAction(player)

        elif key == Key.ESCAPE:
            import screens
            return screens.PauseMenu(self.engine)

        elif key == Key.L:
            return actions.TakeStairsAction(player)
        elif key == Key.PERIOD and modifier & (Mod.LSHIFT | Mod.RSHIFT):
            return actions.TakeStairsAction(player, -1)
        elif key == Key.COMMA and modifier & (Mod.LSHIFT | Mod.RSHIFT):
            return actions.TakeStairsAction(player, 1)
        elif key == Key.LESS:  # the "<" / ">" key of ISO keyboards (Shift gives ">")
            return actions.TakeStairsAction(player, -1 if modifier & (Mod.LSHIFT | Mod.RSHIFT) else 1)

        elif key == Key.V:
            return HistoryViewer(self.engine)

        elif key == Key.G:
            return PickupHandler(self.engine)
        elif key == Key.I:
            return InventoryActivateHandler(self.engine, player.inventory)
        elif key == Key.D:
            return InventoryDropHandler(self.engine, player.inventory)
        elif key == Key.R:
            return CraftingMenuHandler(self.engine)
        elif key == Key.F:
            return actions.InteractAction(player)
        elif key == Key.X:
            return actions.GatherAction(player)   # dig the ground (sand, clay)
        elif key == Key.T:
            return actions.SharpenAction(player)  # put an edge on the wielded tool
        elif key == Key.Z:
            return actions.SleepAction(player)    # sleep on a bed
        elif key == Key.P:
            return SingleRangedAttackHandler(self.engine, lambda xy: actions.FireAction(player, *xy))  # fire the pistol
        elif key == Key.K:
            return actions.TrackAction(player)    # use the tracker
        elif key == Key.S:
            return SingleRangedAttackHandler(self.engine, lambda xy: actions.ScanAction(player, *xy))  # scanner
        elif key == Key.H:
            import screens
            return screens.HelpHandler(self.engine)
        elif key == Key.M:
            import screens
            return screens.NavigationHandler(self.engine)   # where things are
        elif key == Key.O:
            return CodexHandler(self.engine)      # what you have learned

        elif key == Key.C:
            return CharacterScreenEventHandler(self.engine)

        elif key == Key.PERIOD:
            return LookHandler(self.engine)

        # No valid key was pressed
        return action

    def get_action_or_event(self, unit: Unit):
        entities = self.engine.game_map.get_entities_at_location(unit.x, unit.y)
        for entity in entities:
            if not entity:
                continue
            if not (unit.x == entity.x and unit.y == entity.y):
                continue
            if entity == unit or entity == self.engine.player:
                continue
            if not entity.has_inventory and not isinstance(entity, Item):
                continue  # scenery (a stump) has nothing to pick up
            if isinstance(entity, Item):
                item: Item = entity
                return actions.PickupAction(unit, item)
                
            return InventoryLootHandler(self.engine, unit, entities=entities)

class GameOverEventHandler(EventHandler):
    """Roguelike: the run is over (the save is deleted). Casual: `R` wakes you at your last bed (the bed save)."""

    def casual_respawn(self) -> bool:
        import os
        return self.engine.game_world.run.mode == "casual" and os.path.isdir(actions.BED_SAVE)

    def on_render(self, canvas: Canvas) -> None:
        from ui import Theme
        super().on_render(canvas)   # the map stays visible (and the tooltip works): you can still look around with the mouse
        hints = [("R", "wake at your last bed"), ("Esc", "give up")] if self.casual_respawn() else [("Esc", "leave")]
        ix, iy, iw, ih = canvas.window((canvas.width - 40) // 2, 1, 40, 6, title="The end of the road", hints=hints)
        canvas.print(ix + iw // 2, iy + 1, "You died.", fg=Theme.BAD, alignment=CENTER)

    def on_quit(self) -> None:
        """Handle exiting out of a finished game."""
        import savegame
        if getattr(self.engine, "continued", False):
            savegame.remove_save("savegame")  # this run owns the active save: permadeath deletes it (never another run's)
        raise exceptions.QuitWithoutSaving()  # Avoid saving a finished game.

    def ev_quit(self, event: events.Quit) -> None:
        self.on_quit()

    def ev_keydown(self, event: events.KeyDown):
        if event.sym == Key.R and self.casual_respawn():
            import savegame
            engine = savegame.load_game(actions.BED_SAVE, self.engine.session)
            engine.continued = getattr(self.engine, "continued", False)
            engine.game_world.run.deaths += 1
            engine.message_log.add_message("You wake at your last bed.", color.green)
            self.session.reset(MainGameEventHandler(engine))
            return None
        if event.sym == Key.ESCAPE:
            self.on_quit()

CURSOR_Y_KEYS = {
    Key.UP: -1,
    Key.DOWN: 1,
    Key.PAGEUP: -10,
    Key.PAGEDOWN: 10,
}

class HistoryViewer(Panel):
    """The message log in a window: scroll with Up/Down, Home/End jump."""

    TITLE = "Log"
    TABBED = True
    HINTS = [("Up/Down", "scroll"), ("Home/End", "first/last"), ("Esc", "close")]

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, canvas: Canvas) -> None:
        ix, iy, iw, ih = self.frame(canvas)
        self.engine.message_log.render_messages(canvas, ix, iy, iw, ih, self.engine.message_log.messages[: self.cursor + 1])

    def ev_keydown(self, event: events.KeyDown) -> Optional[MainGameEventHandler]:
        # Fancy conditional movement to make it feel right.
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                # Only move from the top to the bottom when you're on the edge.
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                # Same with bottom to top movement.
                self.cursor = 0
            else:
                # Otherwise move while staying clamped to the bounds of the history log.
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1))
        elif event.sym == Key.HOME:
            self.cursor = 0  # Move directly to the top message.
        elif event.sym == Key.END:
            self.cursor = self.log_length - 1  # Move directly to the last message.
        elif event.sym == Key.TAB:
            return super().ev_keydown(event)
        else:  # Any other key moves back to the main game state.
            self.reset_to_handler(MainGameEventHandler(self.engine))
        return None

class PlaceConstructableHandler(SelectIndexHandler):
    """Lets the player pick a tile to place a constructable item."""

    def __init__(self, engine: Engine, item):
        super().__init__(engine)
        self.item = item
        # Start cursor at player position
        self.engine.mouse_location = engine.player.x, engine.player.y

    def on_render(self, canvas: Canvas) -> None:
        super().on_render(canvas)
        # Highlight valid placement tiles (current + adjacent)
        px, py = self.engine.player.x, self.engine.player.y
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                tx, ty = px + dx, py + dy
                if self.engine.game_map.in_bounds(tx, ty):
                    highlight_world(self.engine, canvas, tx, ty, color.menu_text)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return actions.PlaceConstructableAction(self.engine.player, self.item, x, y)


def __getattr__(name):
    """`input_handlers.PodHandler` and `EndingHandler` live in `screens` (they import this module)."""
    if name in ("PodHandler", "EndingHandler", "NavigationHandler", "HelpHandler"):
        import screens
        return getattr(screens, name)
    raise AttributeError(name)
