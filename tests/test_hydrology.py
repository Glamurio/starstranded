"""Rivers: sources, downhill courses, confluences, honest ends, no stray puddles, agreement across chunk borders."""
from collections import Counter, deque

import numpy as np
import pytest

import hydrology
import relief
import worldgen

SEEDS = (1, 5, 12345)
AREA = (-700, -400, 1400, 800)


@pytest.fixture(scope="module", params=SEEDS)
def world(request):
    noise = worldgen.TerrainNoise(request.param)
    system = hydrology.system_for(noise)
    return noise, system, system.rivers_near(*AREA)


def test_there_are_rivers(world):
    noise, system, rivers = world
    assert len(rivers) >= 5
    assert {r.source for r in rivers} <= {"spring", "thaw"}


def test_every_river_flows_downhill_from_its_source(world):
    noise, system, rivers = world
    for river in rivers:
        heights = [system.height(*node) for node in river.nodes]
        body = heights[:-hydrology.RUN_ON] if river.end == "sea" else heights
        assert all(a > b for a, b in zip(body, body[1:])), river.cell
        assert heights[0] >= hydrology.SOURCE_MIN_HEIGHT, "a source starts on high ground"


def test_every_river_ends_in_the_sea_or_a_lake(world):
    noise, system, rivers = world
    for river in rivers:
        assert river.end in ("sea", "lake")
        x, y = river.nodes[-1][0] * hydrology.NODE, river.nodes[-1][1] * hydrology.NODE
        mask = hydrology.water_mask(noise, x - 15, y - 15, 31, 31)
        assert mask[10:21, 10:21].sum() >= 20, f"no water where river {river.cell} ends"
        if river.end == "sea":
            assert system.height(*river.nodes[-hydrology.RUN_ON - 1]) < relief.SEA_LEVEL + hydrology.SEA_MARGIN


def test_rivers_merge_and_the_flow_adds_up(world):
    noise, system, rivers = world
    flow = Counter()
    for river in rivers:
        flow.update(river.nodes)
    assert max(flow.values()) >= 2, "no confluence in the sample"
    assert hydrology.river_width(1) < hydrology.river_width(4) < hydrology.river_width(9)


def test_water_is_the_same_however_the_world_is_cut(world):
    noise, system, rivers = world
    whole = hydrology.water_mask(noise, -300, -200, 600, 400)
    part = hydrology.water_mask(noise, -100, -50, 200, 150)
    assert np.array_equal(whole[200:400, 150:300], part)


def test_no_stray_puddles(world):
    """Every body of water (river, lake or sea) has at least six tiles."""
    noise, system, rivers = world
    x0, y0, w, h = -300, -200, 600, 400
    kinds = worldgen.base_terrain(noise, x0, y0, w, h)
    water = kinds == 0
    seen = np.zeros_like(water)
    small = []
    for sx, sy in np.argwhere(water & ~seen).tolist():
        if seen[sx, sy]:
            continue
        queue, size = deque([(sx, sy)]), 0
        seen[sx, sy] = True
        touches_edge = False
        while queue:
            x, y = queue.popleft()
            size += 1
            touches_edge |= x in (0, w - 1) or y in (0, h - 1)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and water[nx, ny] and not seen[nx, ny]:
                    seen[nx, ny] = True
                    queue.append((nx, ny))
        if size < 6 and not touches_edge:
            small.append((sx + x0, sy + y0, size))
    assert not small, small[:5]


def test_the_landing_chunk_has_no_river():
    for seed in SEEDS + (2, 3, 11, 99):
        noise = worldgen.TerrainNoise(seed)
        assert not hydrology.water_mask(noise, 0, 0, 70, 40).any(), seed


# ── fjords ──────────────────────────────────────────────────────────────────────────────────────────────
def test_fjords_are_drowned_valleys_that_reach_the_sea_through_mountains():
    found = 0
    for seed in (3, 5, 12345, 7, 8):
        noise = worldgen.TerrainNoise(seed)
        system = hydrology.system_for(noise)
        for river in system.rivers_near(-1000, -600, 2000, 1200):
            if river.fjord_from < 0:
                continue
            found += 1
            assert river.end == "sea"
            assert len(river.nodes) - river.fjord_from >= hydrology.FJORD_MIN_NODES + hydrology.RUN_ON
            ix, iy = river.nodes[river.fjord_from]
            assert relief.range_potential(noise, ix * hydrology.NODE, iy * hydrology.NODE, 1, 1)[0, 0] >= hydrology.FJORD_MIN_RANGE
            mx, my = river.nodes[(river.fjord_from + len(river.nodes)) // 2]
            wet = hydrology.water_mask(noise, mx * hydrology.NODE - 10, my * hydrology.NODE - 10, 21, 21)
            assert wet.sum() >= 100, "a fjord is wide"
    assert found >= 3


# ── hot springs ─────────────────────────────────────────────────────────────────────────────────────────
def test_hot_springs_lie_in_hot_ground_and_are_real_pools():
    import biomes
    seen = 0
    for seed in (1, 5, 99):
        noise = worldgen.TerrainNoise(seed)
        system = hydrology.system_for(noise)
        for i in range(-16, 16):
            for j in range(-10, 10):
                site = system.hot_site(i, j)
                if site is None:
                    continue
                seen += 1
                x, y, radius, lava = site
                env = worldgen.environment_for(noise, int(x), int(y), 1, 1, np.ones((1, 1), dtype=np.int8))
                assert biomes.BIOMES[biomes.BIOME_IDS[int(env["biome"][0, 0])]].hot_springs > 0
                pool = hydrology.hot_spring_mask(noise, int(x) - 8, int(y) - 8, 17, 17, lava=lava)
                assert pool.sum() >= 12
    assert seen >= 3


def test_hot_spring_tiles_are_hot_liquid_and_scald_waders(new_engine):
    import liquids
    from components.unit import Unit
    from test_turn_flow import quiet_corridor
    noise = worldgen.TerrainNoise(5)
    mask = hydrology.hot_spring_mask(noise, -1000, -600, 2000, 1200)
    assert mask.any()
    x0, y0 = np.argwhere(mask)[0]
    tiles, _ = worldgen.generate_terrain(noise, int(x0) - 1000 - 10, int(y0) - 600 - 10, 70, 40)
    assert (tiles["liquid"] == int(liquids.LiquidKind.HOT)).any()
    quiet_corridor(new_engine)
    engine, world = new_engine, new_engine.game_map
    x, y = engine.player.x + 1, engine.player.y
    world.modify_tile(x, y, walkable=True, liquid=int(liquids.LiquidKind.HOT), depth=1)
    hp = engine.player.hp
    engine.player.move(x, y)
    assert engine.player.hp == hp - liquids.HOT_WADE_DAMAGE


def test_lava_lakes_are_unwalkable_deep_and_only_in_lava_country():
    import biomes
    import liquids
    found = 0
    for seed in (1, 5, 99, 7, 21, 33, 2, 4, 8, 12):          # (volcanic regions are big and rare now: look over a wider area)
        noise = worldgen.TerrainNoise(seed)
        system = hydrology.system_for(noise)
        for i in range(-40, 40):
            if found >= 3:
                break
            for j in range(-25, 25):
                site = system.hot_site(i, j)
                if site is None or not site[3]:
                    continue
                x, y = int(site[0]), int(site[1])
                env = worldgen.environment_for(noise, x, y, 1, 1, np.ones((1, 1), dtype=np.int8))
                biome = biomes.BIOMES[biomes.BIOME_IDS[int(env["biome"][0, 0])]]
                assert biome.family == "volcanic" and biome.hot_springs >= hydrology.LAVA_HOT
                tiles, _ = worldgen.generate_terrain(noise, x - 35, y - 20, 70, 40)
                lava = tiles["liquid"] == int(liquids.LiquidKind.LAVA)
                assert lava.sum() >= 12
                assert not tiles["walkable"][lava].any() and (tiles["depth"][lava] == 3).all()
                found += 1
    assert found >= 1


def test_waterfalls_are_deep_unwadable_foam_in_rivers():
    import liquids
    noise = worldgen.TerrainNoise(1234)
    fall = hydrology.waterfall_mask(noise, -600, -350, 1200, 700)
    assert fall.any()
    x, y = (int(v) for v in np.argwhere(fall)[0])
    tiles, _ = worldgen.generate_terrain(noise, x - 600 - 35, y - 350 - 20, 70, 40)
    foam = (tiles["depth"] == 3) & (tiles["liquid"] != 0) & (tiles["light"]["fg"][..., 0] > 200)
    assert foam.any() and not tiles["walkable"][foam].any()


# ── bridges ─────────────────────────────────────────────────────────────────────────────────────────────
def _bridges(seed, x0=-600, y0=-350, w=1200, h=700):
    noise = worldgen.TerrainNoise(seed)
    system = hydrology.system_for(noise)
    out = []
    for river in system.rivers_near(x0, y0, w, h):
        for k in range(len(river.nodes)):
            found = system.bridge_at(river, k)
            if found:
                out.append(found)
    return noise, out


def test_natural_bridges_are_uncommon_short_and_have_dry_banks():
    import tile_types
    for seed in (1234, 5):
        noise, bridges = _bridges(seed)
        assert 1 <= len(bridges) <= 25
        for found in bridges:
            deck = [p for p in found if p[2]]
            assert hydrology.BRIDGE_SPAN[0] <= len(deck) <= hydrology.BRIDGE_SPAN[1]
            for a, b in zip(found, found[1:]):
                assert max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1           # one unbroken line of tiles
            xs, ys = [p[0] for p in found], [p[1] for p in found]
            x0, y0 = min(xs) - 3, min(ys) - 3
            tiles, trees = worldgen.generate_terrain(noise, x0, y0, max(xs) - x0 + 4, max(ys) - y0 + 4)
            for x, y, is_deck in found:
                tile = tiles[x - x0, y - y0]
                assert tile["walkable"] and tile["liquid"] == 0 and not trees[x - x0, y - y0]
                assert bool(tile_types.is_laid(tile[None])[0])


def test_a_bridge_looks_the_same_from_either_chunk():
    import tile_types
    noise, bridges = _bridges(1234)
    xs, ys = [p[0] for p in bridges[0]], [p[1] for p in bridges[0]]
    cx, cy = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
    whole, _ = worldgen.generate_terrain(noise, cx - 40, cy - 30, 80, 60)
    left, _ = worldgen.generate_terrain(noise, cx - 40, cy - 30, 40, 60)
    right, _ = worldgen.generate_terrain(noise, cx, cy - 30, 40, 60)
    assert np.array_equal(tile_types.is_laid(whole)[:40], tile_types.is_laid(left))
    assert np.array_equal(tile_types.is_laid(whole)[40:], tile_types.is_laid(right))
