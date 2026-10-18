"""Wild input must never raise: random keys, clicks, text and mouse moves on every screen, from the menu into the game."""
import random
import traceback

import pytest

import main
import setup_game
from events import Key, KeyDown, MouseButton, MouseButtonDown, MouseMotion, Point, TextInput
from ui_helpers import SESSION

KEYS = [v for k, v in vars(Key).items() if k.isupper() and isinstance(v, int)]


def random_event(rng):
    kind = rng.random()
    if kind < 0.55:
        return KeyDown(rng.choice(KEYS), rng.choice([0, 0, 0, 1, 64]))
    if kind < 0.65:
        return TextInput(rng.choice("abcxyz 0123"))
    cell = Point(rng.randrange(-2, 82), rng.randrange(-2, 47))
    if kind < 0.85:
        return MouseMotion(cell)
    return MouseButtonDown(cell, rng.choice([MouseButton.LEFT, MouseButton.LEFT, MouseButton.RIGHT, MouseButton.MIDDLE]))


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_random_input_never_raises(seed, monkeypatch, tmp_path):
    import actions
    import settings
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "settings.json"))   # keep the real files untouched
    monkeypatch.setattr(actions, "BED_SAVE", str(tmp_path / "bed"))
    errors = []
    monkeypatch.setattr(main.traceback, "print_exc", lambda *a, **k: errors.append(traceback.format_exc()))
    rng = random.Random(seed)
    random.seed(seed)
    handler = setup_game.MainMenu(SESSION)
    SESSION.handlers = [handler]
    for step in range(600):
        if step % 150 == 0 and not hasattr(handler, "engine"):
            # help the fuzzer into a game now and then: New Game, confirm every step
            for key in [Key.RETURN] * 7:
                handler = main.process(handler, KeyDown(key, 0), SESSION)
        event = random_event(rng)
        if isinstance(event, KeyDown) and event.sym in (Key.ESCAPE,) and isinstance(handler, setup_game.MainMenu):
            continue                      # Escape on the main menu quits the program
        try:
            handler = main.process(handler, event, SESSION)
        except SystemExit:
            handler = setup_game.MainMenu(SESSION)
            SESSION.handlers = [handler]
        except Exception as exc:          # QuitWithoutSaving etc. end the run, which is fine
            if type(exc).__name__ != "QuitWithoutSaving":
                raise
            handler = setup_game.MainMenu(SESSION)
            SESSION.handlers = [handler]
        handler = main.render(handler, SESSION)
    assert not errors, errors[0]
