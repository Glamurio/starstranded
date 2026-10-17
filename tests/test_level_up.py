"""Level-up: Level.increase_* must modify the owning unit (they used to touch the Level itself and crash)."""
import tcod

import g
import input_handlers


def press(key):
    return tcod.event.KeyDown(scancode=tcod.event.Scancode.A, sym=key, mod=tcod.event.Modifier.NONE)


def test_increase_max_hp(small_world):
    p = small_world().player
    hp, mx, lvl = p.hp, p.max_hp, p.level.current_level
    p.level.current_xp = 400
    p.level.increase_max_hp()
    assert (p.max_hp, p.hp) == (mx + 20, hp + 20)
    assert p.level.current_level == lvl + 1 and p.level.current_xp == 400 - (100 + lvl * 150)


def test_increase_power_and_defense(small_world):
    p = small_world().player
    power, defense = p.power, p.defense
    p.level.increase_power()
    p.level.increase_defense()
    assert p.power == power + 1 and p.defense == defense + 1


def test_requires_level_up_threshold(small_world):
    p = small_world().player
    p.level.add_xp(250)  # needs strictly more than 100 + 1 * 150
    assert not p.level.requires_level_up
    p.level.add_xp(1)
    assert p.level.requires_level_up


def test_level_up_screen_applies_choice_and_closes(small_world):
    e = small_world()
    p = e.player
    p.level.current_xp = 400
    main = input_handlers.MainGameEventHandler(e)
    handler = input_handlers.LevelUpEventHandler(e)
    g.handlers = [main, handler]
    mx = p.max_hp
    handler.ev_keydown(press(tcod.event.KeySym.A))
    assert p.max_hp == mx + 20
    assert g.handlers == [main]


def test_level_up_screen_rejects_invalid_key(small_world):
    e = small_world()
    handler = input_handlers.LevelUpEventHandler(e)
    g.handlers = [input_handlers.MainGameEventHandler(e), handler]
    handler.ev_keydown(press(tcod.event.KeySym.Z))
    assert any("Invalid entry" in m.plain_text for m in e.message_log.messages)
    assert len(g.handlers) == 2
