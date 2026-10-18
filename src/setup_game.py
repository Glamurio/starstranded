"""Handle the loading and initialization of game sessions."""
from __future__ import annotations

import exceptions
import os
import traceback
from typing import TYPE_CHECKING, Optional

import pygame

import color
import events
from events import Key, Point
from ui import CENTER, RIGHT
from engine import Engine

import input_handlers
import settings as settings_module

from utilities import is_mouse_in_rectangle

if TYPE_CHECKING:
    from ui import Canvas
    from components.unit import Unit

_background_image = None

def background_image() -> pygame.Surface:
    """The main menu's backdrop (loaded once, on first use)."""
    global _background_image
    if _background_image is None:
        _background_image = pygame.image.load("menu_background.png")
    return _background_image

def create_player() -> Unit:
    from components.unit import Player
    import components.equippable as equip

    player = Player()

    dagger = equip.Dagger(player.inventory)
    player.inventory.add(dagger)
    player.equipment.toggle_equip(dagger, add_message=False)

    leather_armor = equip.LeatherArmor(player.inventory)
    player.inventory.add(leather_armor)
    player.equipment.toggle_equip(leather_armor, add_message=False)

    return player

CULTURE_OF_RACE = {"human": "human", "selenite_people": "selenite", "mau": "mau"}
"""The naming culture of the planet's catalogue follows the player's people (see `planet`)."""


def new_game(player: Unit, session=None, mode: str = "roguelike") -> Engine:
    """Return a brand new game session as an Engine instance."""
    from world import GameWorld

    import actions
    import savegame
    savegame.remove_save(actions.BED_SAVE)   # a bed save belongs to the run that made it, never to the next one
    engine = Engine(player=player, session=session)
    engine.continued = False
    engine.game_world = GameWorld(engine=engine, culture=CULTURE_OF_RACE.get(player.kind.key, "human"))  # the seed is drawn from `random`
    engine.game_world.run.mode = mode
    sponsor = getattr(player, "sponsor", None)
    if sponsor:
        import sponsors
        sponsors.choose_sponsor(engine.game_world.run, player, sponsor, planet=engine.game_world.planet)
    engine.game_world.start()  # the surface: a chunked world around the start in chunk (0, 0)
    
    engine.message_log.add_message(
        f"Hello and welcome, {player.name}, to a planet that wants you dead. Find a way off.", color.welcome_text
    )

    import survival
    if survival.effective_temperature(engine, player) < survival.COMFORT:
        engine.message_log.add_message(
            "It is cold here. Get warm: build a campfire or a shelter, and wear what you can (H for help).",
            color.yellow)
    return engine

SAVE_PATH = "savegame"
"""The save directory (relative to the working directory, i.e. src/)."""


def load_game(path: str = SAVE_PATH, session=None) -> Engine:
    """Load a game saved with `Engine.save_as` (see `savegame.load_game`)."""
    import savegame
    engine = savegame.load_game(path, session)
    engine.continued = path == SAVE_PATH   # this run owns the active save slot (see `GameOverEventHandler.on_quit`)
    return engine


class MainMenu(input_handlers.BaseEventHandler):
    """Handle the main menu rendering and input."""

    console_height: int
    console_width: int
    menu_width = 24
    menu_i: int = 0

    buttons: dict
    button_height = 2
    button_names = ["New Game", "Continue", "Settings", "Sprite editor", "Exit"]
    button_highlight = button_names[menu_i]

    def on_init(self) -> None:
        self.buttons = {}  # per-instance (was a class-level dict shared by all menus)

    def resolve_menu(self, event: events.Event):
        """Resolves button and click logic"""

        if self.button_highlight == 'New Game':
            return CharacterCreation(self.session)
        elif self.button_highlight == 'Continue':
            try:
                try:
                    return input_handlers.MainGameEventHandler(load_game(SAVE_PATH, self.session))
                except FileNotFoundError:   # a Casual run that ended in death still has its last bed
                    import actions
                    if not os.path.isdir(actions.BED_SAVE):
                        raise
                    return input_handlers.MainGameEventHandler(load_game(actions.BED_SAVE, self.session))
            except FileNotFoundError:
                return input_handlers.PopupMessage(self, "No saved game to load.")
            except Exception as exc:
                traceback.print_exc()  # Print to stderr.
                return input_handlers.PopupMessage(self, f"Failed to load save:\n{exc}")
        elif self.button_highlight == 'Settings':
            return SettingsMenu(self.session, self)
        elif self.button_highlight == 'Sprite editor':
            import sprite_editor
            return sprite_editor.SpriteEditor(self.session, self)
        elif self.button_highlight == 'Exit':
            raise SystemExit()

    def on_render(self, canvas: Canvas) -> None:
        """The main menu: the planet backdrop, a framed window with the title and the choices."""
        from ui import Theme
        self.console_height = canvas.height
        self.console_width = canvas.width
        canvas.blit_image(background_image())
        count = len(self.button_names)
        height = 12 + count * 2
        x, y, width = (canvas.width - 34) // 2, (canvas.height - height) // 2 - 2, 34
        ix, iy, iw, ih = canvas.window(x, y, width, height, hints=[("Up/Down", "choose"), ("Enter", "select")])
        rows = canvas.print_big(canvas.width // 2, iy, "STARSTRANDED", Theme.TITLE, 44)
        canvas.print(canvas.width // 2, iy + rows + 1, "a survival roguelike on an alien world", fg=Theme.DIM, alignment=CENTER)
        has_save = os.path.isdir(SAVE_PATH) or os.path.isfile(SAVE_PATH)
        for i, text in enumerate(self.button_names):
            button_x = canvas.width // 2
            button_y = iy + rows + 4 + i * 2
            self.buttons[text] = {'x': button_x, 'y': button_y}
            selected = text == self.button_highlight
            if selected:
                canvas.fill(ix, button_y, iw, 1, Theme.HILITE)
            fg = Theme.HILITE_TEXT if selected else Theme.TEXT
            if text == "Continue" and not has_save and not selected:
                fg = Theme.DIM   # nothing to continue (it still reports so when chosen)
            canvas.print(button_x, button_y, text, fg=fg, alignment=CENTER)
        canvas.print(canvas.width // 2, canvas.height - 2, "By Ryou", fg=Theme.TITLE, alignment=CENTER)

    def ev_keydown(
        self, event: events.KeyDown
    ) -> Optional[input_handlers.BaseEventHandler]:

        if event.sym == Key.UP:
            self.menu_i = self.menu_i-1 if self.menu_i > 0 else len(self.button_names)-1
        elif event.sym == Key.DOWN:
            self.menu_i = self.menu_i+1 if not self.menu_i == len(self.button_names)-1 else 0
        self.button_highlight = self.button_names[self.menu_i]

        if event.sym in input_handlers.CONFIRM_KEYS:
            return self.resolve_menu(event)

        if event.sym in (Key.Q, Key.ESCAPE):
            raise SystemExit()

        return None

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[input_handlers.ActionOrHandler]:
        """Left click confirms a selection."""

        for text in self.button_names:
            button_pt = Point(self.buttons[text]['x'], self.buttons[text]['y'])
            in_rect = is_mouse_in_rectangle(event, button_pt, self.menu_width, self.button_height)

            if in_rect:
                return self.resolve_menu(event)

    def ev_mousemotion(
        self, event: events.MouseMotion
    ) -> Optional[input_handlers.ActionOrHandler]:
        """Tracks mouse movement"""
        for i, text in enumerate(self.button_names):
            button_pt = Point(self.buttons[text]['x'], self.buttons[text]['y'])
            in_rect = is_mouse_in_rectangle(event, button_pt, self.menu_width, self.button_height)
            if in_rect:
                self.menu_i = i
                self.button_highlight = self.button_names[i]


class SettingsMenu(input_handlers.BaseEventHandler):
    """Audio levels and fullscreen. UP/DOWN pick a row, LEFT/RIGHT change it, ESC saves and goes back."""

    ROWS = (("Master volume", "master_volume"), ("Music volume", "music_volume"), ("Effects volume", "sfx_volume"),
            ("Fullscreen", "fullscreen"))

    def __init__(self, session=None, back=None, settings=None):
        self.settings = settings if settings is not None else settings_module.load()
        self.back = back
        self.row = 0
        super().__init__(session)

    def change(self, step: int) -> None:
        field = self.ROWS[self.row][1]
        if field == "fullscreen":
            self.settings.fullscreen = not self.settings.fullscreen
        else:
            setattr(self.settings, field, getattr(self.settings, field) + step)
        self.settings.clamp()
        settings_module.apply(self.settings, self.session)

    def ev_mousebuttondown(self, event: events.MouseButtonDown):
        """Click a row to select it; on a volume row the left half turns it down and the right half up; Fullscreen toggles."""
        if event.button != events.MouseButton.LEFT:
            return None
        x, y = int(event.position[0]), int(event.position[1])
        for rect, i in getattr(self, "row_rects", []):
            if rect.collidepoint(x, y):
                self.row = i
                if self.ROWS[i][1] == "fullscreen":
                    self.change(1)
                else:
                    self.change(1 if x >= rect.x + rect.w // 2 else -1)
        return None

    def on_render(self, canvas: Canvas) -> None:
        from ui import Theme
        canvas.blit_image(background_image())
        self.row_rects = []
        x, y, width = canvas.width // 2 - 20, canvas.height // 2 - 7, 40
        ix, iy, iw, ih = canvas.window(x, y, width, 14, title="Settings", hints=[("Up/Down", "row"), ("Left/Right", "change"), ("Esc", "back")])
        for i, (label, field) in enumerate(self.ROWS):
            value = getattr(self.settings, field)
            selected = i == self.row
            row = iy + 1 + i * 2
            self.row_rects.append((pygame.Rect(ix, row, iw, 1), i))
            if selected:
                canvas.fill(ix, row, iw, 1, Theme.HILITE)
            canvas.print(ix, row, label, fg=Theme.HILITE_TEXT if selected else Theme.TEXT)
            if field == "fullscreen":
                canvas.print(ix + iw - 1, row, "on" if value else "off", fg=Theme.HILITE_TEXT if selected else Theme.TEXT, alignment=RIGHT)
            else:
                bar_x = (ix + iw - 10) * 24
                for step in range(settings_module.MAX_VOLUME):
                    canvas.surface.fill(Theme.KEY if step < value else Theme.BORDER_DIM, (bar_x + step * 22, row * 24 + 6, 18, 12))

    def ev_keydown(self, event: events.KeyDown):
        if event.sym == Key.UP:
            self.row = (self.row - 1) % len(self.ROWS)
        elif event.sym == Key.DOWN:
            self.row = (self.row + 1) % len(self.ROWS)
        elif event.sym == Key.LEFT:
            self.change(-1)
        elif event.sym == Key.RIGHT or event.sym in input_handlers.CONFIRM_KEYS:
            self.change(1)
        elif event.sym == Key.ESCAPE:
            settings_module.save(self.settings)
            return self.back if self.back is not None else MainMenu(self.session)
        return None


class CharacterCreation(input_handlers.BaseEventHandler):
    """Name -> people -> background -> sponsor -> mode -> confirm. ENTER goes on, ESC goes back (from the name: to the menu)."""

    TITLE = "What is your name?"
    MAX_CHARS = 16
    STEPS = ("name", "race", "background", "sponsor", "mode", "confirm")
    MODES = (("roguelike", "Roguelike", "Permadeath: when you die the run and its save are gone."),
             ("casual", "Casual", "Sleep in a bed to save; after a death you return to your last bed."))

    def on_init(self):
        self.player = create_player()  # a fresh player per visit (was one Player built at import and reused)
        self.step = 0
        self.choice = {"race": 0, "background": 0, "sponsor": 0, "mode": 0}
        self.session.start_text_input()

    # the options of each step, as (key, label)
    def options(self, step: str):
        import characters
        import sponsors
        if step == "race":
            return [(k, info.species.name) for k, info in characters.RACES.items()]
        if step == "background":
            return [(k, b.name) for k, b in characters.BACKGROUNDS.items()]
        if step == "sponsor":
            return [(k, s.name) for k, s in sponsors.SPONSORS.items()]
        if step == "mode":
            return [(k, label) for k, label, _ in self.MODES]
        return []

    def selected(self, step: str) -> str:
        return self.options(step)[self.choice[step]][0]

    def details(self, step: str):
        import characters
        import sponsors
        race, background = self.selected("race"), self.selected("background")
        if step == "race":
            info = characters.RACES[race]
            return [info.lore, "", "Strengths: " + ", ".join(info.strengths), "Weaknesses: " + ", ".join(info.weaknesses),
                    "Lifespan: " + info.ages]
        if step == "background":
            bg = characters.BACKGROUNDS[background]
            return [bg.description, "", "Skills: " + ", ".join(f"{s} {l}" for s, l in bg.skills),
                    "Kit: " + (", ".join(bg.kit) or "none extra")]
        if step == "sponsor":
            spec = sponsors.SPONSORS[self.selected("sponsor")]
            return [spec.blurb, "", "Wants: " + ", ".join(spec.wants), "Perk: " + spec.perk]
        if step == "mode":
            return [self.MODES[self.choice["mode"]][2]]
        if step == "confirm":
            import sponsors as sp
            lines = characters.describe(race, background)
            lines += ["", f"Sponsor: {sp.SPONSORS[self.selected('sponsor')].name}",
                      f"Mode: {self.MODES[self.choice['mode']][1]}", ""]
            return lines
        return []

    def build(self) -> Unit:
        import characters
        return characters.create_character(self.player.name, self.selected("race"), self.selected("background"),
                                           sponsor=self.selected("sponsor"))

    def on_render(self, canvas: Canvas) -> None:
        import widgets
        from ui import Theme
        canvas.blit_image(background_image())
        step = self.STEPS[self.step]
        if step == "name":
            x, y, width = canvas.width // 2 - 20, canvas.height // 2 - 5, 40
            ix, iy, iw, ih = canvas.window(x, y, width, 9, title=self.TITLE, hints=[("Enter", "next"), ("Esc", "back")])
            shown = self.player.name + ("_" if len(self.player.name) < self.MAX_CHARS - 1 else "")
            canvas.fill(ix, iy + 1, iw, 1, Theme.PANEL)
            canvas.print(ix, iy + 1, shown, fg=Theme.HILITE_TEXT)
            return
        title = {"race": "Choose your people", "background": "Choose your background", "sponsor": "Choose your sponsor",
                 "mode": "Choose your mode", "confirm": f"{self.player.name}: ready?"}[step]
        hints = [("Enter", "begin"), ("Esc", "back")] if step == "confirm" else [("Up/Down", "choose"), ("Enter", "next"), ("Esc", "back")]
        ix, iy, iw, ih = canvas.window((canvas.width - 70) // 2, 8, 70, 26, title=title, hints=hints)
        options = self.options(step)
        left_w = 24 if options else 0
        if options:
            rows = [widgets.Row(label, data=i) for i, (_, label) in enumerate(options)]
            view = self.view = widgets.ListView(rows)
            view.selected = self.choice.get(step, 0)
            view.draw(canvas, ix, iy, left_w, ih)
        dx = ix + (left_w + 1 if options else 0)
        if options:
            import pygame
            pygame.draw.line(canvas.surface, Theme.BORDER_DIM, (dx * 24 - 12, iy * 24), (dx * 24 - 12, (iy + ih) * 24), 1)
        lines = []
        for k, paragraph in enumerate(self.details(step)):
            lines.append((paragraph, Theme.TEXT))
        widgets.text_block(canvas, dx, iy, iw - (left_w + 1 if options else 0), ih, lines)

    view = None

    def ev_mousebuttondown(self, event: events.MouseButtonDown):
        """Click an option to choose it; click the chosen one again to go on."""
        step = self.STEPS[self.step]
        if step in self.choice and self.view is not None and event.button == events.MouseButton.LEFT:
            index = self.view.row_at(int(event.position[0]) * 24 + 12, int(event.position[1]) * 24 + 12)
            if index is not None:
                if self.choice[step] == index:
                    return self.ev_keydown(events.KeyDown(Key.RETURN, 0))
                self.choice[step] = index
        return None

    def ev_textinput(self, event: events.TextInput) -> Optional[input_handlers.BaseEventHandler]:
        if self.STEPS[self.step] != "name":
            return None
        name = self.player.name
        name += event.text
        if len(name) < self.MAX_CHARS:
            self.player.set_name(name)

    def ev_keydown(self, event: events.KeyDown) -> Optional[input_handlers.BaseEventHandler]:
        step = self.STEPS[self.step]
        if event.sym in input_handlers.CONFIRM_KEYS or event.sym == Key.RETURN:
            if step == "confirm":
                self.session.stop_text_input()
                game_handler = input_handlers.MainGameEventHandler(
                    new_game(self.build(), self.session, mode=self.selected("mode")))
                self.session.reset(game_handler)
                return game_handler
            if step == "name" and not self.player.name.strip():
                return None
            self.step += 1
            if self.STEPS[self.step] != "name":
                self.session.stop_text_input()
        elif event.sym == Key.ESCAPE:  # (not Q: it is a letter in a name)
            if self.step == 0:
                self.session.stop_text_input()
                return MainMenu(self.session)
            self.step -= 1
            if self.STEPS[self.step] == "name":
                self.session.start_text_input()
        elif step == "name":
            if event.sym == Key.BACKSPACE:
                self.player.set_name(self.player.name[:-1])
        elif step in self.choice:
            count = len(self.options(step))
            if Key.A <= event.sym <= Key.Z and event.sym - Key.A < count:
                self.choice[step] = event.sym - Key.A
            elif event.sym == Key.UP:
                self.choice[step] = (self.choice[step] - 1) % count
            elif event.sym == Key.DOWN:
                self.choice[step] = (self.choice[step] + 1) % count
        return None
