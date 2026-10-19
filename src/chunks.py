"""Chunks: the 70x40 pieces the world is made of.

A world tile `(x, y)` (unbounded ints) belongs to chunk `(x // CHUNK_W, y // CHUNK_H)` at local index
`(x % CHUNK_W, y % CHUNK_H)`. A `Chunk` owns the terrain of its rectangle (`tiles`, `explored`, `blocked`, all
indexed `[lx, ly]`, order F) and the per-chunk part of the entity index: the entities standing on it, by category,
those with an AI, and per render layer. The `World` routes every entity operation to the right chunk.
"""
from __future__ import annotations

from typing import Dict, Iterator, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore

from entity import EntityCategory
from render_order import LAYERS, RenderOrder

if TYPE_CHECKING:
    from entity import Entity

CHUNK_W = 70
CHUNK_H = 40

ChunkKey = Tuple[int, int]


def chunk_key(x: int, y: int) -> ChunkKey:
    """Key of the chunk containing world tile (x, y)."""
    return x // CHUNK_W, y // CHUNK_H


def chunk_origin(key: ChunkKey) -> Tuple[int, int]:
    """World coordinates of the chunk's top-left tile."""
    return key[0] * CHUNK_W, key[1] * CHUNK_H


def local(x: int, y: int) -> Tuple[int, int]:
    """Index of world tile (x, y) inside its chunk's arrays."""
    return x % CHUNK_W, y % CHUNK_H


def chebyshev(a: ChunkKey, b: ChunkKey) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def keys_around(center: ChunkKey, radius: int) -> Iterator[ChunkKey]:
    """Chunk keys within Chebyshev `radius` of `center`, row by row (deterministic order)."""
    cx, cy = center
    for ky in range(cy - radius, cy + radius + 1):
        for kx in range(cx - radius, cx + radius + 1):
            yield kx, ky


class Chunk:
    """Terrain and entity index of one chunk. Only `World` mutates it."""

    def __init__(self, key: ChunkKey, tiles: np.ndarray, explored: Optional[np.ndarray] = None):
        assert tiles.shape == (CHUNK_W, CHUNK_H), tiles.shape
        self.key = key
        self.x0, self.y0 = chunk_origin(key)
        self.tiles = tiles
        self.explored = explored if explored is not None else np.zeros((CHUNK_W, CHUNK_H), dtype=bool, order="F")
        self.blocked = np.zeros((CHUNK_W, CHUNK_H), dtype=np.int16, order="F")
        self.terrain_version = 0
        self.wild_capacity = 0                  # how many wild animals the ground carries (see wildlife.py); 0: not tracked
        self.wild_stamp = None                  # game time the wildlife was last settled
        self.entities: Dict[Entity, None] = {}
        self.by_category: Dict[EntityCategory, Dict[Entity, None]] = {c: {} for c in EntityCategory}
        self.actors: Dict[Entity, None] = {}
        self.lights: Dict[Entity, None] = {}  # entities that can emit light (see `Entity.emits_light`)
        self.buckets: Dict[RenderOrder, Dict[Entity, None]] = {r: {} for r in LAYERS}

    def __repr__(self) -> str:
        return f"Chunk{self.key}({len(self.entities)} entities)"

    def contains(self, x: int, y: int) -> bool:
        return self.x0 <= x < self.x0 + CHUNK_W and self.y0 <= y < self.y0 + CHUNK_H

    # ── index maintenance (called by World) ────────────────────────────────────────
    def index(self, entity: Entity) -> None:
        self.entities[entity] = None
        self.by_category[entity.category][entity] = None
        self.buckets[entity.render_order][entity] = None
        if entity.ai:
            self.actors[entity] = None
        if entity.light_radius > 0:
            self.lights[entity] = None
        if entity.blocks_movement:
            self.blocked[entity.x - self.x0, entity.y - self.y0] += 1

    def unindex(self, entity: Entity) -> None:
        del self.entities[entity]
        self.by_category[entity.category].pop(entity, None)
        self.buckets[entity.render_order].pop(entity, None)
        self.actors.pop(entity, None)
        self.lights.pop(entity, None)
        if entity.blocks_movement:
            self.blocked[entity.x - self.x0, entity.y - self.y0] -= 1

    def moved_within(self, entity: Entity, old: Tuple[int, int], new: Tuple[int, int]) -> None:
        if entity.blocks_movement:
            self.blocked[old[0] - self.x0, old[1] - self.y0] -= 1
            self.blocked[new[0] - self.x0, new[1] - self.y0] += 1

    def entity_changed(self, entity: Entity, attribute: str, old, new) -> None:
        if attribute == "render_order":
            self.buckets[old].pop(entity, None)
            self.buckets[new][entity] = None
        elif attribute == "blocks_movement":
            self.blocked[entity.x - self.x0, entity.y - self.y0] += 1 if new else -1
        elif attribute == "ai":
            if new:
                self.actors[entity] = None
            else:
                self.actors.pop(entity, None)

    def has_food(self) -> bool:
        """Is there something to forage here (a fruiting plant with fruit, or food on the ground)?"""
        from components.consumable import FoodConsumable
        for plant in self.by_category[EntityCategory.PLANT]:
            if plant.fruit and not plant.inventory.is_empty():
                return True
        return any(isinstance(item, FoodConsumable) for item in self.by_category[EntityCategory.ITEM])
