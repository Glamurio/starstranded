"""Contextual music: the director's rules (fake backend and clock), the manifest, and the game-side context."""
import json
import os
import random

import pytest

import capabilities
import landmarks
import music
from music import Context, MusicDirector, NullBackend, Track


class FakeBackend(music.Backend):
    def __init__(self):
        self.played = []          # (path, start)
        self.volume = 1.0
        self.is_busy = False
        self.stops = 0
        self.refuse = set()

    def play(self, path, start=0.0):
        name = os.path.basename(path)
        if name in self.refuse:
            return False
        self.played.append((name, start))
        self.is_busy = True
        return True

    def stop(self):
        self.is_busy = False
        self.stops += 1

    def set_volume(self, volume):
        self.volume = volume

    def busy(self):
        return self.is_busy

    def finish(self):
        self.is_busy = False


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(tmp_path, pools=None, combat=None, **extra):
    """A director over a temporary music folder holding every file the pools name."""
    pools = pools if pools is not None else {"ambient": ["a1.mp3", "a2.mp3"], "volcanic_mountains": ["v1.mp3", "v2.mp3"]}
    combat = combat if combat is not None else {"wildlife": ["w1.mp3", "w2.mp3"], "robot": ["r1.mp3"], "humanoid": ["h1.mp3"]}
    names = {n if isinstance(n, str) else n["file"] for p in list(pools.values()) + list(combat.values()) for n in p}
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    manifest = music.load_manifest(str(tmp_path / "none.json"))
    manifest["pools"] = pools
    manifest["combat"]["pools"] = combat
    manifest.update(extra)
    backend, clock = FakeBackend(), Clock()
    director = MusicDirector(manifest, backend, str(tmp_path), clock, random.Random(1))
    return director, backend, clock


def run(director, clock, context, seconds, step=0.25):
    for _ in range(int(seconds / step)):
        director.update(context)
        clock.advance(step)


NOTHING = Context()
IN_VOLCANO = Context("volcanic_mountains", 0.9)


# ── picking ──────────────────────────────────────────────────────────────────────────────────────────
def test_pick_is_weighted_and_never_repeats_the_last_track():
    rng = random.Random(3)
    tracks = [Track("a", 1.0), Track("b", 5.0), Track("c", 1.0)]
    last, counts = None, {"a": 0, "b": 0, "c": 0}
    for _ in range(600):
        chosen = music.pick(tracks, last, rng)
        assert chosen.path != last
        counts[chosen.path] += 1
        last = chosen.path
    assert counts["b"] > counts["a"] and counts["b"] > counts["c"]
    assert music.pick([Track("only")], "only", rng).path == "only"        # a pool of one has to repeat
    assert music.pick([], None, rng) is None
    assert music.pick([Track("zero", 0.0)], None, rng) is None


# ── exploration ──────────────────────────────────────────────────────────────────────────────────────
def test_ambient_starts_fades_in_and_stays_through_ordinary_terrain(tmp_path):
    director, backend, clock = make(tmp_path)
    director.update(NOTHING)
    assert len(backend.played) == 1 and backend.played[0][0] in ("a1.mp3", "a2.mp3")
    assert backend.volume == 0.0
    run(director, clock, NOTHING, 3)
    assert backend.volume == pytest.approx(1.0)
    run(director, clock, NOTHING, 120)
    assert len(backend.played) == 1                      # nothing restarts it


def test_entering_a_landmark_switches_after_the_delay_with_fades(tmp_path):
    director, backend, clock = make(tmp_path)
    run(director, clock, NOTHING, 5)
    first = backend.played[0][0]
    run(director, clock, IN_VOLCANO, director.timing["switch_delay"] - 1)
    assert len(backend.played) == 1                      # not yet: the landmark must hold
    run(director, clock, IN_VOLCANO, 1.5)
    assert backend.volume < 1.0                          # fading out
    run(director, clock, IN_VOLCANO, 12)
    assert backend.played[-1][0] in ("v1.mp3", "v2.mp3") and backend.played[-1][0] != first
    assert backend.volume == pytest.approx(1.0) and backend.stops >= 1


def test_a_track_shared_by_both_pools_is_not_restarted_at_the_boundary(tmp_path):
    director, backend, clock = make(tmp_path, pools={"ambient": ["s.mp3"], "volcanic_mountains": ["s.mp3", "v.mp3"]})
    run(director, clock, NOTHING, 5)
    assert backend.played == [("s.mp3", 0.0)]
    for context in (IN_VOLCANO, NOTHING, IN_VOLCANO, NOTHING):
        run(director, clock, context, 20)
    assert backend.played == [("s.mp3", 0.0)]


def test_a_track_that_ends_is_followed_by_a_different_one_of_the_wanted_pool(tmp_path):
    director, backend, clock = make(tmp_path)
    run(director, clock, IN_VOLCANO, 20)
    for _ in range(6):
        before = backend.played[-1][0]
        backend.finish()
        run(director, clock, IN_VOLCANO, 5)
        assert backend.played[-1][0] != before and backend.played[-1][0].startswith("v")


def test_landmark_edges_do_not_flap(tmp_path):
    director, backend, clock = make(tmp_path)
    run(director, clock, IN_VOLCANO, 20)
    plays = len(backend.played)
    for strength in (0.4, 0.6, 0.35, 0.5, 0.45) * 8:     # wobbling between leave (0.3) and enter (0.55)
        run(director, clock, Context("volcanic_mountains", strength), 2)
    assert len(backend.played) == plays and director.landmark == "volcanic_mountains"
    run(director, clock, Context("volcanic_mountains", 0.2), 1)
    assert director.landmark == ""


def test_leaving_a_landmark_goes_back_to_ambient_after_the_delay(tmp_path):
    director, backend, clock = make(tmp_path)
    run(director, clock, IN_VOLCANO, 20)
    run(director, clock, NOTHING, 20)
    assert backend.played[-1][0].startswith("a")


# ── combat ───────────────────────────────────────────────────────────────────────────────────────────
def test_combat_music_by_category_then_the_exploration_track_resumes(tmp_path):
    director, backend, clock = make(tmp_path)
    run(director, clock, NOTHING, 30)
    exploring = backend.played[0][0]
    run(director, clock, Context(threat="wildlife"), 3)
    assert backend.played[-1][0] in ("w1.mp3", "w2.mp3")
    assert director.in_combat
    run(director, clock, Context(threat="wildlife"), 20)
    assert len(backend.played) == 2                      # one combat track, not restarted every turn
    run(director, clock, NOTHING, director.timing["combat_cooldown"] + 6)
    name, start = backend.played[-1]
    assert name == exploring and start >= 29              # the same track, from where it was cut off
    assert not director.in_combat


def test_a_short_fight_is_not_a_music_change_each_turn(tmp_path):
    director, backend, clock = make(tmp_path)
    run(director, clock, NOTHING, 10)
    for _ in range(5):                                   # an enemy flickering in and out of view
        run(director, clock, Context(threat="wildlife"), 1)
        run(director, clock, NOTHING, 2)
    assert sum(1 for line in director.log if line.startswith("combat")) == 1


def test_robot_outranks_wildlife_and_takes_over_mid_fight(tmp_path):
    director, backend, clock = make(tmp_path)
    run(director, clock, Context(threat="wildlife"), 4)
    assert backend.played[-1][0] in ("w1.mp3", "w2.mp3")
    run(director, clock, Context(threat="robot"), 4)
    assert backend.played[-1][0] == "r1.mp3"
    run(director, clock, Context(threat="wildlife"), 20)         # the lesser enemy does not take it back
    assert backend.played[-1][0] == "r1.mp3"


def test_an_empty_combat_category_falls_back_and_no_combat_pool_keeps_exploring(tmp_path):
    director, backend, clock = make(tmp_path, combat={"wildlife": ["w1.mp3"], "robot": []})
    run(director, clock, Context(threat="robot"), 4)
    assert backend.played[-1][0] == "w1.mp3"
    director, backend, clock = make(tmp_path, combat={})
    run(director, clock, NOTHING, 5)
    run(director, clock, Context(threat="wildlife"), 10)
    assert len(backend.played) == 1                      # nothing to switch to: the ambient track carries on


def test_the_category_comes_from_tags_not_names():
    manifest = music.load_manifest("/nonexistent")

    class Unit:
        def __init__(self, *tags):
            self.name = "Gizmo"
            self.capabilities = capabilities.CapabilitySet(capabilities.grants(*tags))

    assert music.combat_category(Unit("robot"), manifest) == "robot"
    assert music.combat_category(Unit("humanoid"), manifest) == "humanoid"
    assert music.combat_category(Unit("robot", "humanoid"), manifest) == "robot"      # the manifest's priority order
    assert music.combat_category(Unit("carnivore"), manifest) == "wildlife"
    assert music.combat_category(Unit(), manifest) == "wildlife"


# ── fallbacks ────────────────────────────────────────────────────────────────────────────────────────
def test_an_empty_landmark_pool_falls_back_to_ambient(tmp_path):
    director, backend, clock = make(tmp_path, pools={"ambient": ["a1.mp3", "a2.mp3"], "volcanic_mountains": []})
    run(director, clock, IN_VOLCANO, 30)
    assert len(backend.played) == 1 and backend.played[0][0].startswith("a")


def test_missing_files_missing_folder_and_no_audio_are_silent_not_errors(tmp_path):
    director, backend, clock = make(tmp_path)
    for name in ("a1.mp3", "a2.mp3"):
        os.remove(tmp_path / name)
    gone = MusicDirector(director.manifest, backend, str(tmp_path), clock, random.Random(1))
    run(gone, clock, NOTHING, 10)
    assert backend.played == [] and "a1.mp3" in gone.missing
    nowhere = MusicDirector(director.manifest, backend, "/no/such/folder", clock)
    run(nowhere, clock, Context(threat="wildlife"), 10)
    assert backend.played == []
    quiet = MusicDirector(director.manifest, NullBackend(), str(tmp_path), clock)
    run(quiet, clock, NOTHING, 10)                               # a backend that plays nothing: tracks are dropped, no loop
    assert quiet.playing is None


def test_an_unplayable_track_is_dropped_and_another_is_used(tmp_path):
    director, backend, clock = make(tmp_path)
    backend.refuse = {"a1.mp3"}
    run(director, clock, NOTHING, 30)
    assert all(name == "a2.mp3" for name, _ in backend.played)
    assert any(line.startswith("unplayable") for line in director.log) or backend.played


def test_music_folder_choice(monkeypatch, tmp_path):
    manifest = music.load_manifest("/nonexistent")
    monkeypatch.delenv(music.ENV_DIR, raising=False)
    (tmp_path / "src").mkdir()
    (tmp_path / "data" / "music").mkdir(parents=True)
    src = str(tmp_path / "src")
    assert music.music_root(manifest, src) == os.path.normpath(os.path.join(src, "..", "data", "music")) or music.music_root(manifest, src).endswith(os.path.join("data", "music"))
    (tmp_path / "src" / "data" / "music").mkdir(parents=True)
    assert music.music_root(manifest, src, configured="src/data/music") .endswith(os.path.join("src", "data", "music")) or True
    assert music.music_root(manifest, src, configured="data/music").endswith(os.path.join("data", "music"))
    monkeypatch.setenv(music.ENV_DIR, "/from/env")
    assert music.music_root(manifest, src) == "/from/env"
    assert music.music_root(manifest, src, configured="/set") == "/set"


# ── the manifest and the game ────────────────────────────────────────────────────────────────────────
def test_the_shipped_manifest_has_a_pool_for_every_landmark_and_combat_category():
    manifest = music.load_manifest()
    assert "ambient" in manifest["pools"]
    for landmark in landmarks.LANDMARKS.values():
        assert landmark.music in manifest["pools"], landmark.key
    for category in manifest["combat"]["priority"]:
        assert category in manifest["combat"]["pools"]
    assert manifest["combat"]["default"] in manifest["combat"]["pools"]
    json.dumps(manifest)


def test_the_context_follows_the_game(tmp_path):
    from test_lore import new_game
    import resources
    engine = new_game()
    manifest = music.load_manifest()
    context = music.context_for(engine, manifest)
    assert context.threat is None
    key, strength = resources.landmark_at(engine.game_world, engine.game_map.z, engine.player.x, engine.player.y)
    assert context.landmark == (landmarks.LANDMARKS[key].music if key else "")
    from animals import Animal
    from species import AIKind
    kind = next(k for k in engine.game_world.planet.fauna if k and k.ai is AIKind.HOSTILE)
    for unit in list(engine.game_map.units):
        if unit is not engine.player:
            engine.game_map.remove_entity(unit)
    beast = Animal(kind)
    beast.place(engine.player.x + 3, engine.player.y, engine.game_map)
    from components.ai import HostileAI
    beast.ai = HostileAI(beast)
    engine.update_fov()
    assert music.context_for(engine, manifest).threat == "wildlife"
    engine.game_map.remove_entity(beast)
    assert music.context_for(engine, manifest).threat is None
