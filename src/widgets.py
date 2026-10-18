"""Pieces the windows are built from (after Caves of Qud): lists with letter hotkeys and category headers, framed sprite
slots, detail text, and the tab row shared by the main screens.

Everything draws through `ui.Canvas` in cells, with text set in pixels (see `ui`). The functions are pure drawing (plus a
little state for the list); the screens in `input_handlers` own the game logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

import pygame

import ui
from ui import CELL, Theme

HOTKEYS = "abcdefghijklmnopqrstuvwxyz"

# The main screens, in the order Tab cycles through them: (name, handler factory name in input_handlers).
TABS: Tuple[Tuple[str, str], ...] = (
    ("Inventory", "InventoryActivateHandler"),
    ("Character", "CharacterScreenEventHandler"),
    ("Recipes", "CraftingMenuHandler"),
    ("Codex", "CodexHandler"),
    ("Log", "HistoryViewer"),
)


def tab_titles() -> List[Tuple[str, str]]:
    """`(key, name)` pairs for the tab row (the key shown is the one that opens the screen from the map)."""
    keys = {"Inventory": "i", "Character": "c", "Recipes": "r", "Codex": "o", "Log": "v"}
    return [(keys[name], name) for name, _ in TABS]


@dataclass
class Row:
    """One line of a list: a header (category name) or a selectable entry."""
    label: str
    header: bool = False
    icon: Optional[Tuple[int, tuple, bool]] = None   # (sprite id, tint, flipped)
    right: str = ""
    color: Optional[tuple] = None
    data: object = None


class ListView:
    """A scrolling list: rows are headers or entries; entries get letter hotkeys a, b, c ... (skipping `reserved`)."""

    def __init__(self, rows: Sequence[Row] = (), reserved: str = "") -> None:
        self.reserved = reserved
        self.rows: List[Row] = []
        self.keys: dict = {}
        self.selected: Optional[int] = None   # index into rows
        self.top = 0
        self.hits: List[Tuple[pygame.Rect, int]] = []
        self.set_rows(rows)

    # ── content ────────────────────────────────────────────────────────────────────
    def set_rows(self, rows: Sequence[Row]) -> None:
        keep = self.rows[self.selected].data if self.selected is not None and self.selected < len(self.rows) else None
        self.rows = list(rows)
        letters = [c for c in HOTKEYS if c not in self.reserved]
        self.keys = {}
        for i, row in enumerate(self.rows):
            if not row.header and letters:
                self.keys[letters.pop(0)] = i
        entries = self.entries
        if self.selected is not None and self.selected < len(self.rows) and not self.rows[self.selected].header:
            pass
        else:
            self.selected = entries[0] if entries else None
        if keep is not None:   # stay on the same entry when the list is rebuilt
            for i in entries:
                if self.rows[i].data is keep:
                    self.selected = i
        if self.selected is not None and self.selected >= len(self.rows):
            self.selected = entries[-1] if entries else None

    @property
    def entries(self) -> List[int]:
        return [i for i, row in enumerate(self.rows) if not row.header]

    @property
    def current(self) -> Optional[Row]:
        return self.rows[self.selected] if self.selected is not None and self.selected < len(self.rows) else None

    # ── navigation ─────────────────────────────────────────────────────────────────
    def move(self, step: int) -> None:
        entries = self.entries
        if not entries:
            self.selected = None
            return
        if self.selected not in entries:
            self.selected = entries[0] if step > 0 else entries[-1]
            return
        self.selected = entries[(entries.index(self.selected) + step) % len(entries)]

    def select_key(self, character: str) -> Optional[int]:
        index = self.keys.get(character.lower())
        if index is not None:
            self.selected = index
        return index

    def key_of(self, index: int) -> str:
        for k, i in self.keys.items():
            if i == index:
                return k
        return ""

    def row_at(self, x_px: int, y_px: int) -> Optional[int]:
        for rect, index in self.hits:
            if rect.collidepoint(x_px, y_px):
                return index
        return None

    # ── drawing ────────────────────────────────────────────────────────────────────
    def draw(self, canvas: ui.Canvas, x: int, y: int, width: int, height: int) -> None:
        """Draw into the cell rectangle (x, y, width, height); scrolls to keep the selection in view."""
        self.hits = []
        if self.selected is not None:
            if self.selected < self.top:
                self.top = self.selected
            elif self.selected >= self.top + height:
                self.top = self.selected - height + 1
        self.top = max(0, min(self.top, max(0, len(self.rows) - height)))
        text_cells = width - 4
        for row_no, index in enumerate(range(self.top, min(len(self.rows), self.top + height))):
            row = self.rows[index]
            cy = y + row_no
            if row.header:
                canvas.print(x, cy, row.label, fg=Theme.TITLE)
                px = x * CELL + canvas.font.width(row.label) + ui.CHAR_W
                pygame.draw.line(canvas.surface, Theme.BORDER_DIM, (px, cy * CELL + CELL // 2), ((x + width) * CELL - 6, cy * CELL + CELL // 2), 1)
                continue
            selected = index == self.selected
            if selected:
                canvas.fill(x, cy, width, 1, Theme.HILITE)
            fg = Theme.HILITE_TEXT if selected else (row.color or Theme.TEXT)
            key = self.key_of(index)
            if key:
                canvas.print(x, cy, key + ")", fg=Theme.KEY if not selected else Theme.HILITE_TEXT)
            if row.icon is not None:
                sprite, tint, flipped = row.icon
                canvas.sprite(x + 1, cy, sprite, tint, flipped)
            right = row.right
            right_cells = canvas.text_width(right) + 1 if right else 0
            label = row.label
            limit = canvas.chars(width - 3 - right_cells)
            if len(label) > limit:
                label = label[: max(1, limit - 1)] + "…"
            canvas.print(x + 2, cy, label, fg=fg)
            if right:
                canvas.print(x + width - 1, cy, right, fg=Theme.HILITE_TEXT if selected else Theme.DIM, alignment=ui.RIGHT)
            self.hits.append((pygame.Rect(x * CELL, cy * CELL, width * CELL, CELL), index))
        if len(self.rows) > height:   # scroll hints
            if self.top > 0:
                canvas.print(x + width - 1, y, "▲", fg=Theme.DIM, alignment=ui.RIGHT)
            if self.top + height < len(self.rows):
                canvas.print(x + width - 1, y + height - 1, "▼", fg=Theme.DIM, alignment=ui.RIGHT)


def sprite_slot(canvas: ui.Canvas, x: int, y: int, sprite: Optional[int], tint=(255, 255, 255), flipped: bool = False, size: int = 4) -> None:
    """A framed square slot (`size` x `size` cells) with the sprite drawn large in the middle."""
    rect = canvas.cell_rect(x, y, size, size)
    canvas.surface.fill(Theme.PANEL, rect)
    pygame.draw.rect(canvas.surface, Theme.BORDER_DIM, rect, 1)
    pygame.draw.rect(canvas.surface, Theme.ORNAMENT, rect.inflate(-6, -6), 1)
    if sprite is None:
        return
    image = canvas.sprites.get(sprite, flipped, tint)
    scale = max(1, (size - 1) * CELL // CELL)
    big = pygame.transform.scale(image, (CELL * scale, CELL * scale))
    canvas.surface.blit(big, (rect.centerx - big.get_width() // 2, rect.centery - big.get_height() // 2))


def text_block(canvas: ui.Canvas, x: int, y: int, width: int, height: int, lines: Sequence, scroll: int = 0) -> int:
    """Wrapped text lines into a cell rectangle; each line is a string or `(string, colour)`. Returns rows used."""
    row = 0
    for line in lines:
        text, fg = (line, Theme.TEXT) if isinstance(line, str) else line
        for part in canvas.wrap(text, width):
            if row >= height:
                return row
            canvas.print(x, y + row, part, fg=fg)
            row += 1
    return row


def item_category(item) -> str:
    """Which list heading an inventory entry sits under."""
    from components.equippable import Equippable
    from components.consumable import Consumable
    import species as defs
    from items import Ammo, Gear, Made, Stuff
    kind = getattr(item, "kind", None)
    if isinstance(item, Equippable):
        etype = getattr(kind, "equipment_type", None)
        if etype is not None and etype.name == "WEAPON":
            return "Weapons and tools"
        return "Armour"
    if kind is defs.FLASK or isinstance(item, Consumable):
        return "Food and drink"
    if isinstance(item, Stuff):
        return "Materials"
    if isinstance(item, Ammo):
        return "Ammunition"
    if isinstance(item, Made):
        return "Parts"
    return "Other"


CATEGORY_ORDER = ("Weapons and tools", "Armour", "Food and drink", "Materials", "Parts", "Ammunition", "Other")


def item_rows(entries: Sequence, equipped: Callable = lambda item: False) -> List[Row]:
    """Group items under category headers (in a fixed order) as list rows."""
    groups: dict = {}
    for item in entries:
        groups.setdefault(item_category(item), []).append(item)
    rows: List[Row] = []
    for category in CATEGORY_ORDER:
        if category not in groups:
            continue
        rows.append(Row(category, header=True))
        for item in groups[category]:
            title = item.get_title()
            right = "equipped" if equipped(item) else ("more >" if getattr(item, "has_inventory", False) else "")
            rows.append(Row(title, icon=(item.sprite_id, item.color, getattr(item, "flipped", False)), right=right, data=item))
    return rows


def item_details(engine, item) -> List:
    """What the player may read about an item: its name, what it is, and the properties they have learned."""
    import lore
    from items import Composite, Stuff
    lines: List = []
    run = engine.game_world.run
    lines.append((item.get_title(), Theme.TITLE))
    if isinstance(item, Stuff):
        lines.append((f"{item.form.lower()} of {lore.material_name(run, item.substance)}", Theme.DIM))
        lines.extend(_property_lines(run, item.substance))
    elif isinstance(item, Composite):
        lines.append((f"quality {item.quality:.1f}", Theme.DIM))
        for role, material in item.parts.items():
            lines.append((f"{role}: {lore.material_name(run, material)}", Theme.TEXT))
    elif getattr(item, "substance", None) is not None:
        lines.append((f"made of {lore.material_name(run, item.substance)}", Theme.DIM))
    hunger, thirst = getattr(item, "hunger_amount", 0), getattr(item, "thirst_amount", 0)
    if hunger or thirst:
        lines.append((f"food {hunger:+d}   drink {thirst:+d}" if hunger or thirst else "", Theme.TEXT))
    power = getattr(item, "power_bonus", 0)
    defense = getattr(item, "defense_bonus", 0)
    if power or defense:
        lines.append((f"attack {power:+d}   defence {defense:+d}", Theme.TEXT))
    return lines


def _property_lines(run, material) -> List:
    import lore
    from materials import PROPERTY_KEYS
    out = []
    for prop in PROPERTY_KEYS:
        value = material.get(prop)
        if not value:
            continue
        shown = f"{value:.1f}" if lore.property_known(run, material, prop) else "?"
        out.append((f"{prop.replace('_', ' ')}: {shown}", Theme.TEXT))
    return out


def tab_index(handler) -> int:
    import input_handlers as ih
    for i, (_, cls_name) in enumerate(TABS):
        if isinstance(handler, getattr(ih, cls_name)):
            return i
    return 0


def next_screen(handler, step: int = 1):
    """The next (or previous) main screen in the tab row; the current one is closed first."""
    import input_handlers as ih
    engine = handler.engine
    target = getattr(ih, TABS[(tab_index(handler) + step) % len(TABS)][1])
    handler.resolve_handler()
    if target is ih.InventoryActivateHandler:
        return target(engine, engine.player.inventory)
    return target(engine)
