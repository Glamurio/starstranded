import pygame
import pytest

import display
import events


@pytest.fixture
def disp():
    d = display.Display(headless=True, window_size=(1920, 1080))
    yield d
    import g
    g.init(headless=True)  # the shared window the other tests draw on was replaced by this test


def test_fit_integer_scale_and_letterbox():
    assert display.fit((1920, 1080)) == ((1920, 1080), (0, 0), 1.0)
    size, offset, scale = display.fit((3840, 2200))
    assert scale == 2.0 and size == (3840, 2160) and offset == (0, 20)
    size, offset, scale = display.fit((2500, 1080))
    assert scale == 1.0 and size == (1920, 1080) and offset == (290, 0)


def test_fit_fractional_below_logical_size():
    size, offset, scale = display.fit((960, 600))
    assert scale == 0.5 and size == (960, 540) and offset == (0, 30)
    size, offset, scale = display.fit((1000, 400))
    assert size[1] == 400 and abs(size[0] / size[1] - 16 / 9) < 0.01


def test_to_cell_identity_and_letterbox(disp):
    assert disp.to_cell((0, 0)) == (0, 0)
    assert disp.to_cell((1919, 1079)) == (79, 44)
    assert disp.to_cell((24, 48)) == (1, 2)
    pygame.display.set_mode((2500, 1080), pygame.RESIZABLE)
    assert disp.to_cell((100, 100)) is None  # left bar
    assert disp.to_cell((290, 0)) == (0, 0)
    assert disp.to_cell((290 + 48, 24 * 3)) == (2, 3)


def test_to_cell_when_scaled_up_and_down(disp):
    pygame.display.set_mode((3840, 2160), pygame.RESIZABLE)
    assert disp.to_cell((47, 47)) == (0, 0)
    assert disp.to_cell((48, 48)) == (1, 1)
    assert disp.to_cell((3839, 2159)) == (79, 44)
    pygame.display.set_mode((960, 540), pygame.RESIZABLE)
    assert disp.to_cell((12, 12)) == (1, 1)
    assert disp.to_cell((959, 539)) == (79, 44)


def test_present_scales_and_letterboxes(disp):
    pygame.display.set_mode((3840, 2200), pygame.RESIZABLE)
    disp.surface.fill((200, 10, 10))
    disp.present()
    window = pygame.display.get_surface()
    assert window.get_at((10, 5))[:3] == (0, 0, 0)  # top bar
    assert window.get_at((10, 30))[:3] == (200, 10, 10)
    assert window.get_at((3839, 2179))[:3] == (200, 10, 10)
    assert window.get_at((3839, 2190))[:3] == (0, 0, 0)  # bottom bar
    assert disp.frames_presented == 1


def test_translate_converts_mouse_to_cells(disp):
    raw = pygame.event.Event(pygame.MOUSEMOTION, pos=(100, 50), rel=(1, 1), buttons=(0, 0, 0))
    ev = events.translate(raw, disp.to_cell, events.Point(2, 1))
    assert isinstance(ev, events.MouseMotion)
    assert ev.position == (4, 2) and ev.motion == (2, 1)
    click = events.translate(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(25, 0), button=1), disp.to_cell)
    assert isinstance(click, events.MouseButtonDown) and click.position == (1, 0) and click.button == events.MouseButton.LEFT
    assert events.translate(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(25, 0), button=4), disp.to_cell) is None


def test_translate_keys_text_quit():
    key = events.translate(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP, mod=pygame.KMOD_LSHIFT, unicode=""), None)
    assert isinstance(key, events.KeyDown) and key.sym == events.Key.UP and key.mod & events.Mod.LSHIFT
    text = events.translate(pygame.event.Event(pygame.TEXTINPUT, text="x"), None)
    assert isinstance(text, events.TextInput) and text.text == "x"
    assert isinstance(events.translate(pygame.event.Event(pygame.QUIT), None), events.Quit)
    assert events.translate(pygame.event.Event(pygame.KEYUP, key=pygame.K_UP, mod=0), None) is None
    assert isinstance(events.translate(pygame.event.Event(pygame.VIDEORESIZE, size=(1, 1), w=1, h=1), None), events.WindowChanged)


def test_letters_are_consecutive_and_dispatch_routes():
    assert events.Key.C - events.Key.A == 2
    assert events.Key.Z - events.Key.A == 25

    class Handler(events.EventDispatch):
        def ev_keydown(self, event):
            return ("key", event.sym)

    handler = Handler()
    assert handler.dispatch(events.KeyDown(events.Key.G)) == ("key", events.Key.G)
    assert handler.dispatch(events.Quit()) is None
    assert handler.dispatch(events.MouseMotion(events.Point(1, 1))) is None


def test_poll_drops_letterbox_mouse_events(disp):
    pygame.display.set_mode((2500, 1080), pygame.RESIZABLE)
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5), rel=(0, 0), buttons=(0, 0, 0)))
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(290 + 24, 24), rel=(0, 0), buttons=(0, 0, 0)))
    got = list(disp.poll())
    assert len(got) == 1 and got[0].position == (1, 1)
