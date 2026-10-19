"""Contextual music: a small state machine that decides what plays, and a backend that plays it.

What plays is decided by three things, in this order of priority (the *priority rule*):

1. **Combat** - a hostile creature in view. The track comes from the combat pool of the creature's *category* (wildlife,
   humanoid, robot ...), which is read from the tags the creature's species grants (`humanoid`, `robot`; anything else is
   wildlife), never from its name. With several categories in view the one that comes first in the manifest's `priority` list wins,
   and a higher-priority category may take over from a lower one mid-fight. Combat starts at once (short fade) and ends
   `combat_cooldown` seconds after the last hostile left view; then the exploration track that was playing is resumed from where it was
   cut off (or a new one starts if little of it was left).
2. **Landmark** - inside a landmark (a landmark names its pool with its `music` key), with hysteresis: the pool is entered at
   strength `landmark_enter` and left below `landmark_leave`, so walking along an edge does not flap. A track that belongs to the
   wanted pool is never interrupted or restarted; a track from another pool is replaced (fade out, fade in) only once the wanted
   pool has been steady for `switch_delay` seconds, and a track that ends is followed by one of the wanted pool.
3. **Biome** - the pool the manifest's `biomes` table gives the biome the player stands in (forest, plains, cold, wet, dry), if it has tracks.
4. **Ambient** - everywhere else: the `ambient` pool, which is the fallback of everything above it.

Tracks are picked by weight and never repeat the one just played (when the pool has another). Everything is data: `data/music.json`
names the pools, tracks (paths below the music folder; the folder is not part of the repository), weights, fades and timings.
Missing files, an empty pool, a missing music folder or no audio device are never errors: an empty pool falls back (landmark ->
ambient, a combat category -> the default category -> keep what plays) and with nothing to play there is silence.

`MusicDirector` knows nothing about pygame or the game: it is told the `Context` (landmark, strength, threat category) and a clock, and it
drives a `Backend`. `PygameBackend` plays through `pygame.mixer.music`; `NullBackend` plays nothing. The sound-effect system that is
to come can share the same manifest style and the volume settings (`settings.effective("music")`)."""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "music.json")
ENV_DIR = "STARSTRANDED_MUSIC"

DEFAULTS = {
    "root": "data/music",
    "fade_ms": {"landmark": 3000, "combat_in": 700, "combat_out": 1200, "resume_in": 1500, "start": 2000},
    "timing": {"switch_delay": 6.0, "combat_cooldown": 1.0, "landmark_enter": 0.55, "landmark_leave": 0.3, "resume_min_left": 10.0},
    "pools": {},
    "combat": {"priority": ["robot", "humanoid", "wildlife"], "default": "wildlife", "tags": {"robot": ["robot"], "humanoid": ["humanoid"]},
               "pools": {}},
}


@dataclass(frozen=True)
class Track:
    path: str            # as written in the manifest (below the music folder)
    weight: float = 1.0
    length: float = 0.0  # seconds, if the manifest says (lets a track cut off by combat be resumed only if enough is left)


@dataclass(frozen=True)
class Context:
    """What the director is told about the game: the landmark the player is in (key, strength 0..1; "" for none) and the
    category of the hostile creature in view, if any."""
    landmark: str = ""
    strength: float = 0.0
    threat: Optional[str] = None
    biome: str = ""


# ── manifest ─────────────────────────────────────────────────────────────────────────────────────────
def load_manifest(path: str = MANIFEST) -> dict:
    """The manifest merged over the defaults; a missing or broken file is the defaults (silence)."""
    data: dict = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        pass
    merged = json.loads(json.dumps(DEFAULTS))
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def _tracks(entries) -> List[Track]:
    out = []
    for entry in entries or []:
        if isinstance(entry, str):
            out.append(Track(entry))
        elif isinstance(entry, dict) and entry.get("file"):
            out.append(Track(str(entry["file"]), max(float(entry.get("weight", 1.0)), 0.0), float(entry.get("length", 0.0))))
    return out


def music_root(manifest: dict, game_dir: Optional[str] = None, configured: str = "") -> str:
    """The music folder: the setting, else the environment variable, else the manifest's `root`. A relative folder is looked for
    beside `src/` (the game folder), in `src/` itself, then in the working directory; the first that exists wins, so the
    usual spellings ("music", "data/music", "src/data/music") all work whichever folder the game was started from."""
    src = game_dir or os.path.dirname(os.path.abspath(__file__))
    choice = configured or os.environ.get(ENV_DIR, "") or manifest.get("root", "data/music")
    if os.path.isabs(choice):
        return choice
    candidates = [os.path.join(src, "..", choice), os.path.join(src, choice), os.path.abspath(choice)]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return os.path.normpath(candidate)
    return os.path.normpath(candidates[0])


def pick(tracks: List[Track], last: Optional[str], rng: random.Random) -> Optional[Track]:
    """A weighted random track that is not `last` (unless it is the only one); None for an empty pool."""
    pool = [t for t in tracks if t.weight > 0]
    if not pool:
        return None
    others = [t for t in pool if t.path != last]
    pool = others or pool
    return rng.choices(pool, weights=[t.weight for t in pool])[0]


# ── backends ─────────────────────────────────────────────────────────────────────────────────────────
class Backend:
    """What the director plays through."""

    crossfades = False
    """True when `play(..., fade_in)` lets what plays now fade out while the new track fades in (two tracks at once)."""

    def play(self, path: str, start: float = 0.0, fade_in: float = 0.0) -> bool:
        """Start `path` (a full path) `start` seconds in; False when it cannot be played. A crossfading backend takes
        `fade_in` seconds to bring it in while the track before it fades out; the others ignore it."""
        return False

    def update(self) -> None:
        """Called by the director every update (a crossfading backend moves its fades along here)."""

    def stop(self) -> None:
        pass

    def set_volume(self, volume: float) -> None:
        pass

    def busy(self) -> bool:
        return False


class NullBackend(Backend):
    """Plays nothing (no audio device, or tests)."""


class PygameBackend(Backend):
    def __init__(self):
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self.mixer = pygame.mixer

    def play(self, path: str, start: float = 0.0, fade_in: float = 0.0) -> bool:
        try:
            self.mixer.music.load(path)
            self.mixer.music.play(start=start)
            return True
        except Exception:
            return False

    def stop(self) -> None:
        self.mixer.music.stop()

    def set_volume(self, volume: float) -> None:
        self.mixer.music.set_volume(max(0.0, min(1.0, volume)))

    def busy(self) -> bool:
        return bool(self.mixer.music.get_busy())


class CrossfadeBackend(Backend):
    """Plays whole tracks as mixer Sounds on their own channels, so one can fade out while the next fades in (the streaming
    `mixer.music` can only hold one). A track is decoded on a worker thread (a few tenths of a second, about 45 MB) and starts when
    ready; until then what plays carries on. Only the track playing and those still fading out are kept in memory."""

    crossfades = True

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self.pygame = pygame
        self.clock = clock
        self.volume = 1.0
        self.current: Optional[dict] = None          # {"channel", "sound", "level"}
        self.leaving: List[dict] = []                # tracks fading out: {"channel", "sound", "level", "from", "since", "seconds"}
        self._loading: Optional[dict] = None         # {"thread", "result", "fade", "start"}
        self._fade_in: Optional[Tuple[float, float]] = None      # (since, seconds) of the current track

    def play(self, path: str, start: float = 0.0, fade_in: float = 0.0) -> bool:
        import threading
        job = {"result": None, "fade": fade_in, "start": start}

        def load() -> None:
            try:
                sound = self.pygame.mixer.Sound(path)
                if start > 0.5:                                  # (a Sound cannot seek: cut the start off)
                    import numpy as np
                    samples = self.pygame.sndarray.array(sound)
                    sound = self.pygame.sndarray.make_sound(np.ascontiguousarray(samples[int(start * self.pygame.mixer.get_init()[0]):]))
                job["result"] = sound
            except Exception:
                job["result"] = False
        job["thread"] = threading.Thread(target=load, daemon=True)
        self._loading = job
        job["thread"].start()
        return True

    def update(self) -> None:
        now = self.clock()
        job = self._loading
        if job is not None and job["result"] is not None:
            self._loading = None
            if job["result"] is not False and len(job["result"].get_raw()) > 0:
                self._begin(job["result"], job["fade"], now)
        if self.current is not None and self._fade_in is not None:
            since, seconds = self._fade_in
            self.current["level"] = min((now - since) / seconds, 1.0) if seconds > 0 else 1.0
            if self.current["level"] >= 1.0:
                self._fade_in = None
        for old in list(self.leaving):
            old["level"] = max(0.0, old["from"] * (1.0 - (now - old["since"]) / old["seconds"])) if old["seconds"] > 0 else 0.0
            if old["level"] <= 0.0 or not old["channel"].get_busy():
                old["channel"].stop()
                self.leaving.remove(old)
        for entry in ([self.current] if self.current else []) + self.leaving:
            entry["channel"].set_volume(max(0.0, min(1.0, self.volume * entry["level"])))

    def _begin(self, sound, fade: float, now: float) -> None:
        mixer = self.pygame.mixer
        used = {e["index"] for e in self.leaving} | ({self.current["index"]} if self.current else set())
        # (channels are picked by number: `Channel` objects are new every time, so comparing them cannot tell that a channel is
        # the one that a fading track still holds; a stop of that old track would then cut the new one off, over and over)
        free = [i for i in range(mixer.get_num_channels()) if i not in used]
        index = next((i for i in free if not mixer.Channel(i).get_busy()), free[0] if free else 0)
        channel = mixer.Channel(index)
        if self.current is not None:
            self.leaving.append({**self.current, "from": self.current["level"], "since": now, "seconds": max(fade, 0.05)})
        self.current = {"channel": channel, "index": index, "sound": sound, "level": 0.0 if fade > 0 else 1.0}
        self._fade_in = (now, fade) if fade > 0 else None
        channel.set_volume(0.0 if fade > 0 else self.volume)
        channel.play(sound)

    def stop(self) -> None:
        self._loading = None
        for entry in ([self.current] if self.current else []) + self.leaving:
            entry["channel"].stop()
        self.current, self.leaving, self._fade_in = None, [], None

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))

    def busy(self) -> bool:
        """Something is playing, or is about to (still being decoded) - the same as `mixer.music.get_busy` for the director."""
        return self._loading is not None or (self.current is not None and bool(self.current["channel"].get_busy()))


def make_backend() -> Backend:
    """The crossfading mixer backend if the pygame mixer can be started, else a backend that plays nothing."""
    try:
        return CrossfadeBackend()
    except Exception:
        return NullBackend()


# ── the director ─────────────────────────────────────────────────────────────────────────────────────
@dataclass
class _Playing:
    track: Track
    pool: str
    started: float          # clock time the track began, minus its start offset: `now - started` is the position
    combat: bool = False


@dataclass
class _Pending:
    track: Track
    pool: str
    start: float            # seconds into the track
    fade_in: float          # seconds
    combat: bool


class MusicDirector:
    def __init__(self, manifest: Optional[dict] = None, backend: Optional[Backend] = None, root: str = "",
                 clock: Callable[[], float] = time.monotonic, rng: Optional[random.Random] = None, volume: float = 1.0):
        self.manifest = manifest if manifest is not None else load_manifest()
        self.backend = backend or NullBackend()
        self.root = root
        self.clock = clock
        self.rng = rng or random.Random()
        self.volume = volume
        self.fades = self.manifest["fade_ms"]
        self.timing = self.manifest["timing"]
        self.priority: List[str] = list(self.manifest["combat"]["priority"])
        self.pools: Dict[str, List[Track]] = {}
        self.missing: List[str] = []
        for key, entries in self.manifest["pools"].items():
            self.pools[key] = self._existing(_tracks(entries))
        for key, entries in self.manifest["combat"]["pools"].items():
            self.pools["combat:" + key] = self._existing(_tracks(entries))
        self.playing: Optional[_Playing] = None
        self.last: Optional[str] = None                  # the track played last (never picked again straight away)
        self.landmark = ""                               # the landmark pool wanted (with hysteresis)
        self._wanted = "ambient"                          # the exploration pool wanted at the last update
        self.biome = ""                                  # the biome pool wanted (the track only changes once it has been steady, see switch_delay)
        self.mismatch_since: Optional[float] = None      # since when the wanted pool is not the one playing
        self.threat_until = -1.0
        self.in_combat = False
        self.combat_category: Optional[str] = None
        self.resume: Optional[Tuple[Track, str, float]] = None      # the exploration track cut off by combat, and where
        self.log: List[str] = []                         # what happened (for tests and the debug overlay)
        self._factor = 1.0                               # fade level 0..1
        self._ramp: Optional[Tuple[float, float, float, float]] = None      # (start time, seconds, from, to)
        self._pending: Optional[_Pending] = None

    def reset(self) -> None:
        """Back to the start: stop at once and forget the fight, the landmark and what was cut off (leaving a game for the menu)."""
        self.backend.stop()
        self.playing = None
        self.landmark = ""
        self.biome = ""
        self.mismatch_since = None
        self.threat_until = -1.0
        self.in_combat = False
        self.combat_category = None
        self.resume = None
        self._factor = 1.0
        self._ramp = None
        self._pending = None

    def now_playing(self) -> str:
        """The name of the track that is playing (its file name without folder and extension); "" when nothing is."""
        if self.playing is None or not self.backend.busy():
            return ""
        return os.path.splitext(os.path.basename(self.playing.track.path))[0]

    # ── pools ────────────────────────────────────────────────────────────────────────────────────
    def _existing(self, tracks: List[Track]) -> List[Track]:
        kept = []
        for track in tracks:
            if self.root and os.path.isfile(os.path.join(self.root, track.path)):
                kept.append(track)
            else:
                self.missing.append(track.path)
        return kept

    def pool(self, key: str) -> List[Track]:
        return self.pools.get(key, [])

    def exploration_pool(self) -> str:
        """The wanted exploration pool: the landmark's if it has tracks, else the biome's, else ambient (an empty pool falls back)."""
        for key in (self.landmark, self.biome):
            if key and self.pool(key):
                return key
        return "ambient"

    def combat_pool(self, category: Optional[str]) -> Optional[str]:
        for key in (category, self.manifest["combat"]["default"]):
            if key and self.pool("combat:" + key):
                return "combat:" + key
        return None

    def _rank(self, category: Optional[str]) -> int:
        return self.priority.index(category) if category in self.priority else len(self.priority)

    # ── deciding ─────────────────────────────────────────────────────────────────────────────────
    def update(self, context: Context) -> None:
        """Look at the game and decide; call a few times a second."""
        now = self.clock()
        self._hysteresis(context)
        self.biome = self.manifest.get("biomes", {}).get(context.biome, "")
        if context.threat:
            self.threat_until = now + self.timing["combat_cooldown"]
        fighting = now < self.threat_until
        if fighting and not self.in_combat:
            self._begin_combat(context.threat, now)
        elif self.in_combat and not fighting:
            self._end_combat(now)
        elif self.in_combat:
            self._keep_combat(context.threat, now)
        else:
            self._keep_exploring(now)
        self._advance(now)

    def _hysteresis(self, context: Context) -> None:
        if context.landmark and context.strength >= self.timing["landmark_enter"]:
            self.landmark = context.landmark
        elif self.landmark and not (context.landmark == self.landmark and context.strength >= self.timing["landmark_leave"]):
            self.landmark = ""

    def _idle(self) -> bool:
        return self._pending is None and self._ramp is None

    def _keep_exploring(self, now: float) -> None:
        wanted = self.exploration_pool()
        if wanted != self._wanted:                       # a different pool is wanted: the steady-for-`switch_delay` clock starts again
            self._wanted, self.mismatch_since = wanted, None
        playing = self.playing
        if not self._idle():
            return
        if playing is None or not self.backend.busy():                       # nothing playing, or the track ended
            track = pick(self.pool(wanted), self.last, self.rng)
            if track is not None:
                self._switch(track, wanted, 0.0, self.fades["start" if playing is None else "landmark"], now)
            self.mismatch_since = None
            return
        if any(t.path == playing.track.path for t in self.pool(wanted)) or playing.combat:
            self.mismatch_since = None                                       # right music: never interrupt or restart it
            return
        if self.mismatch_since is None:
            self.mismatch_since = now
        if now - self.mismatch_since >= self.timing["switch_delay"]:
            track = pick(self.pool(wanted), self.last, self.rng)
            if track is not None:
                self._switch(track, wanted, 0.0, self.fades["landmark"], now)
            self.mismatch_since = None

    def _begin_combat(self, category: Optional[str], now: float) -> None:
        self.in_combat, self.combat_category = True, category
        pool = self.combat_pool(category)
        if pool is None:                                                     # nothing to fight to: the exploration music carries on
            return
        playing = self.playing
        if playing is not None and not playing.combat:
            self.resume = (playing.track, playing.pool, now - playing.started)
        self._combat_track(pool, now)
        self.log.append(f"combat:{category}")

    def _combat_track(self, pool: str, now: float, quick: bool = True) -> None:
        track = pick(self.pool(pool), self.last, self.rng)
        if track is not None:
            self._switch(track, pool, 0.0, self.fades["combat_in"], now, combat=True, out=self.fades["combat_in"] if quick else None)

    def _keep_combat(self, category: Optional[str], now: float) -> None:
        if category is not None and self._rank(category) < self._rank(self.combat_category):     # a more important kind of enemy
            pool = self.combat_pool(category)
            self.combat_category = category
            if pool is not None and (self.playing is None or self.playing.pool != pool):
                self._combat_track(pool, now)
                self.log.append(f"combat:{category}")
            return
        playing = self.playing
        if playing is not None and playing.combat and self._idle() and not self.backend.busy():     # the fight outlasted the track
            pool = self.combat_pool(self.combat_category)
            if pool is not None:
                self._combat_track(pool, now)

    def _end_combat(self, now: float) -> None:
        self.in_combat, self.combat_category = False, None
        resume, self.resume = self.resume, None
        if self.playing is None or not self.playing.combat:
            return
        if resume is not None:
            track, pool, position = resume
            left = track.length - position if track.length else float("inf")
            if left > self.timing["resume_min_left"] and any(t.path == track.path for t in self.pool(pool)):
                self._switch(track, pool, position, self.fades["resume_in"], now, out=self.fades["combat_out"])
                self.log.append("resume")
                return
        wanted = self.exploration_pool()
        track = pick(self.pool(wanted), resume[0].path if resume else None, self.rng)
        if track is not None:
            self._switch(track, wanted, 0.0, self.fades["resume_in"], now, out=self.fades["combat_out"])

    # ── playing and fading ───────────────────────────────────────────────────────────────────────
    def _switch(self, track: Track, pool: str, start: float, fade_in_ms: float, now: float, combat: bool = False,
                out: Optional[float] = None) -> None:
        """Fade what plays out (over `out` ms, default the landmark fade), then start `track` and fade it in."""
        self._pending = _Pending(track, pool, start, fade_in_ms / 1000.0, combat)
        if self.backend.crossfades:                      # the old track fades out under the new one: nothing to wait for
            self._ramp = None
            self._start(now)
            return
        if self.playing is not None and self.backend.busy():
            seconds = max(self.fades["landmark"] if out is None else out, 1) / 1000.0
            self._ramp = (now, seconds, self._factor, 0.0)
        else:
            self.playing = None
            self._ramp = None

    def _advance(self, now: float) -> None:
        if self._ramp is not None:
            started, seconds, a, b = self._ramp
            progress = min((now - started) / seconds, 1.0)
            self._factor = a + (b - a) * progress
            if progress >= 1.0:
                self._ramp = None
                if b <= 0.0:
                    self.backend.stop()
                    self.playing = None
        if self._ramp is None and self._pending is not None and self.playing is None:
            self._start(now)
        self.backend.set_volume(self.volume * self._factor)
        self.backend.update()

    def _start(self, now: float) -> None:
        pending, self._pending = self._pending, None
        path = os.path.join(self.root, pending.track.path)
        if not (self.backend.play(path, pending.start, pending.fade_in) if self.backend.crossfades else self.backend.play(path, pending.start)):
            self.log.append(f"unplayable:{pending.track.path}")
            for key in list(self.pools):
                self.pools[key] = [t for t in self.pools[key] if t.path != pending.track.path]     # never tried again
            self._factor = 1.0
            return
        self.playing = _Playing(pending.track, pending.pool, now - pending.start, pending.combat)
        self.last = pending.track.path
        self.log.append(f"play:{pending.track.path}")
        if self.backend.crossfades:
            self._factor = 1.0                           # (the backend fades the tracks itself)
        elif pending.fade_in > 0:
            self._factor, self._ramp = 0.0, (now, pending.fade_in, 0.0, 1.0)
        else:
            self._factor = 1.0


# ── the game side ────────────────────────────────────────────────────────────────────────────────────
def combat_category(unit, manifest: dict) -> str:
    """The category of a creature, from the tags its species grants (see the manifest's `combat.tags`); anything untagged is the
    default category (wildlife)."""
    tags = set(unit.capabilities.tags) if hasattr(unit, "capabilities") else set()
    rules = manifest["combat"].get("tags", {})
    for category in manifest["combat"]["priority"]:
        if tags & set(rules.get(category, [])):
            return category
    return manifest["combat"]["default"]


THREAT_RADIUS = 8


def context_for(engine, manifest: dict) -> Context:
    """The director's context from the game: the landmark under the player (surface only) and the best hostile creature in view."""
    import resources
    from entity import EntityCategory
    player = engine.player
    world = engine.game_map
    landmark, strength, biome = "", 0.0, ""
    game_world = getattr(engine, "game_world", None)
    if game_world is not None:
        try:
            landmark, strength = resources.landmark_at(game_world, world.z, player.x, player.y)
            biome = resources.biome_key_at(game_world, world.z, player.x, player.y) if world.z == 0 else ""
        except Exception:
            landmark, strength, biome = "", 0.0, ""
        import landmarks
        if landmark in landmarks.LANDMARKS:
            landmark = landmarks.LANDMARKS[landmark].music or ""
    rank = {c: i for i, c in enumerate(manifest["combat"]["priority"])}
    best: Optional[str] = None
    import debug
    for unit in ([] if debug.is_god(engine) else world.actors):      # (God Mode: nobody is a threat)
        import allegiance
        if unit is player or unit.category is not EntityCategory.UNIT or not allegiance.threatens(unit, player):
            continue
        if max(abs(unit.x - player.x), abs(unit.y - player.y)) > THREAT_RADIUS or not engine.can_see(player.x, player.y, unit.x, unit.y, THREAT_RADIUS):
            continue
        category = combat_category(unit, manifest)
        if best is None or rank.get(category, 99) < rank.get(best, 99):
            best = category
    return Context(landmark, strength, best, biome)


_DIRECTOR: Optional[MusicDirector] = None
_NEXT = 0.0
TICK = 0.25


def director() -> MusicDirector:
    """The one director of the game, made on first use (with the pygame mixer if there is one)."""
    global _DIRECTOR
    if _DIRECTOR is None:
        import settings
        manifest = load_manifest()
        current = settings.CURRENT
        _DIRECTOR = MusicDirector(manifest, make_backend(), music_root(manifest, configured=getattr(current, "music_dir", "")),
                                  volume=current.music_level() if current else 0.35)
    return _DIRECTOR


def engine_of(handler):
    """The game a screen belongs to (a popup or a menu opened from the game points back at it), or None for the main menu and the like."""
    seen = 0
    while handler is not None and seen < 8:
        engine = getattr(handler, "engine", None)
        if engine is not None:
            return engine
        handler = getattr(handler, "parent", None) or getattr(handler, "back", None)
        seen += 1
    return None


def now_playing() -> str:
    """The track playing now, for the HUD ("" when there is none)."""
    return _DIRECTOR.now_playing() if _DIRECTOR is not None else ""


def tick(handler) -> None:
    """Called by the main loop each frame: a few times a second, show the director what the game is like. Never raises."""
    global _NEXT, _DIRECTOR
    engine = engine_of(handler)
    now = time.monotonic()
    if engine is None:
        if _DIRECTOR is not None and (_DIRECTOR.playing is not None or _DIRECTOR._pending is not None or _DIRECTOR.in_combat):
            _DIRECTOR.reset()          # a menu outside any game: the music stops and the next game starts from scratch
        return
    if now < _NEXT or getattr(engine, "player", None) is None:
        return
    _NEXT = now + TICK
    try:
        import settings
        music = director()
        if settings.CURRENT is not None:
            music.volume = settings.CURRENT.music_level()
        music.update(context_for(engine, music.manifest))
    except Exception:
        import traceback
        traceback.print_exc()
        _DIRECTOR = MusicDirector(backend=NullBackend())     # whatever went wrong, the game goes on in silence
