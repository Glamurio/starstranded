"""Debug sprite editor (main menu): pick a thing on the left, click a cell of the sprite sheet on the right to draw it with
that sprite. Every click is saved at once to data/sprites.json (see spriteconfig.py)."""
from __future__ import annotations

import string
from typing import Optional

import pygame

import atlas
import events
import input_handlers
import spriteconfig
import widgets
from events import Key, Mod
from ui import CELL, RIGHT, Canvas, Theme

LIST_W = 22
SHEET_STEP = 10   # cells scrolled per key press


class SpriteEditor(input_handlers.BaseEventHandler):
    """Type to search the list; Up/Down choose; click the sheet to assign; Left/Right/PgUp/PgDn scroll it; Ctrl+R resets."""

    X, Y, WIDTH, HEIGHT = 1, 1, 78, 43

    def __init__(self, session=None, back=None):
        self.back = back
        self.query = ""
        self.list = widgets.ListView(reserved=string.ascii_lowercase)
        self.col0 = 0
        self.row0 = 0
        self.sheet_rect = pygame.Rect(0, 0, 0, 0)   # in cells, set while drawing
        self.hover: Optional[tuple] = None
        self.message = ""
        super().__init__(session)
        self.refresh()
        if self.session is not None:
            self.session.start_text_input()

    # ── data ───────────────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        rows, last = [], None
        for key in spriteconfig.catalog():
            if self.query and self.query not in spriteconfig.label(key):
                continue
            kind = key.split(".", 1)[0]
            if kind != last:
                rows.append(widgets.Row(kind, header=True))
                last = kind
            pos = spriteconfig.current(key)
            icon = (pos[1] * atlas.COLUMNS + pos[0], (255, 255, 255), False) if pos else None
            changed = spriteconfig.is_changed(key)
            rows.append(widgets.Row(key.split(".", 1)[1].replace(".", " "), icon=icon, data=key,
                                    right="*" if changed else "", color=Theme.KEY if changed else None))
        self.list.set_rows(rows)

    @property
    def key(self) -> Optional[str]:
        row = self.list.current
        return row.data if row is not None else None

    def assign(self, pos) -> None:
        key = self.key
        if key is None:
            return
        spriteconfig.set(key, pos)
        self.message = f"{key} = {pos[0]},{pos[1]}"
        self.refresh()

    def reset(self) -> None:
        key = self.key
        if key is not None:
            spriteconfig.reset(key)
            self.message = f"{key} reset"
            self.refresh()

    def cell_at(self, x: int, y: int) -> Optional[tuple]:
        """The sheet cell under the logical cell (x, y), if it is inside the sheet viewport."""
        rect = self.sheet_rect
        if not rect.collidepoint(x, y):
            return None
        pos = (self.col0 + x - rect.x, self.row0 + y - rect.y)
        return pos if pos[0] < atlas.COLUMNS and pos[1] < atlas.ROWS else None

    def scroll(self, dx: int, dy: int) -> None:
        rect = self.sheet_rect
        self.col0 = max(0, min(self.col0 + dx, max(0, atlas.COLUMNS - rect.w)))
        self.row0 = max(0, min(self.row0 + dy, max(0, atlas.ROWS - rect.h)))

    # ── drawing ────────────────────────────────────────────────────────────────────
    def on_render(self, canvas: Canvas) -> None:
        import setup_game
        canvas.blit_image(setup_game.background_image())
        ix, iy, iw, ih = canvas.window(self.X, self.Y, self.WIDTH, self.HEIGHT, title="Sprite editor", hints=[
            ("type", "search"), ("Up/Down", "thing"), ("click", "assign"), ("Left/Right/PgUp/PgDn", "scroll sheet"),
            ("Ctrl+R", "reset"), ("Esc", "back")])
        canvas.print(ix, iy, "search: " + self.query + "_", fg=Theme.TITLE)
        self.list.draw(canvas, ix, iy + 2, LIST_W, ih - 2)
        rx, rw = ix + LIST_W + 1, iw - LIST_W - 1
        pygame.draw.line(canvas.surface, Theme.BORDER_DIM, (rx * CELL - 12, iy * CELL), (rx * CELL - 12, (iy + ih) * CELL), 1)
        key = self.key
        if key is None:
            canvas.print(rx, iy, "Nothing matches.", fg=Theme.DIM)
        else:
            current, default = spriteconfig.current(key), spriteconfig.DEFAULTS.get(key)
            sprite = current[1] * atlas.COLUMNS + current[0]
            widgets.sprite_slot(canvas, rx, iy, sprite, size=4)
            canvas.print(rx + 5, iy, spriteconfig.label(key), fg=Theme.TITLE)
            canvas.print(rx + 5, iy + 1, f"now {current[0]},{current[1]}   default {default[0]},{default[1]}"
                         + ("   (changed)" if spriteconfig.is_changed(key) else ""), fg=Theme.TEXT)
            hover = self.hover
            canvas.print(rx + 5, iy + 2, f"cell under mouse: {hover[0]},{hover[1]}" if hover else self.message, fg=Theme.DIM)
        top = iy + 5
        self.sheet_rect = pygame.Rect(rx, top, min(rw, atlas.COLUMNS), min(iy + ih - top, atlas.ROWS))
        rect = self.sheet_rect
        self.scroll(0, 0)   # re-clamp after a resize
        canvas.surface.fill(Theme.PANEL, canvas.cell_rect(rect.x, rect.y, rect.w, rect.h))
        sheet = atlas.get_atlas().sheet
        area = pygame.Rect(self.col0 * CELL, self.row0 * CELL, rect.w * CELL, rect.h * CELL).clip(sheet.get_rect())
        canvas.surface.blit(sheet, (rect.x * CELL, rect.y * CELL), area)
        if key is not None:   # outline the chosen cell (if scrolled into view) and the one under the mouse
            for pos, colour in ((current, Theme.KEY), (self.hover, Theme.HILITE_TEXT)):
                if pos is None:
                    continue
                x, y = rect.x + pos[0] - self.col0, rect.y + pos[1] - self.row0
                if rect.collidepoint(x, y):
                    pygame.draw.rect(canvas.surface, colour, canvas.cell_rect(x, y), 1)
        canvas.print(rx + rw - 1, top - 1, f"sheet {self.col0},{self.row0}", fg=Theme.DIM, alignment=RIGHT)

    # ── input ──────────────────────────────────────────────────────────────────────
    def ev_keydown(self, event: events.KeyDown):
        if event.sym == Key.ESCAPE:
            import setup_game
            return self.back if self.back is not None else setup_game.MainMenu(self.session)
        if event.sym == Key.R and event.mod & Mod.CTRL:
            self.reset()
        elif event.sym == Key.UP:
            self.list.move(-1)
        elif event.sym == Key.DOWN:
            self.list.move(1)
        elif event.sym == Key.LEFT:
            self.scroll(-SHEET_STEP, 0)
        elif event.sym == Key.RIGHT:
            self.scroll(SHEET_STEP, 0)
        elif event.sym == Key.PAGEUP:
            self.scroll(0, -SHEET_STEP)
        elif event.sym == Key.PAGEDOWN:
            self.scroll(0, SHEET_STEP)
        elif event.sym == Key.BACKSPACE and self.query:
            self.query = self.query[:-1]
            self.refresh()
        return None

    def ev_textinput(self, event: events.TextInput):
        self.query += event.text.lower()
        self.refresh()

    def ev_mousemotion(self, event: events.MouseMotion):
        self.hover = self.cell_at(*event.position)

    def ev_mousebuttondown(self, event: events.MouseButtonDown):
        x, y = event.position
        pos = self.cell_at(x, y)
        if pos is not None:
            self.assign(pos)
            return None
        index = self.list.row_at(x * CELL + CELL // 2, y * CELL + CELL // 2)
        if index is not None:
            self.list.selected = index
        return None
