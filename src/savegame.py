"""Saving and loading: a directory with a manifest plus one file per chunk, pickles (the manifest lzma-compressed, chunks zlib-compressed: they are
re-compressed on every unload, so speed matters more than size).

    <save dir>/manifest.lzma                          {"version": 5, "body": <pickle>}
    <save dir>/floor<N>/chunk_<cx>_<cy>.<gen>.zlib    one chunk: terrain, explored, its entities

The manifest body holds the floor (number, seed, chunk source with the floor's procedural species), the clock, the
player (with inventory and equipment), the message log, the config, the loaded chunk set, the chunk file table
(`key -> (filename, digest)`) and the next free uid. No whole-engine pickle.

Chunk pickles use *persistent ids*: the World, the Engine, the player and the floor's procedural definitions are
written as references and re-bound on load, so a chunk file never drags in the rest of the world. An entity of
another chunk (not expected; AI targets are transient) is written as its uid and resolves to None if absent.

Atomicity: chunk files are written under a new generation number (temp file + `os.replace`); the manifest is
written last the same way (that is the commit point); files the new manifest no longer references are deleted
afterwards. A crash at any point leaves a manifest that points at complete files. Unchanged chunks (same digest)
keep their old file.

The same chunk serialisation is used in memory: `World.unload_chunk` stores the bytes, `World.load_chunk` restores
them (applying catch-up for the time the chunk was away).
"""
from __future__ import annotations

import glob
import hashlib
import io
import lzma
import zlib
import os
import pickle
from typing import Dict, Optional, Tuple, TYPE_CHECKING

import exceptions
from chunks import Chunk, ChunkKey
from entity import Entity, bump_uid_counter, new_uid

if TYPE_CHECKING:
    from engine import Engine
    from world import World

SAVE_VERSION = 5
"""1 = pre-Phase-2 raw Engine pickle; 2 = species/instance split; 3 = sprite-id tiles; 4 = chunked world directory."""

MANIFEST = "manifest.lzma"
COMPRESSION_LEVEL = 3


# ── pickling with references ──────────────────────────────────────────────────────
class _Pickler(pickle.Pickler):
    def __init__(self, file, refs: Dict[int, tuple], members: Optional[set]):
        super().__init__(file, protocol=pickle.HIGHEST_PROTOCOL)
        self._refs = refs
        self._members = members

    def persistent_id(self, obj):
        tag = self._refs.get(id(obj))
        if tag is not None:
            return tag
        if self._members is not None and isinstance(obj, Entity) and id(obj) not in self._members:
            return ("uid", obj.uid)
        return None


class _Unpickler(pickle.Unpickler):
    def __init__(self, file, bindings: Dict[tuple, object], world: Optional[World]):
        super().__init__(file)
        self._bindings = bindings
        self._world = world

    def persistent_load(self, pid):
        if pid[0] == "uid":
            return self._world.find_uid(pid[1]) if self._world is not None else None
        return self._bindings[tuple(pid)]


def _references(world: World) -> Tuple[Dict[int, tuple], Dict[tuple, object]]:
    """id -> persistent tag for the shared objects of `world`, and the inverse binding for loading."""
    engine = world.engine
    objects = {("world",): world, ("engine",): engine}
    player = getattr(engine, "player", None)
    if player is not None:
        objects[("player",)] = player
    for i, definition in enumerate(_definitions(world)):
        objects[("def", i)] = definition
    return {id(obj): tag for tag, obj in objects.items()}, objects


def _definitions(world: World) -> list:
    source = world.source
    return list(source.definitions()) if hasattr(source, "definitions") else []


def _members(chunk: Chunk, player) -> set:
    """ids of the chunk's entities and everything in their inventories (pickled by value in the chunk file)."""
    found = set()
    stack = [e for e in chunk.entities if e is not player]
    while stack:
        entity = stack.pop()
        found.add(id(entity))
        inventory = getattr(entity, "inventory", None)
        if inventory is not None:
            stack.extend(inventory.items)
    return found


def _dumps(obj, refs: Dict[int, tuple], members: Optional[set]) -> bytes:
    buffer = io.BytesIO()
    _Pickler(buffer, refs, members).dump(obj)
    return zlib.compress(buffer.getvalue(), COMPRESSION_LEVEL)


def _loads(blob: bytes, bindings: Dict[tuple, object], world: Optional[World]):
    return _Unpickler(io.BytesIO(zlib.decompress(blob)), bindings, world).load()


# ── chunks ─────────────────────────────────────────────────────────────────────────
def serialize_chunk(world: World, chunk: Chunk) -> bytes:
    """One chunk as bytes: terrain, explored, its entities in insertion order (the player is never included)."""
    player = getattr(world.engine, "player", None)
    payload = {
        "key": chunk.key,
        "tiles": chunk.tiles,
        "explored": chunk.explored,
        "entities": [e for e in chunk.entities if e is not player],
    }
    refs, _ = _references(world)
    return _dumps(payload, refs, _members(chunk, player))


def restore_chunk(world: World, blob: bytes) -> Chunk:
    """Re-create a chunk from `serialize_chunk` bytes in `world`, then catch its actors up to the current time."""
    from simulation import upkeep
    _, bindings = _references(world)
    payload = _loads(blob, bindings, world)
    chunk = Chunk(payload["key"], payload["tiles"], payload["explored"])
    world.chunks[chunk.key] = chunk
    for entity in payload["entities"]:
        entity.parent = None
        world.add_entity(entity, entity._x, entity._y)
    game_world = getattr(world.engine, "game_world", None)
    if game_world is not None:
        now = game_world.current_time
        for entity in list(chunk.entities):
            if entity.ai:
                upkeep(entity, now)
    return chunk


# ── files ──────────────────────────────────────────────────────────────────────────
def _atomic_write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _read_manifest_body(directory: str) -> Optional[dict]:
    """The previous manifest's body without binding references (only for its file table), or None."""
    path = os.path.join(directory, MANIFEST)
    if not os.path.exists(path):
        return None
    try:
        outer = pickle.loads(lzma.decompress(open(path, "rb").read()))

        class _Lenient(pickle.Unpickler):
            def persistent_load(self, pid):
                return None
        return _Lenient(io.BytesIO(outer["body"])).load()
    except Exception:
        return None


def save_game(engine: Engine, directory: str) -> None:
    """Write the game to `directory` (created if needed). See the module docstring for the format."""
    if os.path.isfile(directory):
        os.remove(directory)  # an old single-file save of the same name
    world = engine.game_map
    game_world = engine.game_world
    previous = _read_manifest_body(directory) or {}
    previous_files = previous.get("chunks", {}) if previous.get("floor") == world.floor else {}
    generation = previous.get("generation", 0) + 1

    blobs = dict(world.stored)
    for key, chunk in world.chunks.items():
        blobs[key] = serialize_chunk(world, chunk)
    files: Dict[ChunkKey, Tuple[str, str]] = {}
    for key, blob in sorted(blobs.items()):
        digest = hashlib.blake2b(blob, digest_size=16).hexdigest()
        old = previous_files.get(key)
        if old and old[1] == digest and os.path.exists(os.path.join(directory, old[0])):
            files[key] = old
            continue
        name = f"floor{world.floor}/chunk_{key[0]}_{key[1]}.{generation}.zlib"
        _atomic_write(os.path.join(directory, name), blob)
        files[key] = (name, digest)

    body = {
        "generation": generation,
        "floor": world.floor,
        "floor_seed": world.seed,
        "source": world.source,
        "seed": game_world.seed,
        "time": game_world.current_time,
        "player": engine.player,
        "message_log": engine.message_log,
        "config": engine.config,
        "downstairs": world.downstairs_location,
        "loaded": sorted(world.chunks),
        "chunks": files,
        "next_uid": new_uid(),
    }
    refs = {id(world): ("world",), id(engine): ("engine",)}
    buffer = io.BytesIO()
    _Pickler(buffer, refs, None).dump(body)
    manifest = lzma.compress(pickle.dumps({"version": SAVE_VERSION, "world_class": type(world), "body": buffer.getvalue()}))
    _atomic_write(os.path.join(directory, MANIFEST), manifest)  # commit point

    referenced = {os.path.normpath(os.path.join(directory, name)) for name, _ in files.values()}
    for path in glob.glob(os.path.join(directory, "floor*", "chunk_*.zlib*")):
        if os.path.normpath(path) not in referenced:
            os.remove(path)


def load_game(directory: str, session=None) -> Engine:
    """Load a game written by `save_game`. Raises `exceptions.IncompatibleSave` for other versions / old files,
    `FileNotFoundError` if there is no save."""
    from engine import Engine
    from world import GameWorld

    if os.path.isfile(directory):  # a single-file save from before the chunked world
        _reject_single_file(directory)
    manifest_path = os.path.join(directory, MANIFEST)
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(manifest_path)
    try:
        outer = pickle.loads(lzma.decompress(open(manifest_path, "rb").read()))
    except Exception as exc:
        raise exceptions.IncompatibleSave(f"Unreadable save file ({type(exc).__name__}).") from exc
    version = outer.get("version", "unknown") if isinstance(outer, dict) else 1
    if version != SAVE_VERSION:
        raise exceptions.IncompatibleSave(
            f"Save file version {version} is not supported (this game uses version {SAVE_VERSION})."
        )

    engine = Engine(player=None, session=session)
    world_shell = object.__new__(outer["world_class"])
    try:
        body = _Unpickler(io.BytesIO(outer["body"]), {("world",): world_shell, ("engine",): engine}, None).load()
    except Exception as exc:
        raise exceptions.IncompatibleSave(f"Unreadable save file ({type(exc).__name__}).") from exc

    engine.config = body["config"]
    engine.message_log = body["message_log"]
    engine.player = body["player"]
    engine.game_world = GameWorld(engine=engine, seed=body["seed"], current_floor=body["floor"], current_time=body["time"])
    world = world_shell
    world.init_loaded(engine, body["source"], floor=body["floor"], seed=body["floor_seed"])
    world.downstairs_location = body["downstairs"]
    engine.game_map = world
    bump_uid_counter(body["next_uid"])

    for key, (name, _) in body["chunks"].items():
        with open(os.path.join(directory, name), "rb") as f:
            world.stored[key] = f.read()
    for key in body["loaded"]:
        world.load_chunk(key)
    player = engine.player
    player.parent = None
    world.add_entity(player, player._x, player._y)
    world.update_tiers()
    engine.update_fov()
    return engine


def _reject_single_file(path: str) -> None:
    try:
        payload = pickle.loads(lzma.decompress(open(path, "rb").read()))
    except Exception as exc:
        raise exceptions.IncompatibleSave(f"Unreadable save file ({type(exc).__name__}).") from exc
    found = payload.get("version", "unknown") if isinstance(payload, dict) else 1
    raise exceptions.IncompatibleSave(
        f"Save file version {found} is not supported (this game uses version {SAVE_VERSION})."
    )
