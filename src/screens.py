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
        super().on_render(canvas)
        x, y, width, height = layout.SIDE_PANEL_WIDTH, 2, 70, 28
        canvas.draw_frame(x=x, y=y, width=width, height=height, title=self.TITLE, clear=True, fg=color.menu_text, bg=color.nigh_black)
        run = self.run
        tabs = "   ".join((f"[{name}]" if i == self.tab else f" {name} ") for i, name in enumerate(TABS))
        canvas.print(x + 2, y + 1, tabs, fg=color.yellow)
        canvas.print(x + 2, y + 2, f"Credits: {run.credits}", fg=color.menu_text)
        rows = self.rows()
        self.row = max(0, min(self.row, len(rows) - 1))
        line = y + 4
        if self.tab == 0:
            if not rows:
                canvas.print(x + 2, line, "No open contracts.", fg=color.impossible)
            for i, c in enumerate(rows):
                carry = len(sponsors.matching_items(self.engine.player, c)) if c.category != sponsors.KNOWLEDGE_CONTRACT else \
                    max(0, sponsors.knowledge_count(run) - run.knowledge_spent)
                text = f"{c.title}  {c.filled}/{c.count}  (carrying {carry})  +{c.reputation} rep, {c.credits} cr"
                fg, bg = (color.black, color.white) if i == self.row else (color.menu_text, color.nigh_black)
                canvas.print(x + 2, line + i, text[:width - 4], fg=fg, bg=bg)
            canvas.print(x + 2, y + height - 3, "ENTER: hand in what you carry   TAB: next page   ESC: close", fg=color.impossible)
        elif self.tab == 1:
            for i, (key, (price, name)) in enumerate(rows):
                fg, bg = (color.black, color.white) if i == self.row else (color.menu_text, color.nigh_black)
                canvas.print(x + 2, line + i, f"{name:<24}{price:>4} cr", fg=fg, bg=bg)
            canvas.print(x + 2, y + height - 3, "ENTER: buy   TAB: next page   ESC: close", fg=color.impossible)
        else:
            for i, spec in enumerate(rows):
                rep = run.reputation.get(spec.key, 0)
                mark = " <- your sponsor" if spec.key == run.sponsor else ""
                fg, bg = (color.black, color.white) if i == self.row else (color.menu_text, color.nigh_black)
                canvas.print(x + 2, line + i * 2, f"{spec.name:<24}reputation {rep:>4}{mark}", fg=fg, bg=bg)
            spec = rows[self.row]
            for k, text in enumerate(textwrap.wrap(spec.blurb + " Wants: " + ", ".join(spec.wants) + ".", width - 4)):
                canvas.print(x + 2, line + 11 + k, text, fg=color.menu_text)
            ready = sponsors.rescue_ready(run, run.sponsor)
            canvas.print(x + 2, y + height - 4,
                         f"Rescue: reputation {run.reputation.get(run.sponsor, 0)}/{sponsors.RESCUE_REPUTATION}, "
                         f"{'ready - build a beacon' if ready else 'not yet'}", fg=color.green if ready else color.impossible)

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
        canvas.draw_frame(x=2, y=2, width=canvas.width - 4, height=canvas.height - 4, title="The End", clear=True,
                          fg=color.white, bg=color.black)
        row = 5
        for i, text in enumerate(endings.epilogue(self.engine)):
            for part in (textwrap.wrap(text, canvas.width - 12) or [""]):
                canvas.print(canvas.width // 2, row, part, fg=color.yellow if i == 0 else color.menu_text, bg=color.black,
                             alignment=__import__("ui").CENTER)
                row += 1
        canvas.print(canvas.width // 2, canvas.height - 5, "Press any key", fg=color.impossible, bg=color.black,
                     alignment=__import__("ui").CENTER)

    def ev_keydown(self, event: events.KeyDown):
        if event.sym in (Key.LSHIFT, Key.RSHIFT, Key.LCTRL, Key.RCTRL, Key.LALT, Key.RALT):
            return None
        self.finish()

    def ev_quit(self, event) -> None:
        self.finish()

    def finish(self) -> None:
        import shutil, os
        for path in ("savegame", "savegame_bed"):
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
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
        super().on_render(canvas)
        lines = navigation_lines(self.engine)
        canvas.draw_frame(x=layout.SIDE_PANEL_WIDTH, y=2, width=60, height=len(lines) + 4, title="Navigation", clear=True,
                          fg=color.menu_text, bg=color.nigh_black)
        for i, line in enumerate(lines):
            canvas.print(layout.SIDE_PANEL_WIDTH + 2, 4 + i, line, fg=color.menu_text)


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
        super().on_render(canvas)
        canvas.draw_frame(x=2, y=2, width=76, height=len(CONTROLS) + 6, title="Controls", clear=True, fg=color.menu_text,
                          bg=color.nigh_black)
        for i, (keys, what) in enumerate(CONTROLS):
            canvas.print(4, 4 + i, f"{keys:<16}{what}"[:72], fg=color.menu_text)
