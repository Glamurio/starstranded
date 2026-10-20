"""In-game screens added for the survival game: the sponsor cargo pod (contracts and shop) and the ending."""
from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, Optional

import color
import events
import exceptions
import layout
import sponsors
from events import Key
from input_handlers import AskUserEventHandler, CONFIRM_KEYS, EventHandler

if TYPE_CHECKING:
    from engine import Engine
    from ui import Canvas

TABS = ("Contracts", "Supplies", "Sponsors")


class PodHandler(AskUserEventHandler):
    """The sponsor cargo pod: TAB switches between your contracts, the supply shop and the reputation board."""

    TITLE = "Sponsor cargo pod"

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.tab = 0
        self.row = 0

    @property
    def run(self):
        return self.engine.game_world.run

    def rows(self):
        if self.tab == 0:
            return [c for c in self.run.contracts if not c.done]
        if self.tab == 1:
            return list(sponsors.SHOP.items())
        return list(sponsors.SPONSORS.values())

    def on_render(self, canvas: Canvas) -> None:
        import pygame
        import widgets
        from ui import Theme
        super().on_render(canvas)
        run = self.run
        hints = {0: [("Enter", "hand in what you carry")], 1: [("Enter", "buy")], 2: []}[self.tab] + [("Tab", "next page"), ("Esc", "close")]
        ix, iy, iw, ih = canvas.window(5, 4, 70, 30, title=self.TITLE, hints=hints, tabs=[("", name) for name in TABS], active=self.tab)
        canvas.print(ix + iw - 1, iy - 1, f"credits: {run.credits}", fg=Theme.TITLE, alignment=__import__("ui").RIGHT)
        rows = self.rows()
        self.row = max(0, min(self.row, len(rows) - 1))
        list_w = 40
        out = []
        for item in rows:
            if self.tab == 0:
                out.append(widgets.Row(item.title, right=f"{item.filled}/{item.count}", data=item))
            elif self.tab == 1:
                out.append(widgets.Row(item[1][1], right=f"{item[1][0]} cr", data=item))
            else:
                out.append(widgets.Row(item.name, right=f"rep {run.reputation.get(item.key, 0)}" + ("  yours" if item.key == run.sponsor else ""), data=item))
        self.list = widgets.ListView(out)
        if rows:
            self.list.selected = self.row
        else:
            canvas.print(ix, iy + 1, "No open contracts." if self.tab == 0 else "Nothing here.", fg=Theme.DIM)
        self.list.draw(canvas, ix, iy, list_w, ih - 3)
        dx = ix + list_w + 1
        pygame.draw.line(canvas.surface, Theme.BORDER_DIM, (dx * 24 - 12, iy * 24), (dx * 24 - 12, (iy + ih) * 24), 1)
        dw = iw - list_w - 1
        if rows and self.tab == 0:
            c = rows[self.row]
            carry, worth = sponsors.offer_value(self.engine.player, run, c)
            widgets.text_block(canvas, dx, iy, dw, ih, [(c.title, Theme.TITLE), f"filled {c.filled} of {c.count}",
                                                           f"you carry {carry}, worth {worth} credits now", f"reputation +{c.reputation}"])
        elif rows and self.tab == 2:
            spec = rows[self.row]
            widgets.text_block(canvas, dx, iy, dw, ih, [(spec.name, Theme.TITLE), spec.blurb, "", "Wants: " + ", ".join(spec.wants) + "."])
        if self.tab == 2:
            ready = sponsors.rescue_ready(run, run.sponsor)
            canvas.print(ix, iy + ih - 1, f"Rescue: reputation {run.reputation.get(run.sponsor, 0)}/{sponsors.RESCUE_REPUTATION}, "
                         f"{'ready - build a beacon' if ready else 'not yet'}", fg=Theme.GOOD if ready else Theme.DIM)

    def ev_keydown(self, event: events.KeyDown):
        key = event.sym
        if key == Key.TAB:
            self.tab = (self.tab + 1) % len(TABS)
            self.row = 0
        elif key == Key.UP:
            self.row = max(0, self.row - 1)
        elif key == Key.DOWN:
            self.row = min(max(0, len(self.rows()) - 1), self.row + 1)
        elif key in CONFIRM_KEYS:
            self._activate()
        elif key in (Key.LSHIFT, Key.RSHIFT, Key.LCTRL, Key.RCTRL, Key.LALT, Key.RALT):
            pass
        else:
            return self.on_exit()
        return None

    def ev_mousebuttondown(self, event):
        if event.button == events.MouseButton.RIGHT:
            return self.on_exit()
        view = getattr(self, "list", None)
        if view is not None:
            index = view.row_at(int(event.position[0]) * 24 + 12, int(event.position[1]) * 24 + 12)
            if index is not None:
                if index == self.row:
                    self._activate()   # a second click on the chosen row does what Enter does
                self.row = index
        return None

    def _activate(self) -> None:
        log = self.engine.message_log
        rows = self.rows()
        if not rows:
            return
        player = self.engine.player
        try:
            if self.tab == 0:
                n, value = sponsors.deliver(player, self.run, rows[self.row])
                log.add_message(f"Delivered {n}: {value} credits.", color.green)
            elif self.tab == 1:
                key = rows[self.row][0]
                item = sponsors.buy(player, self.run, key)
                log.add_message(f"You buy {item.get_title()}.", color.green)
        except exceptions.Impossible as exc:
            log.add_message(exc.args[0], color.impossible)


class EndingHandler(EventHandler):
    """The last screen of a finished run: the ending and what the run looked like. Any key leaves (and deletes the save)."""

    def on_render(self, canvas: Canvas) -> None:
        import endings
        from ui import Theme, CENTER
        ix, iy, iw, ih = canvas.window(6, 3, canvas.width - 12, canvas.height - 6, title="The End", hints=[("any key", "leave")])
        row = iy + 2
        for i, text in enumerate(endings.epilogue(self.engine)):
            for part in canvas.wrap(text, iw - 8):
                canvas.print(ix + iw // 2, row, part, fg=Theme.TITLE if i == 0 else Theme.TEXT, alignment=CENTER)
                row += 1
            row += 1 if i == 0 else 0

    def ev_keydown(self, event: events.KeyDown):
        if event.sym in (Key.LSHIFT, Key.RSHIFT, Key.LCTRL, Key.RCTRL, Key.LALT, Key.RALT):
            return None
        self.finish()

    def ev_quit(self, event) -> None:
        self.finish()

    def finish(self) -> None:
        import savegame
        if getattr(self.engine, "continued", False):
            savegame.remove_save("savegame")
        savegame.remove_save("savegame_bed")   # the run is over: no bed to wake in
        raise exceptions.QuitWithoutSaving()


def bearing(dx: int, dy: int) -> str:
    """Words for an offset: '12 east, 5 north' (y grows downward)."""
    parts = []
    if dx:
        parts.append(f"{abs(dx)} {'east' if dx > 0 else 'west'}")
    if dy:
        parts.append(f"{abs(dy)} {'south' if dy > 0 else 'north'}")
    return ", ".join(parts) or "here"


def navigation_lines(engine) -> list:
    """Where the places you know of are, relative to you: the crash site, the cargo pod and ruins you have found."""
    player, run = engine.player, engine.game_world.run
    lines = [f"You are at {player.x}, {player.y} (layer {engine.game_world.current_z})", ""]
    places = []
    if run.wreck:
        places.append(("Your ship", run.wreck))
    if run.pod:
        places.append(("Sponsor cargo pod", run.pod))
    for index, at in sorted((run.flags.get("sites") or {}).items()):
        if run.knowledge.is_known(f"ruin:{index}"):
            places.append((f"Precursor ruin {index + 1}", at))
    for name, (x, y) in places:
        lines.append(f"{name}: {bearing(x - player.x, y - player.y)}")
    return lines


def known_places(engine) -> list:
    """`[(name, (x, y), color, sprite)]`: the places the player knows of (ship, cargo pod, ruins and gate found); `sprite` is the
    (column, row) of the picture the world map draws for it, the same one the place has in the world."""
    import species as defs
    from structures import RUIN_COUNT
    run = engine.game_world.run
    places = []
    if run.wreck:
        places.append(("Your ship", run.wreck, (255, 200, 80), defs.SHIP.sprite))
    if run.pod:
        places.append(("Sponsor cargo pod", run.pod, (120, 220, 255), defs.CARGO_POD.sprite))
    for index, at in sorted((run.flags.get("sites") or {}).items()):
        if run.knowledge.is_known(f"ruin:{index}"):
            if index >= RUIN_COUNT:
                places.append(("Precursor gate", at, (120, 230, 200), defs.GATE.sprite))
            else:
                places.append((f"Precursor ruin {index + 1}", at, (200, 140, 255), defs.RUIN.sprite))
    return places


class WorldMapHandler(AskUserEventHandler):
    """The world map (M): one cell per chunk of the surface, from what the player has seen (see `worldmap`). Chunks in view are
    bright, explored ones dim, undiscovered ones blank. Arrows move the cursor, +/- zoom, Home goes back to you, M or Esc close.
    Drawing it never generates terrain."""

    SIDE = 32
    """Width (cells) of the side panel; below `MIN_FOR_SIDE` cells of window it moves under the map."""
    MIN_FOR_SIDE = 72
    UNDISCOVERED = (14, 18, 30)
    BRIGHTEN = 1.7       # (the recorded colours are the lit tile colours, which are dark on screen)

    def __init__(self, engine):
        super().__init__(engine)
        from chunks import chunk_key
        player = engine.player
        self.home = chunk_key(player.x, player.y)
        self.cursor = self.home
        self.zoom = None          # pixels per chunk; None = fit the known world
        self.origin = None        # chunk at the top-left of the map area; None = centred on the cursor
        self._geometry = None

    # ── geometry ─────────────────────────────────────────────────────────────────────
    def _layout(self, canvas):
        """Cell rectangles (in cells) of the map area and the side panel, and the window frame."""
        width, height = canvas.width, canvas.height
        wx, wy, ww, wh = 1, 1, max(width - 2, 20), max(height - 2, 10)
        side = self.SIDE if ww >= self.MIN_FOR_SIDE else 0
        return (wx, wy, ww, wh), side

    def _cell_px(self, known, area_px):
        import worldmap
        if self.zoom:
            return self.zoom
        x0, y0, x1, y1 = worldmap.bounds(known, [self.home, self.cursor])
        return worldmap.fit_cell(x1 - x0 + 3, y1 - y0 + 3, *area_px)

    def _view(self, known, area_px, cell):
        """`(kx0, ky0, columns, rows)`: the chunk rectangle shown, kept around the cursor (or the fitted known world)."""
        import worldmap
        columns, rows = max(area_px[0] // cell, 1), max(area_px[1] // cell, 1)
        x0, y0, x1, y1 = worldmap.bounds(known, [self.home, self.cursor])
        if not self.zoom and x1 - x0 + 3 <= columns and y1 - y0 + 3 <= rows:     # all of it fits: centre it
            return x0 - (columns - (x1 - x0 + 1)) // 2, y0 - (rows - (y1 - y0 + 1)) // 2, columns, rows
        cx, cy = self.cursor
        return cx - columns // 2, cy - rows // 2, columns, rows

    # ── drawing ──────────────────────────────────────────────────────────────────────
    def on_render(self, canvas) -> None:
        import pygame
        import worldmap
        from chunks import chunk_key
        from ui import CELL, Theme
        super().on_render(canvas)
        engine = self.engine
        known = worldmap.records(engine.game_world.run)
        (wx, wy, ww, wh), side = self._layout(canvas)
        ix, iy, iw, ih = canvas.window(wx, wy, ww, wh, title="World map", hints=[("Arrows", "cursor"), ("+/-", "zoom"), ("Home", "you"), ("M", "close")])
        map_w = iw - (side + 1 if side else 0)
        map_h = ih - (0 if side else 7)
        area = pygame.Rect(ix * CELL, iy * CELL, map_w * CELL, map_h * CELL)
        cell = self._cell_px(known, (area.width, area.height))
        kx0, ky0, columns, rows = self._view(known, (area.width, area.height), cell)
        self._geometry = (area, cell, kx0, ky0)
        surface = canvas.surface
        surface.fill(self.UNDISCOVERED, area)
        visible = worldmap.visible_chunks(engine) if engine.game_map.z == 0 else set()
        clip = surface.get_clip()
        surface.set_clip(area)
        for (kx, ky), info in known.items():
            if not (kx0 <= kx < kx0 + columns and ky0 <= ky < ky0 + rows):
                continue
            rect = pygame.Rect(area.x + (kx - kx0) * cell, area.y + (ky - ky0) * cell, cell, cell)
            live = (kx, ky) in visible
            dim = 1.0 if live else 0.7
            fade = 0.55 + 0.45 * min(1.0, info.share * 2.0)         # a chunk seen only in part is paler
            shown = tuple(min(255, int(min(255, c * self.BRIGHTEN) * dim * fade + u * (1 - dim * fade))) for c, u in zip(info.color, self.UNDISCOVERED))
            surface.fill(shown, rect.inflate(-1, -1) if cell >= 6 else rect)
            if live and cell >= 6:
                pygame.draw.rect(surface, (235, 245, 255), rect.inflate(-1, -1), 1)
        for name, (x, y), tint, sprite in known_places(engine):
            key = chunk_key(x, y)
            if key in known and kx0 <= key[0] < kx0 + columns and ky0 <= key[1] < ky0 + rows:
                centre = (area.x + (key[0] - kx0) * cell + cell // 2, area.y + (key[1] - ky0) * cell + cell // 2)
                self._draw_icon(canvas, surface, sprite, tint, centre, cell)
        px, py = self.home
        if kx0 <= px < kx0 + columns and ky0 <= py < ky0 + rows:             # you: a red-ringed white mark (blinks a little)
            rect = pygame.Rect(area.x + (px - kx0) * cell, area.y + (py - ky0) * cell, cell, cell)
            pygame.draw.rect(surface, (255, 70, 70), rect, max(1, cell // 8))
            mark = rect.inflate(-max(cell // 2, 2), -max(cell // 2, 2))
            surface.fill((255, 255, 255), mark)
        cx, cy = self.cursor
        if kx0 <= cx < kx0 + columns and ky0 <= cy < ky0 + rows:
            rect = pygame.Rect(area.x + (cx - kx0) * cell, area.y + (cy - ky0) * cell, cell, cell)
            pygame.draw.rect(surface, (255, 220, 90), rect, 2)
        surface.set_clip(clip)
        self._side_panel(canvas, known, ix, iy, iw, ih, side, visible)

    ICON_MIN_CELL = 8
    """Below this chunk size (pixels) a place is a plain coloured square; from here up it is its own picture."""

    def _draw_icon(self, canvas, surface, sprite, tint, centre, cell: int) -> None:
        """A place on the map: its sprite from the sheet in its colour on a dark disc, so it reads on any ground."""
        import pygame
        import atlas
        if cell < self.ICON_MIN_CELL:
            spot = pygame.Rect(0, 0, max(cell // 3, 2), max(cell // 3, 2))
            spot.center = centre
            pygame.draw.rect(surface, tint, spot)
            return
        size = max(12, min(cell + cell // 2, 36))
        picture = pygame.transform.scale(canvas.sprites.get(atlas.sprite_id(*sprite), False, tint), (size, size))
        pygame.draw.circle(surface, (10, 12, 20), centre, size // 2 + 1)
        pygame.draw.circle(surface, tint, centre, size // 2 + 1, 1)
        surface.blit(picture, picture.get_rect(center=centre))

    def _side_panel(self, canvas, known, ix, iy, iw, ih, side, visible) -> None:
        from ui import Theme
        engine = self.engine
        player = engine.player
        if side:
            x, y, width = ix + iw - side, iy, side
        else:
            x, y, width = ix, iy + ih - 6, iw
        lines = []
        kx, ky = self.cursor
        info = known.get(self.cursor)
        lines.append((f"Chunk {kx}, {ky}", Theme.TITLE))
        if info is None:
            lines.append(("Undiscovered", Theme.DIM))
        else:
            import biomes
            state = "in view" if self.cursor in visible else "explored"
            lines.append((f"{state}, {round(info.share * 100)}% seen", Theme.TEXT))
            if info.biome in biomes.BIOMES:
                lines.append((biomes.BIOMES[info.biome].name, Theme.KEY))
            terrain = [f"{round(info.water * 100)}% water"] if info.water >= 0.05 else []
            if info.rock >= 0.05:
                terrain.append(f"{round(info.rock * 100)}% rock")
            if terrain:
                lines.append((", ".join(terrain), Theme.DIM))
        if side:
            lines.append(("", Theme.TEXT))
            lines.append((f"You: {player.x}, {player.y}" + (f" (layer {engine.game_world.current_z})" if engine.game_world.current_z else ""), Theme.TEXT))
            for name, (px, py), tint, _ in known_places(engine):
                lines.append((f"{name}: {bearing(px - player.x, py - player.y)}", tint))
            lines.append(("", Theme.TEXT))
            lines.append(("White frame: in view now. Dim: explored. Blank: undiscovered.", Theme.DIM))
        else:
            lines.append((f"You: {player.x}, {player.y}", Theme.TEXT))
        row = y
        for text, tint in lines:
            for part in (canvas.wrap(text, width) if text else [""]):
                if row >= iy + ih:
                    return
                canvas.print(x, row, part, fg=tint)
                row += 1

    # ── input ────────────────────────────────────────────────────────────────────────
    STEP = {Key.LEFT: (-1, 0), Key.RIGHT: (1, 0), Key.UP: (0, -1), Key.DOWN: (0, 1)}

    def ev_keydown(self, event):
        key, big = event.sym, bool(event.mod & (events.Mod.SHIFT))
        if key in self.STEP:
            n = 5 if big else 1
            self.cursor = (self.cursor[0] + self.STEP[key][0] * n, self.cursor[1] + self.STEP[key][1] * n)
            return None
        if key == Key.HOME or key == Key.PERIOD:
            self.cursor = self.home
            return None
        if key in (Key.PLUS, Key.EQUALS, Key.KP_PLUS):
            self.zoom = min((self.zoom or self._fitted()) + 2, 32)
            return None
        if key in (Key.MINUS, Key.KP_MINUS):
            self.zoom = max((self.zoom or self._fitted()) - 2, 3)
            return None
        if key in (Key.M, Key.ESCAPE):
            return self.on_exit()
        return None            # (any other key does nothing: the map is for looking)

    def _fitted(self) -> int:
        return self._geometry[1] if self._geometry else 8

    def _chunk_at(self, position):
        if not self._geometry:
            return None
        from ui import CELL
        area, cell, kx0, ky0 = self._geometry
        px, py = int(position[0]) * CELL + CELL // 2, int(position[1]) * CELL + CELL // 2
        if not area.collidepoint(px, py):
            return None
        return kx0 + (px - area.x) // cell, ky0 + (py - area.y) // cell

    def ev_mousemotion(self, event):
        key = self._chunk_at(event.position)
        if key is not None:
            self.cursor = key
        return None

    def ev_mousebuttondown(self, event):
        if event.button == events.MouseButton.LEFT:
            key = self._chunk_at(event.position)
            if key is not None:
                self.cursor = key
            return None
        return super().ev_mousebuttondown(event)


NavigationHandler = WorldMapHandler       # (M used to open a plain list of places)


CONTROLS = (
    ("Arrows / numpad", "move (Shift/Ctrl move the look cursor further)"),
    ("Space", "wait a turn"),
    ("G / I / D", "pick up / use inventory / drop"),
    ("R", "craft (a recipe is a set of material roles; names stay provisional until you learn them)"),
    ("F", "use what is next to you: ship, wreck, cargo pod, ruin, gate, beacon"),
    ("X / T", "dig the ground / sharpen your tool"),
    ("S", "scan a visible tile or creature (O: codex of what you know)"),
    ("Z", "sleep in a bed (Casual mode saves there)"),
    ("P / K", "fire the pistol at a target / use the bounty tracker"),
    ("M / C / V", "world map and navigation / character / message history"),
    ("L, <, >", "take stairs"),
    ("H", "this help"),
)


class HelpHandler(AskUserEventHandler):
    """The key list (H)."""

    def on_render(self, canvas: Canvas) -> None:
        from ui import Theme
        super().on_render(canvas)
        import debug
        rows = [(keys, canvas.wrap(what, 40)) for keys, what in CONTROLS + (debug.HELP_LINES if debug.enabled() else ())]
        height = sum(len(lines) for _, lines in rows) + len(rows) + 5
        ix, iy, iw, ih = canvas.window(4, 3, 62, height, title="Controls", hints=[("Esc", "close")])
        row = iy
        for keys, lines in rows:
            canvas.print(ix, row, keys, fg=Theme.KEY)
            for part in lines:
                canvas.print(ix + 17, row, part, fg=Theme.TEXT)
                row += 1
            row += 1


class InGameSettings(AskUserEventHandler):
    """The settings screen opened from the pause menu: the same rows as the main menu's, drawn over the game. Esc saves and goes back."""

    def __init__(self, engine):
        super().__init__(engine)
        import setup_game
        self.inner = setup_game.SettingsMenu(engine.session)
        self.inner.overlay = True

    def on_render(self, canvas) -> None:
        stack = self.session.handlers
        below = next((h for h in stack if h is not self and not isinstance(h, (PauseMenu, InGameSettings))), None)
        (below or super()).on_render(canvas)
        canvas.dim(3)
        self.inner.on_render(canvas)

    def ev_keydown(self, event):
        if event.sym == events.Key.ESCAPE:
            import settings
            settings.save(self.inner.settings)
            return self.on_exit()
        self.inner.ev_keydown(event)
        return None

    def ev_mousebuttondown(self, event):
        self.inner.ev_mousebuttondown(event)
        return None


class PauseMenu(AskUserEventHandler):
    """Esc on the map: resume, or save and leave (to the main menu, or out of the game)."""

    OPTIONS = ("Resume", "Settings", "Save & Quit to Main Menu", "Save & Quit Game")

    def __init__(self, engine):
        super().__init__(engine)
        import widgets
        self.choices = widgets.Choices(self.OPTIONS)

    def on_render(self, canvas) -> None:
        parent = self.session.handlers[self.session.handlers.index(self) - 1] if self in self.session.handlers and self.session.handlers.index(self) > 0 else None
        (parent or super()).on_render(canvas)
        canvas.dim(3)
        width, height = 36, 11
        ix, iy, iw, ih = canvas.window((canvas.width - width) // 2, (canvas.height - height) // 2, width, height, title="Paused",
                                       hints=[("Up/Down", "choose"), ("Enter", "select"), ("Esc", "resume")])
        self.choices.draw(canvas, ix, iy + 1, iw)

    def _choose(self, index: int):
        if index == 0:
            return self.on_exit()
        if index == 1:
            return InGameSettings(self.engine)
        if index == 2:
            import setup_game
            self.engine.save_as("savegame")
            menu = setup_game.MainMenu(self.session)
            self.session.reset(menu)
            return menu
        raise SystemExit()   # the main loop saves on the way out

    def ev_keydown(self, event):
        if event.sym == events.Key.ESCAPE:
            return self.on_exit()
        index = self.choices.handle(event)
        return None if index is None else self._choose(index)

    def ev_mousemotion(self, event):
        self.choices.handle(event)

    def ev_mousebuttondown(self, event):
        index = self.choices.handle(event)
        return None if index is None else self._choose(index)


class ContextMenu(AskUserEventHandler):
    """Right click on the map: every action that makes sense for what lies on that tile (scan, grab, attack, look inside, walk there).
    A convenience on top of the roguelike keys, which all keep working."""

    def __init__(self, engine, x: int, y: int, position=(0, 0)):
        super().__init__(engine)
        import widgets
        self.x, self.y, self.position = x, y, position
        self.entries = self.options(engine, x, y)
        self.choices = widgets.Choices([label for label, _ in self.entries], gap=0)

    @staticmethod
    def options(engine, x: int, y: int) -> list:
        """`[(label, make)]`: `make()` gives the action (or screen) to run when it is chosen."""
        import actions
        import render_functions
        from entity import EntityCategory, Item
        player, world = engine.player, engine.game_map
        near = max(abs(x - player.x), abs(y - player.y)) <= 1
        out = []
        seen = world.is_visible(x, y)
        things = [e for e in world.stack_at(x, y) if e is not player and not getattr(e, "decal", False)][:5] if seen else []
        for thing in things:
            name = thing.get_title()
            unit = getattr(thing, "category", None) is EntityCategory.UNIT
            alive = unit and getattr(thing, "is_alive", False)
            if alive:
                out.append((f"Attack {name}", lambda: actions.BumpAction(player, x, y)))
            if isinstance(thing, Item) or getattr(thing, "scenery", False):
                if near:
                    out.append((f"Grab {name}", lambda t=thing: actions.PickupAction(player, t)))
            elif getattr(thing, "has_inventory", False) and near and not alive:
                import input_handlers
                label = "Look inside" if unit else "Gather from"
                out.append((f"{label} {name}", lambda t=thing: input_handlers.InventoryLootHandler(engine, player, t.inventory)))
            if not getattr(thing, "scenery", False):
                out.append((f"Scan {name}", lambda t=thing: actions.ScanThingAction(player, t)))
        if not things and seen and render_functions.rock_face_at(engine, x, y) is not None:
            out.append(("Scan rock", lambda: actions.ScanAction(player, x, y)))
        elif not things and seen and int(world.tile_at(x, y)["liquid"]):
            out.append(("Scan liquid", lambda: actions.ScanAction(player, x, y)))
        if world.is_walkable(x, y) and (x, y) != (player.x, player.y):
            out.append(("Walk here", lambda: actions.BumpAction(player, x, y)))
        return out or [("Nothing to do here", lambda: None)]

    def on_render(self, canvas) -> None:
        parent = self.session.handlers[self.session.handlers.index(self) - 1] if self in self.session.handlers and self.session.handlers.index(self) > 0 else None
        (parent or super()).on_render(canvas)
        width = max(16, max(len(label) for label, _ in self.entries) + 4)
        height = len(self.entries) + 2
        x = max(0, min(int(self.position[0]), canvas.width - width))
        y = max(0, min(int(self.position[1]), canvas.height - height))
        ix, iy, iw, ih = canvas.window(x, y, width, height, title="Actions")
        self.choices.draw(canvas, ix, iy, iw)

    def _choose(self, index: int):
        make = self.entries[index][1]
        self.resolve_handler()                    # this menu is done; what comes out runs on the map
        return make()

    def ev_keydown(self, event):
        if event.sym == events.Key.ESCAPE:
            return self.on_exit()
        index = self.choices.handle(event)
        return None if index is None else self._choose(index)

    def ev_mousemotion(self, event):
        self.choices.handle(event)

    def ev_mousebuttondown(self, event):
        if event.button == events.MouseButton.RIGHT:
            return self.on_exit()
        if event.button == events.MouseButton.LEFT and self.choices.at(event.position) is None:
            return self.on_exit()                  # a click away from the menu closes it
        index = self.choices.handle(event)
        return None if index is None else self._choose(index)
