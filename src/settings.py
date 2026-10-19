"""Player settings (audio levels, fullscreen), saved as JSON beside the game and applied at start-up.

Volumes are 0-10. The game ships no sound effects yet, so the levels are stored (and applied to pygame's mixer when one
is running) for when it does.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

PATH = "settings.json"
CURRENT = None
"""The settings last applied (what the music reads its volume and folder from)."""
MAX_VOLUME = 10
MUSIC_GAIN = 0.5
"""The music is mixed this much quieter in the game than the slider says (the tracks are mastered loud)."""


@dataclass
class Settings:
    master_volume: int = 7
    music_volume: int = 7
    sfx_volume: int = 7
    fullscreen: bool = False
    theme: str = "ion"
    music_dir: str = ""       # folder of the music files; empty: STARSTRANDED_MUSIC, else the manifest root (src/data/music)

    def clamp(self) -> "Settings":
        for name in ("master_volume", "music_volume", "sfx_volume"):
            setattr(self, name, max(0, min(MAX_VOLUME, int(getattr(self, name)))))
        self.fullscreen = bool(self.fullscreen)
        self.theme = str(self.theme)
        self.music_dir = str(self.music_dir or "")
        return self

    def effective(self, channel: str) -> float:
        """Loudness 0..1 of `channel` ('music' or 'sfx') after the master level."""
        return self.master_volume / MAX_VOLUME * getattr(self, channel + "_volume") / MAX_VOLUME

    def music_level(self) -> float:
        """What the music backend is given: the music loudness at the in-game gain."""
        return self.effective("music") * MUSIC_GAIN


def load(path: str = None) -> Settings:
    """Saved settings; defaults when the file is missing or unreadable (a broken file never blocks the game)."""
    path = path or PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        known = {k: v for k, v in data.items() if k in Settings.__dataclass_fields__}
        return Settings(**known).clamp()
    except (OSError, ValueError, TypeError, AttributeError):
        return Settings()


def save(settings: Settings, path: str = None) -> None:
    path = path or PATH
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(asdict(settings.clamp()), f, indent=2)
    os.replace(tmp, path)


def apply(settings: Settings, session=None) -> None:
    """Put the settings into effect: fullscreen on the window, volume on the mixer if it is running."""
    import pygame
    import ui
    global CURRENT
    CURRENT = settings
    ui.Theme.apply(settings.theme)
    if session is not None and session.display is not None and pygame.display.get_surface() is not None:
        if bool(pygame.display.is_fullscreen()) != settings.fullscreen:
            try:
                pygame.display.toggle_fullscreen()
            except pygame.error:   # e.g. the headless driver: the setting is kept, the window stays as it is
                pass
    if pygame.mixer.get_init():
        pygame.mixer.music.set_volume(settings.music_level())
