"""Input events, independent of the windowing library.

Handlers receive these small event objects (positions are already converted to grid cells) and key
codes from `Key` / modifier bits from `Mod`, so only this module and `display.py` know about pygame's
event stream. `EventDispatch` routes an event to the matching ``ev_<type>`` method, like the tcod class
the handlers used to inherit from.
"""
from __future__ import annotations

from typing import Any, NamedTuple, Optional

import pygame


class Point(NamedTuple):
    x: int
    y: int


class Key:
    """Key codes (pygame keycodes, so letters are consecutive: ``Key.B - Key.A == 1``)."""

    UP = pygame.K_UP
    DOWN = pygame.K_DOWN
    LEFT = pygame.K_LEFT
    RIGHT = pygame.K_RIGHT
    HOME = pygame.K_HOME
    END = pygame.K_END
    PAGEUP = pygame.K_PAGEUP
    PAGEDOWN = pygame.K_PAGEDOWN
    RETURN = pygame.K_RETURN
    KP_ENTER = pygame.K_KP_ENTER
    SPACE = pygame.K_SPACE
    CLEAR = pygame.K_CLEAR
    ESCAPE = pygame.K_ESCAPE
    BACKSPACE = pygame.K_BACKSPACE
    TAB = pygame.K_TAB
    PERIOD = pygame.K_PERIOD
    COMMA = pygame.K_COMMA
    LESS = pygame.K_LESS
    LSHIFT = pygame.K_LSHIFT
    RSHIFT = pygame.K_RSHIFT
    LCTRL = pygame.K_LCTRL
    RCTRL = pygame.K_RCTRL
    LALT = pygame.K_LALT
    RALT = pygame.K_RALT
    KP_1 = pygame.K_KP1
    KP_2 = pygame.K_KP2
    KP_3 = pygame.K_KP3
    KP_4 = pygame.K_KP4
    KP_5 = pygame.K_KP5
    KP_6 = pygame.K_KP6
    KP_7 = pygame.K_KP7
    KP_8 = pygame.K_KP8
    KP_9 = pygame.K_KP9


for _letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    setattr(Key, _letter, getattr(pygame, "K_" + _letter.lower()))


class Mod:
    LSHIFT = pygame.KMOD_LSHIFT
    RSHIFT = pygame.KMOD_RSHIFT
    LCTRL = pygame.KMOD_LCTRL
    RCTRL = pygame.KMOD_RCTRL
    LALT = pygame.KMOD_LALT
    RALT = pygame.KMOD_RALT
    SHIFT = pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT
    CTRL = pygame.KMOD_LCTRL | pygame.KMOD_RCTRL
    ALT = pygame.KMOD_LALT | pygame.KMOD_RALT


class MouseButton:
    LEFT = 1
    MIDDLE = 2
    RIGHT = 3


class Event:
    type = "event"


class Quit(Event):
    type = "quit"


class KeyDown(Event):
    type = "keydown"

    def __init__(self, sym: int, mod: int = 0, repeat: bool = False):
        self.sym = sym
        self.mod = mod
        self.repeat = repeat

    def __repr__(self) -> str:
        return f"KeyDown(sym={self.sym}, mod={self.mod})"


class TextInput(Event):
    type = "textinput"

    def __init__(self, text: str):
        self.text = text


class MouseMotion(Event):
    """`position` and `motion` are in grid cells."""

    type = "mousemotion"

    def __init__(self, position: Point, motion: Point = Point(0, 0)):
        self.position = position
        self.motion = motion


class MouseButtonDown(Event):
    type = "mousebuttondown"

    def __init__(self, position: Point, button: int = MouseButton.LEFT):
        self.position = position
        self.button = button


class MouseWheel(Event):
    """`dy` is +1 for a notch away from you (up) and -1 towards you (down)."""

    type = "mousewheel"

    def __init__(self, dy: int):
        self.dy = dy


class WindowChanged(Event):
    """The window was resized or exposed: the screen needs repainting."""

    type = "windowchanged"


class EventDispatch:
    """Calls ``ev_<event.type>(event)``; events without a matching method fall through to `ev_default`."""

    def dispatch(self, event: Event) -> Any:
        method = getattr(self, "ev_" + event.type, None)
        if method is None:
            return self.ev_default(event)
        return method(event)

    def ev_default(self, event: Event) -> Any:
        return None

    def ev_keydown(self, event: KeyDown) -> Any:
        return None

    def ev_textinput(self, event: TextInput) -> Any:
        return None

    def ev_mousemotion(self, event: MouseMotion) -> Any:
        return None

    def ev_mousebuttondown(self, event: MouseButtonDown) -> Any:
        return None

    def ev_mousewheel(self, event: MouseWheel) -> Any:
        return None

    def ev_windowchanged(self, event: WindowChanged) -> Any:
        return None

    def ev_quit(self, event: Quit) -> Any:
        return None


def translate(raw: pygame.event.Event, to_cell, previous_cell: Optional[Point] = None) -> Optional[Event]:
    """Convert a pygame event into an `Event`, or None if the game ignores it.

    `to_cell(pixel_position)` maps window pixels to grid cells (None inside the letterbox bars).
    """
    kind = raw.type
    if kind == pygame.QUIT:
        return Quit()
    if kind == pygame.KEYDOWN:
        return KeyDown(raw.key, raw.mod, repeat=False)
    if kind == pygame.TEXTINPUT:
        return TextInput(raw.text)
    if kind == pygame.MOUSEMOTION:
        cell = to_cell(raw.pos)
        if cell is None:
            return None
        motion = Point(cell.x - previous_cell.x, cell.y - previous_cell.y) if previous_cell else Point(0, 0)
        return MouseMotion(cell, motion)
    if kind == pygame.MOUSEBUTTONDOWN:
        cell = to_cell(raw.pos)
        if cell is None or raw.button > MouseButton.RIGHT:
            return None
        return MouseButtonDown(cell, raw.button)
    if kind == pygame.MOUSEWHEEL:
        return MouseWheel(1 if raw.y > 0 else -1) if raw.y else None
    if kind in (pygame.WINDOWSIZECHANGED, pygame.WINDOWEXPOSED, pygame.VIDEORESIZE, pygame.WINDOWRESTORED):
        return WindowChanged()
    return None
