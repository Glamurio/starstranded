"""HUD bars, the right-hand panel and the colour themes."""
import pytest

import hud
import ui
import settings as settings_module
from ui_helpers import SESSION


@pytest.mark.parametrize("cur,mx,lit", [(0, 100, 0), (1, 100, 1), (50, 100, 5), (51, 100, 6), (100, 100, 10), (30, 30, 10), (5, 0, 0)])
def test_segments_lit(cur, mx, lit):
    assert hud.segments_lit(cur, mx) == lit


def test_every_palette_defines_every_colour_and_apply_swaps_them():
    keys = set(ui.PALETTES["ion"].colors)
    try:
        for name, palette in ui.PALETTES.items():
            assert set(palette.colors) == keys, name
            assert ui.Theme.apply(name) == name
            assert ui.Theme.BG == palette.colors["BG"]
        assert ui.Theme.apply("nonsense") == ui.DEFAULT_THEME
    finally:
        ui.Theme.apply(ui.DEFAULT_THEME)


def test_default_theme_is_not_the_old_teal_and_gold():
    assert ui.DEFAULT_THEME == "ion" and ui.PALETTES["ion"].colors["BG"] != ui.PALETTES["classic"].colors["BG"]


def test_theme_row_cycles_and_persists(tmp_path, monkeypatch):
    import setup_game
    monkeypatch.setattr(settings_module, "PATH", str(tmp_path / "s.json"))
    menu = setup_game.SettingsMenu(SESSION, settings=settings_module.Settings())
    menu.row = [f for _, f in menu.ROWS].index("theme")
    try:
        menu.change(1)
        assert menu.settings.theme == ui.THEME_ORDER[1] and ui.Theme.NAME == ui.THEME_ORDER[1]
        menu.change(-1)
        assert menu.settings.theme == ui.THEME_ORDER[0]
        settings_module.save(menu.settings)
        assert settings_module.load(str(tmp_path / "s.json")).theme == ui.THEME_ORDER[0]
    finally:
        ui.Theme.apply(ui.DEFAULT_THEME)


def test_log_lives_in_the_right_panel(new_engine):
    from view import VIEW_W
    e = new_engine
    e.message_log.add_message("Hello from the log", (255, 255, 255))
    SESSION.canvas.surface.fill((0, 0, 0))
    e.render(SESSION.canvas)
    # nothing is drawn in the old bottom strip's log area of the map; the panel's last log rows are lit
    panel = SESSION.canvas.surface.subsurface((VIEW_W * 24, 25 * 24, (80 - VIEW_W) * 24, 18 * 24))
    import pygame
    assert pygame.surfarray.array3d(panel).max() > 150
