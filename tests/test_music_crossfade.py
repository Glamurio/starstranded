"""Music changes cross over: the old track fades out while the new one fades in (two tracks at once), instead of silence between them."""
import os
import random
import struct
import wave

import pytest

import music
from music import Context, MusicDirector
from test_music import Clock, make


class CrossBackend(music.Backend):
    crossfades = True

    def __init__(self):
        self.plays = []           # (name, start, fade_in)
        self.busy_now = False

    def play(self, path, start=0.0, fade_in=0.0):
        self.plays.append((os.path.basename(path), start, fade_in))
        self.busy_now = True
        return True

    def busy(self):
        return self.busy_now


def _director(tmp_path):
    director, _, clock = make(tmp_path)
    cross = CrossBackend()
    director.backend = cross
    return director, cross, clock


def test_a_landmark_switch_starts_the_new_track_at_once_with_a_fade_not_after_a_fade_out(tmp_path):
    director, backend, clock = _director(tmp_path)
    director.update(Context())
    assert backend.plays and backend.plays[0][0].startswith("a")
    clock.advance(1)
    for _ in range(60):
        clock.advance(0.5)
        director.update(Context("volcanic_mountains", 1.0))
    names = [p[0] for p in backend.plays]
    assert any(n.startswith("v") for n in names)
    first_v = next(p for p in backend.plays if p[0].startswith("v"))
    assert first_v[2] == pytest.approx(director.fades["landmark"] / 1000.0)      # brought in over the landmark fade, over the old track


def test_combat_crosses_over_quickly(tmp_path):
    director, backend, clock = _director(tmp_path)
    director.update(Context())
    clock.advance(5)
    director.update(Context(threat="wildlife"))
    name, start, fade = backend.plays[-1]
    assert name.startswith("w") and fade == pytest.approx(director.fades["combat_in"] / 1000.0)


def _wave(path, seconds=1.0, rate=22050):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(struct.pack("<hh", 8000, 8000) * int(rate * seconds))


def test_the_pygame_backend_fades_one_track_out_while_the_other_comes_in(tmp_path, monkeypatch):
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.mixer.quit()
    pygame.mixer.init(22050, -16, 2, 512)
    clock = Clock()
    backend = music.CrossfadeBackend(clock)
    _wave(tmp_path / "a.wav", 5.0)
    _wave(tmp_path / "b.wav", 5.0)

    def settle():
        for _ in range(200):
            backend.update()
            if backend._loading is None:
                return
            import time
            time.sleep(0.01)
        raise AssertionError("track never loaded")

    backend.set_volume(1.0)
    backend.play(str(tmp_path / "a.wav"))
    settle()
    assert backend.busy() and backend.current["level"] == 1.0
    first = backend.current
    backend.play(str(tmp_path / "b.wav"), 0.0, 2.0)
    settle()
    assert backend.current is not first and len(backend.leaving) == 1
    clock.advance(1.0)
    backend.update()
    assert 0.4 < backend.current["level"] < 0.6 and 0.4 < backend.leaving[0]["level"] < 0.6      # half way: both audible
    assert backend.leaving[0]["channel"].get_volume() > 0 and backend.current["channel"].get_volume() > 0
    clock.advance(1.5)
    backend.update()
    assert backend.current["level"] == 1.0 and not backend.leaving                              # the old one is gone
    backend.stop()
    assert not backend.busy()
