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
FJORD_MAX_NODES, FJORD_MIN_NODES, FJORD_MIN_RANGE, FJORD_MAX_RISE, FJORD_WIDTH = 14, 3, 0.10, 1.3, 8.5
"""A river that meets the sea through a range has its last stretch (at most 14 nodes, at least 3, where the height is still
within 1.3 of the sea) drowned into a fjord 8.5 tiles wide."""
BRIDGE_EVERY, BRIDGE_SPAN, APPROACH = 20, (2, 6), 2
"""One river node in `BRIDGE_EVERY` is a candidate; a bridge spans 2-6 tiles of water and has 2 path tiles on each bank."""
HOT_CELL, HOT_CHANCE = 36, 0.6
LAVA_HOT, LAVA_SHARE = 2.0, 0.5
HOT_SAFE = 150.0
"""No hot spring within this many tiles of the landing site."""
"""Landmark strength from which a hot site may be a lava lake, and the share of those that are."""
"""Hot springs: one candidate per 36x36 tiles, kept where the biome's `hot_springs` allows (volcanic and thermal ground)."""
DIRECTIONS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))


@dataclass
class River:
    cell: Tuple[int, int]
    nodes: List[Node]
    end: str                     # "sea": reaches the sea | "lake": ends in a lake
    source: str                  # "spring" | "thaw"
    box: Tuple[int, int, int, int]   # tile bounding box x0, y0, x1, y1 (with a margin)
    fjord_from: int = -1         # index of the first node of the drowned valley (a fjord) at the mouth, or -1

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
        self._hot: Dict[Tuple[int, int], Optional[Tuple[float, float, float]]] = {}
        self._bridges: Dict[Node, Optional[List[Tuple[int, int, bool]]]] = {}

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
        river = River((i, j), nodes, end, "thaw" if cold < -0.30 else "spring", box)
        if end == "sea":
            river.fjord_from = self._fjord_start(nodes)
        return river

    def _fjord_start(self, nodes: List[Node]) -> int:
        """Where a river valley that reaches the sea through mountains starts to be drowned (a fjord), or -1."""
        shore = len(nodes) - RUN_ON - 1
        first = shore
        while first > 0 and shore - first < FJORD_MAX_NODES:
            ix, iy = nodes[first - 1]
            potential = float(relief.range_potential(self.noise, ix * NODE, iy * NODE, 1, 1)[0, 0])
            if potential < FJORD_MIN_RANGE or self.height(ix, iy) > relief.SEA_LEVEL + FJORD_MAX_RISE:
                break
            first -= 1
        return first if shore - first + 1 >= FJORD_MIN_NODES else -1

    def hot_site(self, i: int, j: int) -> Optional[Tuple[float, float, float, bool]]:
        """`(x, y, radius, lava)` of the hot spring of lattice cell (i, j), if it has one: only deep inside volcanic
        country. Near the core of it the pool may be a lava lake instead (bigger, and it kills)."""
        key = (i, j)
        if key not in self._hot:
            self._hot[key] = self._make_hot(i, j)
        return self._hot[key]

    def _make_hot(self, i: int, j: int) -> Optional[Tuple[float, float, float, bool]]:
        rng = random.Random(mix_seed(self.seed, i, j, 6161))
        if rng.random() > HOT_CHANCE:
            return None
        x, y = (i + rng.random()) * HOT_CELL, (j + rng.random()) * HOT_CELL
        radius = 2.4 + 1.4 * rng.random()
        if math.hypot(x - relief.SPAWN[0], y - relief.SPAWN[1]) < HOT_SAFE:       # (the landing site is dry)
            return None
        import biomes
        import worldgen
        env = worldgen.environment_for(self.noise, int(x), int(y), 1, 1, np.ones((1, 1), dtype=np.int8))
        biome = biomes.BIOMES[biomes.BIOME_IDS[int(env["biome"][0, 0])]]
        if biome.hot_springs <= 0 or float(env["edge"][0, 0]) > 0.25 or rng.random() > min(1.0, biome.hot_springs):
            return None
        lava = biome.family == "volcanic" and biome.hot_springs >= LAVA_HOT and rng.random() < LAVA_SHARE
        return x, y, radius * (1.8 if lava else 1.0), lava

    def bridge_at(self, river: "River", k: int) -> Optional[List[Tuple[int, int, bool]]]:
        """The bridge over `river` at its node `k`, if it has one: `[(x, y, deck)]`, the planks over the water (`deck`) and the
        path tiles on the banks either side. Only a narrow, plain reach with dry banks on both sides and no fall, fjord,
        lake or mouth near it qualifies, and then only one node in `BRIDGE_EVERY`. Judged on the terrain itself, so the
        answer is the same whichever chunk asks."""
        node = river.nodes[k]
        if node not in self._bridges:
            self._bridges[node] = self._make_bridge(river, k)
        return self._bridges[node]

    def _make_bridge(self, river: "River", k: int) -> Optional[List[Tuple[int, int, bool]]]:
        nodes = river.nodes
        if k < 2 or k > len(nodes) - RUN_ON - 3 or (river.fjord_from >= 0 and k >= river.fjord_from - 1):
            return None
        node = nodes[k]
        if mix_seed(self.seed, node[0], node[1], 7171) % BRIDGE_EVERY or mix_seed(self.seed, node[0], node[1], 5353) % FORD_EVERY == 0:
            return None
        import worldgen
        a, b = nodes[k - 1], nodes[k + 1]
        dx, dy = b[0] - a[0] + 0.0, b[1] - a[1] + 0.0
        norm = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / norm, dx / norm
        cx, cy = node[0] * NODE + self.jitter(node)[0], node[1] * NODE + self.jitter(node)[1]
        half = 16
        x0, y0 = int(cx) - half, int(cy) - half
        size = 2 * half + 1
        kinds = worldgen.base_terrain(self.noise, x0, y0, size, size)
        bad = waterfall_mask(self.noise, x0, y0, size, size) | lava_mask(self.noise, x0, y0, size, size) | hot_spring_mask(self.noise, x0, y0, size, size)
        line = []
        for step in range(-2 * half + 2, 2 * half - 1):
            t = step / 2.0
            tile = (int(round(cx + nx * t)), int(round(cy + ny * t)))
            if not line or line[-1] != tile:
                line.append(tile)
        local = [(x - x0, y - y0) for x, y in line]
        inside = [(i, p) for i, p in enumerate(local) if 1 <= p[0] < size - 1 and 1 <= p[1] < size - 1]
        if not inside:
            return None
        water = [i for i, p in inside if kinds[p] == 0]
        if not water or bad[tuple(zip(*[p for _, p in inside]))].any():
            return None
        # the water crossing the centre of the line: the run of water tiles around the water nearest the river node
        centre = min(water, key=lambda i: (line[i][0] - cx) ** 2 + (line[i][1] - cy) ** 2)
        lo = hi = centre
        while lo - 1 >= 0 and 1 <= local[lo - 1][0] < size - 1 and 1 <= local[lo - 1][1] < size - 1 and kinds[local[lo - 1]] == 0:
            lo -= 1
        while hi + 1 < len(local) and 1 <= local[hi + 1][0] < size - 1 and 1 <= local[hi + 1][1] < size - 1 and kinds[local[hi + 1]] == 0:
            hi += 1
        span = hi - lo + 1
        if not BRIDGE_SPAN[0] <= span <= BRIDGE_SPAN[1] or lo - APPROACH < 0 or hi + APPROACH >= len(local):
            return None
        for i in list(range(lo - APPROACH, lo)) + list(range(hi + 1, hi + 1 + APPROACH)):
            px, py = local[i]
            if not (0 <= px < size and 0 <= py < size) or kinds[px, py] != 1:       # dry, open ground on both banks
                return None
        found = [(line[i][0], line[i][1], lo <= i <= hi) for i in range(lo - APPROACH, hi + 1 + APPROACH)]
        return found

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


NO_SOURCE = -(10 ** 9)


def water_mask(noise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    """Tiles of the rectangle covered by a river, its spring pool, its estuary or the lake it ends in."""
    return _paint_rivers(noise, x0, y0, width, height)[0]


def water_sources(noise, x0: int, y0: int, width: int, height: int) -> Tuple[np.ndarray, np.ndarray]:
    """For every tile of river water (see `water_mask`) the coordinates of the spring its river rises from; `NO_SOURCE` elsewhere.
    The longest river wins where two meet, so a stream joining a river takes the river's colour downstream."""
    _, ax, ay = _paint_rivers(noise, x0, y0, width, height)
    return ax, ay


def _paint_rivers(noise, x0: int, y0: int, width: int, height: int):
    system = system_for(noise)
    mask = np.zeros((width, height), dtype=bool)
    ax = np.full((width, height), NO_SOURCE, dtype=np.int32)
    ay = np.full((width, height), NO_SOURCE, dtype=np.int32)
    rivers = sorted(system.rivers_near(x0, y0, width, height), key=lambda r: len(r.nodes))
    if not rivers:
        return mask, ax, ay
    flow = Counter()
    run = {}
    for river in rivers:
        flow.update(river.nodes)
        for k, node in enumerate(river.nodes):
            run[node] = max(run.get(node, 0), k)       # how far the longest river reaching this node has come
    for river in rivers:
        nodes = river.nodes
        part = np.zeros_like(mask)
        widths = []
        for k, node in enumerate(nodes):
            w = river_width(flow[node] + run[node] / CATCHMENT_NODES)
            if mix_seed(system.seed, node[0], node[1], 5353) % FORD_EVERY == 0:
                w = min(w, FORD_WIDTH)                  # a place to wade across
            if river.fjord_from >= 0 and k >= river.fjord_from:
                w = FJORD_WIDTH * min(1.0, (k - river.fjord_from + 1) / 3)      # a drowned valley, easing in
            elif river.end == "sea" and k >= len(nodes) - RUN_ON - 2:
                w = max(w, 3.2) * 1.3                    # the mouth opens out
            widths.append(w)
        widths[0] = 1.4
        pts = np.array([[n[0] * NODE + system.jitter(n)[0], n[1] * NODE + system.jitter(n)[1], w] for n, w in zip(nodes, widths)])
        dense = _dense(_chaikin(pts))
        near = (dense[:, 0] > x0 - 8) & (dense[:, 0] < x0 + width + 8) & (dense[:, 1] > y0 - 8) & (dense[:, 1] < y0 + height + 8)
        if near.any():
            _stamp(part, x0, y0, dense[near][:, :2], dense[near][:, 2] / 2 + 0.3)
        # the ends: a pool at the spring, a lake or an estuary at the mouth
        h = mix_seed(system.seed, nodes[-1][0], nodes[-1][1], 5454)
        end_radius = 6 + (h % 4) if river.end == "lake" else 4
        for centre, radius in (((pts[0, 0], pts[0, 1]), 2.6), ((pts[-1, 0], pts[-1, 1]), end_radius)):
            if x0 - 12 < centre[0] < x0 + width + 12 and y0 - 12 < centre[1] < y0 + height + 12:
                _stamp(part, x0, y0, np.array([centre]), np.array([radius]))
        mask |= part
        ax[part], ay[part] = int(round(pts[0, 0])), int(round(pts[0, 1]))
    return mask, ax, ay


FALL_DROP = 0.2
"""Fall of the drainage height between two river nodes (6 tiles apart) from which the river drops as a waterfall."""


def waterfall_mask(noise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    """Tiles of the rectangle where a river plunges down a mountain step: a short, deep, unwadable stretch."""
    system = system_for(noise)
    mask = np.zeros((width, height), dtype=bool)
    for river in system.rivers_near(x0, y0, width, height):
        for a, b in zip(river.nodes, river.nodes[1:]):
            if system.height(*a) - system.height(*b) < FALL_DROP:
                continue
            ax, ay = a[0] * NODE + system.jitter(a)[0], a[1] * NODE + system.jitter(a)[1]
            bx, by = b[0] * NODE + system.jitter(b)[0], b[1] * NODE + system.jitter(b)[1]
            if min(ax, bx) > x0 + width + 6 or max(ax, bx) < x0 - 6 or min(ay, by) > y0 + height + 6 or max(ay, by) < y0 - 6:
                continue
            mid = np.array([[(ax + bx) / 2, (ay + by) / 2]])
            _stamp(mask, x0, y0, mid, np.array([2.2]))
    return mask


def bridge_tiles(noise, x0: int, y0: int, width: int, height: int) -> Tuple[np.ndarray, np.ndarray]:
    """`(deck, approach)` masks of the natural bridges in the rectangle: planks over the water, and the path tiles of the banks."""
    system = system_for(noise)
    deck = np.zeros((width, height), dtype=bool)
    approach = np.zeros((width, height), dtype=bool)
    for river in system.rivers_near(x0, y0, width, height):
        for k in range(len(river.nodes)):
            found = system.bridge_at(river, k)
            if not found:
                continue
            for x, y, is_deck in found:
                if x0 <= x < x0 + width and y0 <= y < y0 + height:
                    (deck if is_deck else approach)[x - x0, y - y0] = True
    return deck, approach


def lava_mask(noise, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    """Tiles of the rectangle covered by lava: the big pools at the core of volcanic country."""
    return hot_spring_mask(noise, x0, y0, width, height, lava=True)


def hot_spring_mask(noise, x0: int, y0: int, width: int, height: int, lava: bool = False) -> np.ndarray:
    """Tiles of the rectangle covered by a hot spring (or, with `lava`, a lava lake): small irregular pools (three
    overlapping discs) deep in volcanic country."""
    system = system_for(noise)
    mask = np.zeros((width, height), dtype=bool)
    for i in range((x0 - 8) // HOT_CELL, (x0 + width + 8) // HOT_CELL + 1):
        for j in range((y0 - 8) // HOT_CELL, (y0 + height + 8) // HOT_CELL + 1):
            site = system.hot_site(i, j)
            if site is None:
                continue
            x, y, radius, is_lava = site
            if is_lava != lava:
                continue
            h = mix_seed(system.seed, i, j, 6262)
            dx, dy = ((h >> 4) % 100) / 100 * radius - radius / 2, ((h >> 12) % 100) / 100 * radius - radius / 2
            centres = np.array([[x, y], [x + dx, y + dy], [x - dy, y + dx]])
            _stamp(mask, x0, y0, centres, np.array([radius, radius * 0.75, radius * 0.65]))
    return mask
