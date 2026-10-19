"""Hydrology: rivers that rise at a spring (or from thawing ice), flow downhill, join each other and end in the sea or a lake.

Water needs a view of the whole land, but chunks are generated one at a time. So rivers are *traced*, not painted:

- the world is cut into lattice cells of `CELL` tiles; each cell may hold one river source (a hash of the seed and the cell),
  placed on high enough ground that is not desert-dry;
- from the source the river steps from node to node (nodes lie on a `NODE`-tile lattice) always to the lowest neighbouring node
  of `relief.drainage`, with a small bias to keep its heading, until it reaches the sea (it then runs on a little into it and
  opens into an estuary) or a pit (a real basin: it ends in a lake). A river that is still going after `MAX_NODES` nodes ends
  in a lake too, so no river ever just stops;
- because nodes sit on a shared lattice and descent is deterministic, rivers that meet *merge* and share every node downstream;
  the number of sources whose path passes a node is its flow, and flow sets the width: a trickle you can wade, a big river you
  cannot, with a ford now and then;
- a river passing near the landing site is dropped whole (the first chunk stays dry).

A chunk asks for the rivers that can touch it (`water_mask`); each traced river is cached per planet. Nothing is saved: it is
all a pure function of the seed, so chunks agree about where the water is.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np  # type: ignore

import relief
from seeds import mix_seed

Node = Tuple[int, int]
NODE = 6
"""Lattice spacing of river nodes, in tiles."""
CELL = 120
"""One candidate river source per CELL x CELL tiles."""
MAX_NODES = 80
BLOCK = 32
SOURCE_CHANCE = 0.65
SOURCE_MIN_HEIGHT = 0.28
SOURCE_MIN_MOISTURE = -0.40
MIN_NODES = 5
SPAWN_KEEP_OUT = 70
SEA_MARGIN = 0.10
RUN_ON = 3
"""Nodes a river runs on into the sea after crossing the shore line, so it really reaches the water."""
TURN_COST = 0.012
FORD_EVERY = 6
CATCHMENT_NODES = 12
"""Every this many nodes of course count as one more tributary for the width (a river gathers water along its way)."""
BASE_WIDTH, WIDTH_PER_ROOT, MAX_WIDTH, FORD_WIDTH = 1.7, 0.95, 5.6, 2.0
REACH = MAX_NODES * NODE

DIRECTIONS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))


@dataclass
class River:
    cell: Tuple[int, int]
    nodes: List[Node]
    end: str                     # "sea": reaches the sea | "lake": ends in a lake
    source: str                  # "spring" | "thaw"
    box: Tuple[int, int, int, int]   # tile bounding box x0, y0, x1, y1 (with a margin)

    @property
    def start_tile(self) -> Tuple[int, int]:
        return self.nodes[0][0] * NODE, self.nodes[0][1] * NODE


class RiverSystem:
    """The rivers of one planet, traced on demand and cached."""

    def __init__(self, noise):
        self.noise = noise
        self.seed = noise.floor_seed
        self._blocks: Dict[Tuple[int, int], np.ndarray] = {}
        self._cells: Dict[Tuple[int, int], Optional[River]] = {}
        self._jitter: Dict[Node, Tuple[float, float]] = {}

    # ── the field rivers flow over ──────────────────────────────────────────────────────────────────────
    def height(self, ix: int, iy: int) -> float:
        key = (ix // BLOCK, iy // BLOCK)
        block = self._blocks.get(key)
        if block is None:
            block = self._blocks[key] = relief.drainage(self.noise, key[0] * BLOCK * NODE, key[1] * BLOCK * NODE, BLOCK, BLOCK, NODE)
        return float(block[ix - key[0] * BLOCK, iy - key[1] * BLOCK])

    def jitter(self, node: Node) -> Tuple[float, float]:
        """A fixed small sideways offset per node, so rivers meander and merged rivers still share their nodes."""
        found = self._jitter.get(node)
        if found is None:
            h = mix_seed(self.seed, node[0], node[1], 5252)
            found = self._jitter[node] = (((h >> 3) % 1000) / 1000 * 7.0 - 3.5, ((h >> 13) % 1000) / 1000 * 7.0 - 3.5)
        return found

    # ── tracing ─────────────────────────────────────────────────────────────────────────────────────────
    def trace(self, start: Node) -> Tuple[List[Node], str]:
        nodes = [start]
        seen = {start}
        heading = None
        sea = relief.SEA_LEVEL + SEA_MARGIN
        for _ in range(MAX_NODES):
            ix, iy = nodes[-1]
            here = self.height(ix, iy)
            if here < sea:
                for _ in range(RUN_ON):                 # carry on into the water, in the same direction
                    d = DIRECTIONS[heading] if heading is not None else (1, 0)
                    nodes.append((nodes[-1][0] + d[0], nodes[-1][1] + d[1]))
                return nodes, "sea"
            best = None
            for d, (dx, dy) in enumerate(DIRECTIONS):
                nxt = (ix + dx, iy + dy)
                if nxt in seen:
                    continue
                h = self.height(*nxt)
                if h >= here:
                    continue
                turn = 0 if heading is None else min((d - heading) % 8, (heading - d) % 8)
                score = h + TURN_COST * turn
                if best is None or score < best[0]:
                    best = (score, nxt, d)
            if best is None:
                return nodes, "lake"                   # a real basin
            nodes.append(best[1])
            seen.add(best[1])
            heading = best[2]
        return nodes, "lake"

    def river_of_cell(self, i: int, j: int) -> Optional[River]:
        if (i, j) in self._cells:
            return self._cells[(i, j)]
        river = self._cells[(i, j)] = self._make(i, j)
        return river

    def _make(self, i: int, j: int) -> Optional[River]:
        rng = random.Random(mix_seed(self.seed, i, j, 5151))
        if rng.random() > SOURCE_CHANCE:
            return None
        sx, sy = (i + rng.random()) * CELL, (j + rng.random()) * CELL
        start = (round(sx / NODE), round(sy / NODE))
        high = self.height(*start)
        if high < SOURCE_MIN_HEIGHT or high < relief.SEA_LEVEL + 0.3:
            return None
        if self.noise.moisture(int(sx), int(sy), 1, 1)[0, 0] < SOURCE_MIN_MOISTURE:
            return None
        nodes, end = self.trace(start)
        if len(nodes) < MIN_NODES:
            return None
        for ix, iy in nodes:                              # the landing site stays dry
            if math.hypot(ix * NODE - relief.SPAWN[0], iy * NODE - relief.SPAWN[1]) < SPAWN_KEEP_OUT:
                return None
        cold = self.noise.temperature(int(sx), int(sy), 1, 1)[0, 0] - relief.LAPSE * max(high - relief.SNOWLINE, 0.0)
        xs, ys = [n[0] * NODE for n in nodes], [n[1] * NODE for n in nodes]
        box = (min(xs) - 16, min(ys) - 16, max(xs) + 16, max(ys) + 16)
        return River((i, j), nodes, end, "thaw" if cold < -0.30 else "spring", box)

    def rivers_near(self, x0: int, y0: int, width: int, height: int) -> List[River]:
        """Every river whose course may touch the tile rectangle."""
        found = []
        for i in range((x0 - REACH) // CELL, (x0 + width + REACH) // CELL + 1):
            for j in range((y0 - REACH) // CELL, (y0 + height + REACH) // CELL + 1):
                river = self.river_of_cell(i, j)
                if river and river.box[0] < x0 + width and river.box[2] >= x0 and river.box[1] < y0 + height and river.box[3] >= y0:
                    found.append(river)
        return found


_SYSTEMS: Dict[int, RiverSystem] = {}
"""One `RiverSystem` per planet seed (tracing is the expensive part; chunks share it)."""


def system_for(noise) -> RiverSystem:
    system = _SYSTEMS.get(noise.floor_seed)
    if system is None:
        if len(_SYSTEMS) > 8:
            _SYSTEMS.pop(next(iter(_SYSTEMS)))
        system = _SYSTEMS[noise.floor_seed] = RiverSystem(noise)
    return system


# ── drawing ─────────────────────────────────────────────────────────────────────────────────────────────
def _chaikin(points: np.ndarray, rounds: int = 2) -> np.ndarray:
    """Corner-cutting smoothing of a polyline (columns: x, y, width), keeping its two ends."""
    for _ in range(rounds):
        if len(points) < 3:
            break
        q = 0.75 * points[:-1] + 0.25 * points[1:]
        r = 0.25 * points[:-1] + 0.75 * points[1:]
        middle = np.stack([q, r], axis=1).reshape(-1, points.shape[1])
        points = np.vstack([points[:1], middle, points[-1:]])
    return points


def _dense(points: np.ndarray, spacing: float = 1.0) -> np.ndarray:
    steps = np.hypot(*np.diff(points[:, :2], axis=0).T)
    counts = np.maximum(1, np.ceil(steps / spacing).astype(int))
    index = np.repeat(np.arange(len(counts)), counts)
    local = np.concatenate([np.arange(c) / c for c in counts])
    return points[index] * (1 - local)[:, None] + points[index + 1] * local[:, None]


def _stamp(mask: np.ndarray, x0: int, y0: int, centres: np.ndarray, radii: np.ndarray) -> None:
    """Fill discs (centres in tile coordinates, radii in tiles) into the mask of the rectangle starting at (x0, y0)."""
    if not len(centres):
        return
    reach = int(math.ceil(float(radii.max())))
    span = np.arange(-reach, reach + 1)
    ox, oy = np.meshgrid(span, span, indexing="ij")
    ox, oy = ox.ravel(), oy.ravel()
    cx, cy = centres[:, 0] - x0, centres[:, 1] - y0
    px = np.rint(cx)[:, None] + ox[None, :]
    py = np.rint(cy)[:, None] + oy[None, :]
    inside = (px - cx[:, None]) ** 2 + (py - cy[:, None]) ** 2 <= (radii[:, None] ** 2)
    inside &= (px >= 0) & (px < mask.shape[0]) & (py >= 0) & (py < mask.shape[1])
    mask[px[inside].astype(int), py[inside].astype(int)] = True


def river_width(flow: float) -> float:
    return min(MAX_WIDTH, BASE_WIDTH + WIDTH_PER_ROOT * math.sqrt(max(flow - 1, 0)))


def water_mask(noise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    """Tiles of the rectangle covered by a river, its spring pool, its estuary or the lake it ends in."""
    system = system_for(noise)
    mask = np.zeros((width, height), dtype=bool)
    rivers = system.rivers_near(x0, y0, width, height)
    if not rivers:
        return mask
    flow = Counter()
    run = {}
    for river in rivers:
        flow.update(river.nodes)
        for k, node in enumerate(river.nodes):
            run[node] = max(run.get(node, 0), k)       # how far the longest river reaching this node has come
    for river in rivers:
        nodes = river.nodes
        widths = []
        for k, node in enumerate(nodes):
            w = river_width(flow[node] + run[node] / CATCHMENT_NODES)
            if mix_seed(system.seed, node[0], node[1], 5353) % FORD_EVERY == 0:
                w = min(w, FORD_WIDTH)                  # a place to wade across
            if river.end == "sea" and k >= len(nodes) - RUN_ON - 2:
                w = max(w, 3.2) * 1.3                    # the mouth opens out
            widths.append(w)
        widths[0] = 1.4
        pts = np.array([[n[0] * NODE + system.jitter(n)[0], n[1] * NODE + system.jitter(n)[1], w] for n, w in zip(nodes, widths)])
        dense = _dense(_chaikin(pts))
        near = (dense[:, 0] > x0 - 8) & (dense[:, 0] < x0 + width + 8) & (dense[:, 1] > y0 - 8) & (dense[:, 1] < y0 + height + 8)
        if near.any():
            _stamp(mask, x0, y0, dense[near][:, :2], dense[near][:, 2] / 2 + 0.3)
        # the ends: a pool at the spring, a lake or an estuary at the mouth
        h = mix_seed(system.seed, nodes[-1][0], nodes[-1][1], 5454)
        end_radius = 6 + (h % 4) if river.end == "lake" else 4
        for centre, radius in (((pts[0, 0], pts[0, 1]), 2.6), ((pts[-1, 0], pts[-1, 1]), end_radius)):
            if x0 - 12 < centre[0] < x0 + width + 12 and y0 - 12 < centre[1] < y0 + height + 12:
                _stamp(mask, x0, y0, np.array([centre]), np.array([radius]))
    return mask
