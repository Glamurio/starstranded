import colorsys
"""Liquids: depth rings, hidden kinds, wading, acid."""
import numpy as np
import pytest

import behavior
import liquids
import tile_types
import worldgen
from chunks import CHUNK_H, CHUNK_W
from worldgen import NoiseWorldSource


def _liquid_tile(kind, depth):
    tile = tile_types.water.get_array()
    tile["liquid"], tile["depth"], tile["walkable"] = kind, depth, depth == 1
    return tile


def _chunks(seed, keys):
    source = NoiseWorldSource(seed)
    return {k: source.terrain(k) for k in keys}


def test_deeper_liquid_is_always_ringed_by_shallower_liquid():
    deep_seen = 0
    for seed in (1, 2, 3, 4):
        for key, tiles in _chunks(seed, [(x, y) for x in range(-2, 3) for y in range(-2, 3)]).items():
            depth = tiles["depth"].astype(int)
            import tile_types
            padded = np.pad(np.where(tile_types.is_laid(tiles), 9, depth), 1, constant_values=9)  # outside the chunk, or a plank: never a violation
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbour = padded[1 + dx:1 + dx + depth.shape[0], 1 + dy:1 + dy + depth.shape[1]]
                foam = tiles["light"]["fg"][..., 0] > 200            # (a waterfall drops straight from the bank: deliberately abrupt)
                bad = (depth >= 2) & (neighbour < depth - 1) & ~foam
                assert not bad.any(), (seed, key)
            deep_seen += int((depth >= 2).sum())
    assert deep_seen > 0


def test_only_shallow_liquid_can_be_waded_and_the_colours_grade_from_shore_to_deep():
    shallow, middle, deep = [], [], []
    for seed in (1, 2, 3):
        for tiles in _chunks(seed, [(0, 0), (1, 0), (0, 1), (-1, 0)]).values():
            depth = tiles["depth"]
            assert (tiles["liquid"][depth > 0] > 0).all() and (tiles["liquid"][depth == 0] == 0).all()
            assert np.array_equal(tiles["walkable"][depth > 0], depth[depth > 0] == 1)
            fg = tiles["light"]["fg"]
            shallow += fg[depth == 1].tolist()
            middle += fg[depth == 2].tolist()
            deep += fg[depth == 3].tolist()
    assert deep, "no deep liquid generated"
    brightness = lambda colours: np.mean([max(c) for c in colours])
    assert brightness(shallow) > brightness(middle) > brightness(deep)   # deep is the darker end of the gradient
    assert len({tuple(c) for c in shallow}) > 5                           # a gradient, not one flat colour


def test_lakes_are_vivid_and_not_all_one_colour():
    """There is no fixed lake colour: it comes from the biome the water rises in, so different places get clearly different, saturated water."""
    noise = worldgen.TerrainNoise(5)
    places = [worldgen.liquid_palette(noise, x, y, 1, 1) for x in range(-4000, 4000, 400) for y in range(-4000, 4000, 1600)]
    shallow = np.concatenate([p[0].reshape(-1, 3) for p in places])
    deep = np.concatenate([p[1].reshape(-1, 3) for p in places])
    hues = np.array([colorsys.rgb_to_hsv(*(c / 255.0))[0] for c in shallow]) * 360
    assert np.ptp(hues) > 60
    spread = shallow.max(axis=-1) - shallow.min(axis=-1)
    assert spread.min() > 40                                               # always saturated, never grey
    assert (deep.max(axis=-1) < shallow.max(axis=-1)).all()


def test_the_lake_palette_depends_only_on_the_place():
    noise = worldgen.TerrainNoise(5)
    whole, _, kinds = worldgen.liquid_palette(noise, 100, 100, 30, 30)
    part, _, part_kinds = worldgen.liquid_palette(noise, 110, 115, 10, 10)
    assert np.allclose(whole[10:20, 15:25], part) and (kinds[10:20, 15:25] == part_kinds).all()


def test_one_body_of_water_keeps_one_colour_and_one_kind():
    """Every tile fed by the same source has the same hue and nature, however far it runs: a river can be followed back to where
    its colour is from."""
    import hydrology
    noise = worldgen.TerrainNoise(5)
    checked = 0
    for kx in range(-6, 6):
        for ky in range(-6, 6):
            x0, y0 = kx * 70, ky * 40
            mask = hydrology.water_mask(noise, x0, y0, 70, 40)
            if mask.sum() < 20:
                continue
            ax, ay = worldgen.water_anchors(noise, x0, y0, 70, 40)
            shallow, _, kind = worldgen.liquid_palette(noise, x0, y0, 70, 40)
            for source in {(int(a), int(b)) for a, b in zip(ax[mask], ay[mask])}:
                same = mask & (ax == source[0]) & (ay == source[1])
                assert np.allclose(shallow[same], shallow[same][0]) and (kind[same] == kind[same][0]).all()
                checked += 1
    assert checked


def test_water_deepens_gradually_from_the_shore():
    noise = worldgen.TerrainNoise(5)
    liquid = np.zeros((40, 12), dtype=bool)
    liquid[10:, :] = True                                  # a straight shore with open water behind it
    mix = worldgen._water_depth_mix(liquid)
    column = mix[10:20, 6]
    assert column[0] == 0.0 and column[-1] == 1.0
    assert (np.diff(column) >= 0).all() and (np.diff(column)[:6] > 0).all()       # a smooth slope over several tiles, not two steps


def test_kinds_are_whole_numbers_between_impure_and_acidic():
    kinds = set()
    for tiles in _chunks(5, [(x, y) for x in range(-3, 4) for y in range(-3, 4)]).values():
        kinds.update(np.unique(tiles["liquid"]).tolist())
    assert kinds <= {0, 1, 2, 3, 4, 5} and {1} <= kinds


def test_describe_never_names_the_kind():
    for kind in (1, 2, 3, 4):
        assert liquids.describe(_liquid_tile(kind, 1)) == "Liquid, shallow"
    assert liquids.describe(tile_types.floor.get_array()) is None


def test_spawn_and_entrance_are_on_dry_ground():
    import shafts
    for seed in range(1, 12):
        tiles, _ = shafts.surface_layer(seed, (0, 0))
        sx, sy = shafts.start_point(seed)[0]
        ex, ey = shafts.entrance_of(seed)
        assert tiles["liquid"][sx, sy] == 0 and tiles["liquid"][ex, ey] == 0


def test_wading_through_acid_burns(small_world, monkeypatch):
    e = small_world(width=12, height=10)
    e.game_map.set_tile(3, 1, _liquid_tile(3, 1))
    e.game_map.set_tile(4, 1, _liquid_tile(1, 1))
    hp = e.player.hp
    e.player.move(4, 1)
    assert e.player.hp == hp  # plain liquid: harmless
    e.player.move(3, 1)
    assert e.player.hp == hp - liquids.ACID_WADE_DAMAGE


def test_acid_can_burn_the_armor(small_world, monkeypatch):
    from components.equippable import LeatherArmor
    e = small_world(width=12, height=10)
    armor = LeatherArmor(e.player.inventory)
    e.player.inventory.add(armor)
    e.player.equipment.toggle_equip(armor, add_message=False)
    assert e.player.equipment.armor is armor
    monkeypatch.setattr("random.random", lambda: 0.0)
    e.game_map.set_tile(3, 1, _liquid_tile(3, 1))
    e.player.move(3, 1)
    assert e.player.equipment.armor is None and armor not in e.player.inventory.items


def test_creatures_do_not_step_into_acid(small_world):
    e = small_world(width=12, height=10)
    e.game_map.set_tile(3, 1, _liquid_tile(3, 1))
    e.game_map.set_tile(4, 1, _liquid_tile(1, 1))
    assert not behavior.free_step(e, 3, 1) and behavior.free_step(e, 4, 1)
