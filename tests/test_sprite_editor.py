"""The sprite config (data/sprites.json overrides) and the debug sprite editor."""
import json

import pytest

import atlas
import events
import setup_game
import species
import spriteconfig
import sprite_editor
import tile_types
from events import Key, Point
from ui_helpers import SESSION


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Point the config at a temp file and put every sprite back afterwards."""
    monkeypatch.setattr(spriteconfig, "PATH", str(tmp_path / "sprites.json"))
    spriteconfig.reload()
    spriteconfig.catalog()
    yield tmp_path / "sprites.json"
    for key in list(spriteconfig._load()):
        spriteconfig.reset(key, save_now=False)
    spriteconfig.reload()


def draw(editor):
    SESSION.canvas.clear()
    editor.on_render(SESSION.canvas)


def test_catalog_lists_items_units_tiles_flora_and_fauna(config):
    keys = spriteconfig.catalog()
    for expected in ("item.meat", "unit.selenite", "unit.selenite.corpse", "tile.floor", "tile.water.west", "flora.broadleaf.1",
                     "fauna.hopper", "fauna.hopper.corpse"):
        assert expected in keys


def test_set_applies_live_and_save_writes_only_the_changes(config):
    spriteconfig.set("unit.selenite", (9, 9))
    assert species.UNIT_SPECIES["selenite"].sprite == (9, 9)
    assert json.loads(config.read_text()) == {"unit.selenite": [9, 9]}
    spriteconfig.set("tile.floor", (7, 7))
    assert tile_types.floor.sprite == atlas.sprite_id(7, 7)
    assert tile_types.floor.get_array()["light"]["sprite"] == atlas.sprite_id(7, 7)
    assert species.UNIT_SPECIES["selenite_people"].sprite == (9, 9)   # the playable Selenites share the entry
    spriteconfig.reset("unit.selenite")
    assert species.UNIT_SPECIES["selenite"].sprite == (115, 1)
    assert json.loads(config.read_text()) == {"tile.floor": [7, 7]}


def test_setting_the_default_removes_the_override(config):
    spriteconfig.set("item.meat", (5, 5))
    spriteconfig.set("item.meat", (1, 21))
    assert not spriteconfig.is_changed("item.meat")


def test_overrides_are_read_back_from_the_file(config):
    config.write_text(json.dumps({"fauna.hopper": [11, 11]}))
    spriteconfig.reload()
    assert spriteconfig.get("fauna.hopper", (3, 20)) == (11, 11)
    config.write_text("not json")
    spriteconfig.reload()
    assert spriteconfig.get("fauna.hopper", (3, 20)) == (3, 20)   # a broken file means defaults, not a crash


def test_main_menu_opens_the_editor_and_escape_returns(config):
    menu = setup_game.MainMenu(SESSION)
    menu.button_highlight = "Sprite editor"
    editor = menu.resolve_menu(None)
    assert isinstance(editor, sprite_editor.SpriteEditor)
    assert isinstance(editor.ev_keydown(events.KeyDown(Key.ESCAPE)), setup_game.MainMenu)


def test_search_click_assign_and_reset(config):
    editor = sprite_editor.SpriteEditor(SESSION)
    draw(editor)
    for ch in "selenite":
        editor.ev_textinput(events.TextInput(ch))
    assert editor.key == "unit.selenite"
    draw(editor)
    rect = editor.sheet_rect
    editor.ev_mousemotion(events.MouseMotion(Point(rect.x + 2, rect.y + 3)))
    assert editor.hover == (2, 3)
    editor.ev_mousebuttondown(events.MouseButtonDown(Point(rect.x + 2, rect.y + 3)))
    assert species.UNIT_SPECIES["selenite"].sprite == (2, 3)
    assert json.loads(config.read_text()) == {"unit.selenite": [2, 3]}
    draw(editor)
    editor.ev_keydown(events.KeyDown(Key.R, events.Mod.CTRL))
    assert species.UNIT_SPECIES["selenite"].sprite == (115, 1)


def test_sheet_scrolls_and_clicks_follow_the_scroll(config):
    editor = sprite_editor.SpriteEditor(SESSION)
    draw(editor)
    editor.ev_keydown(events.KeyDown(Key.PAGEDOWN))
    editor.ev_keydown(events.KeyDown(Key.RIGHT))
    draw(editor)
    assert (editor.col0, editor.row0) == (sprite_editor.SHEET_STEP, sprite_editor.SHEET_STEP)
    rect = editor.sheet_rect
    assert editor.cell_at(rect.x, rect.y) == (editor.col0, editor.row0)
    assert editor.cell_at(0, 0) is None   # outside the sheet viewport
    for _ in range(40):
        editor.ev_keydown(events.KeyDown(Key.PAGEDOWN))
        editor.ev_keydown(events.KeyDown(Key.RIGHT))
    draw(editor)
    assert editor.col0 + rect.w <= atlas.COLUMNS and editor.row0 + rect.h <= atlas.ROWS


def test_no_match_draws_without_error(config):
    editor = sprite_editor.SpriteEditor(SESSION)
    for ch in "zzzzqq":
        editor.ev_textinput(events.TextInput(ch))
    assert editor.key is None
    draw(editor)
    editor.ev_mousebuttondown(events.MouseButtonDown(Point(60, 20)))   # nothing to assign: no crash


def test_saving_keeps_the_previous_file_as_a_backup(config):
    config.write_text('{"item.beacon": [1, 2], "unit.selenite": [3, 4]}\n')
    spriteconfig.reload()
    spriteconfig.set("item.beacon", (5, 6))
    backup = config.with_name(config.name + ".bak")
    assert backup.read_text() == '{"item.beacon": [1, 2], "unit.selenite": [3, 4]}\n'
    spriteconfig.set("item.beacon", (7, 8))          # later saves in the same run keep the first backup
    assert "unit.selenite" in backup.read_text()


def test_an_unreadable_file_is_never_overwritten(config):
    config.write_text('{"item.beacon": [1, 2],')     # broken by hand or half written
    spriteconfig.reload()
    with pytest.raises(OSError):
        spriteconfig.set("item.beacon", (5, 6))
    assert config.read_text() == '{"item.beacon": [1, 2],'
