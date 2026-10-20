"""The right-hand HUD panel: place and time, status, the three survival bars, what lies under the cursor, and the log.

One engraved frame (the same border the menus use) holds everything, so the map gets the whole left side of the screen.
"""
from __future__ import annotations

import math

import pygame

import lighting
import message_log
import render_functions
import survival
from ui import CELL, RIGHT, Theme

PANEL_W = 22                # cells; the map viewport is the rest of the 80x45 screen (see `view.VIEW_W`)


def segments_lit(current: float, maximum: float, count: int = 10) -> int:
    """How many of `count` bar segments are lit: a sliver of health still lights one, an empty bar none."""
    if maximum <= 0 or current <= 0:
        return 0
    return min(count, max(1, math.ceil(count * current / maximum)))


def draw(canvas, engine) -> None:
    from view import VIEW_W
    x0 = VIEW_W
    canvas.draw_frame(x0, 0, PANEL_W, canvas.height)
    ix, iw = x0 + 2, PANEL_W - 4
    player = engine.player
    world = engine.game_world

    canvas.print(ix, 1, render_functions.layer_name(world.current_z), fg=Theme.TITLE)
    day, clock = lighting.clock_text(world.current_time, engine.config).split(", ")
    canvas.print(ix, 2, day, fg=Theme.TEXT)
    canvas.print(ix + iw - 1, 2, clock, fg=Theme.TEXT, alignment=RIGHT)
    canvas.print(ix, 3, f"X {player.x}  Y {player.y}", fg=Theme.DIM)
    row = 4
    if player.poison > 0:
        canvas.print(ix, row, "Poisoned", fg=Theme.BAD)
        row += 1
    import debug
    if debug.is_god(engine):
        canvas.print(ix, row, "GOD MODE", fg=Theme.TITLE)
        row += 1
    for text, shade in survival.status_lines(engine):
        if row > 8:
            break
        canvas.print(ix, row, text[: canvas.chars(iw)], fg=message_log.legible(shade))
        row += 1

    if player.breath is not None:       # held breath (diving, or foul air): a meter that empties
        capacity = max(1.0, player.capabilities.stat("breath_turns"))
        canvas.print(ix, 9, "Breath", fg=Theme.TEXT)
        canvas.segments(ix + 8, 9, iw - 8, segments_lit(max(0, player.breath), capacity), Theme.THIRST if player.breath > 0.3 * capacity else Theme.BAD)
    canvas.rule(x0 + 1, 10, PANEL_W - 2)
    for k, (label, value, maximum, shade) in enumerate((
        ("HP", player.hp, player.max_hp, Theme.HP),
        ("Hunger", player.hunger, player.max_hunger, Theme.HUNGER),
        ("Thirst", player.thirst, player.max_thirst, Theme.THIRST),
    )):
        top = 11 + k * 3
        canvas.print(ix, top, label, fg=Theme.TEXT)
        canvas.print(ix + iw - 1, top, f"{int(value)}/{int(maximum)}", fg=Theme.DIM, alignment=RIGHT)
        canvas.segments(ix, top + 1, iw, segments_lit(value, maximum), shade)

    canvas.rule(x0 + 1, 20, PANEL_W - 2)
    render_functions.render_names_at_mouse_location(canvas, ix, 21, engine, width=iw, rows=2)
    canvas.print(ix, 23, render_functions.hover_detail(engine)[: canvas.chars(iw)], fg=Theme.DIM)
    canvas.rule(x0 + 1, 24, PANEL_W - 2)
    import music
    song = music.now_playing()
    log_bottom = canvas.height - 2
    import resources
    place = resources.biome_label(world, engine.game_map.z, player.x, player.y)
    if place:                                                  # (the biome you stand in, under the music)
        log_bottom -= 2
        canvas.print(ix, log_bottom, "Biome:", fg=Theme.DIM)
        canvas.print(ix, log_bottom + 1, place[: canvas.chars(iw)], fg=Theme.TEXT)
    if song:
        log_bottom -= 2
        canvas.print(ix, log_bottom, "Now Playing:", fg=Theme.DIM)
        canvas.print(ix, log_bottom + 1, song[: canvas.chars(iw)], fg=Theme.TEXT)
    engine.message_log.render(canvas, x=ix, y=25, width=iw, height=log_bottom - 25)
