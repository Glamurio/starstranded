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


class NavigationHandler(AskUserEventHandler):
    """The navigation screen (M): your position and the way to the places you know."""

    def on_render(self, canvas: Canvas) -> None:
        from ui import Theme
        super().on_render(canvas)
        lines = navigation_lines(self.engine)
        ix, iy, iw, ih = canvas.window(8, 5, 54, len(lines) + 8, title="Navigation", hints=[("Esc", "close")])
        for i, line in enumerate(lines):
            canvas.print(ix, iy + i, line, fg=Theme.TEXT if i else Theme.TITLE)


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
    ("M / C / V", "navigation / character / message history"),
    ("L, <, >", "take stairs"),
    ("H", "this help"),
)


class HelpHandler(AskUserEventHandler):
    """The key list (H)."""

    def on_render(self, canvas: Canvas) -> None:
        from ui import Theme
        super().on_render(canvas)
        rows = [(keys, canvas.wrap(what, 40)) for keys, what in CONTROLS]
        height = sum(len(lines) for _, lines in rows) + len(rows) + 5
        ix, iy, iw, ih = canvas.window(4, 3, 62, height, title="Controls", hints=[("Esc", "close")])
        row = iy
        for keys, lines in rows:
            canvas.print(ix, row, keys, fg=Theme.KEY)
            for part in lines:
                canvas.print(ix + 17, row, part, fg=Theme.TEXT)
                row += 1
            row += 1
