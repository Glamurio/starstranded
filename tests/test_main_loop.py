"""The real main loop, fed through pygame's event queue: it redraws only after input and saves on exit."""
import pygame
import pytest

from ui_helpers import SESSION
import main
import input_handlers as ih
import setup_game


class StopLoop(SystemExit):
    pass


class FakeClock:
    """Counts `tick(fps)` calls and ends the loop after `limit` of them."""

    limit = 5
    ticks = 0
    fps = []

    def tick(self, fps=0):
        type(self).ticks += 1
        type(self).fps.append(fps)
        if type(self).ticks >= type(self).limit:
            raise StopLoop()


@pytest.fixture
def loop(monkeypatch):
    saved = []
    monkeypatch.setattr(main, "save_game", lambda handler, filename: saved.append((handler, filename)))
    FakeClock.ticks = 0
    FakeClock.fps = []
    FakeClock.limit = 5
    monkeypatch.setattr(pygame.time, "Clock", FakeClock)
    pygame.event.clear()
    SESSION.display.frames_presented = 0
    return saved


def test_idle_loop_draws_once_and_is_capped_at_60_fps(loop):
    with pytest.raises(SystemExit):
        main.run(setup_game.MainMenu(SESSION), SESSION)
    assert SESSION.display.frames_presented == 1  # the initial frame only: nothing changed afterwards
    assert FakeClock.ticks == 5 and set(FakeClock.fps) == {60}


def test_input_triggers_a_redraw(loop):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, mod=0, unicode=""))
    with pytest.raises(SystemExit):
        main.run(setup_game.MainMenu(SESSION), SESSION)
    assert SESSION.display.frames_presented == 2  # initial frame + the one after the key press


def test_play_through_menu_creation_and_game_then_quit_saves(loop):
    key = lambda k: pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))  # noqa: E731
    key(pygame.K_RETURN)  # New Game
    pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text="Q"))
    for _ in range(6):
        key(pygame.K_RETURN)  # name, people, background, sponsor, mode, start
    key(pygame.K_RIGHT)
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    with pytest.raises(SystemExit):
        main.run(setup_game.MainMenu(SESSION), SESSION)
    (handler, filename), = loop
    assert isinstance(handler, ih.MainGameEventHandler) and filename == "savegame"
    assert handler.engine.player.name.endswith("Q")


def test_errors_in_a_handler_are_logged_not_fatal(loop, monkeypatch):
    menu = setup_game.MainMenu()

    class Boom(ih.MainGameEventHandler):
        def ev_keydown(self, event):
            raise RuntimeError("boom")

    engine = setup_game.new_game(setup_game.create_player())
    handler = Boom(engine)
    SESSION.handlers = [handler]
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="a"))
    with pytest.raises(SystemExit):
        main.run(handler, SESSION)
    assert any("boom" in m.plain_text for m in engine.message_log.messages)
