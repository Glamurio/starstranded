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
            padded = np.pad(depth, 1, constant_values=9)  # outside the chunk: unknown, never a violation
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbour = padded[1 + dx:1 + dx + depth.shape[0], 1 + dy:1 + dy + depth.shape[1]]
                bad = (depth >= 2) & (neighbour < depth - 1)
                assert not bad.any(), (seed, key)
            deep_seen += int((depth >= 2).sum())
    assert deep_seen > 0


def test_only_shallow_liquid_can_be_waded_and_the_colours_grade_from_shore_to_deep():
    colours = {1: set(), 2: set(), 3: set()}
    for seed in (1, 2, 3):
        for tiles in _chunks(seed, [(0, 0), (1, 0), (0, 1), (-1, 0)]).values():
            depth = tiles["depth"]
            assert (tiles["liquid"][depth > 0] > 0).all() and (tiles["liquid"][depth == 0] == 0).all()
            assert np.array_equal(tiles["walkable"][depth > 0], depth[depth > 0] == 1)
            for d in (1, 2, 3):
                colours[d].update(map(tuple, tiles["light"]["fg"][depth == d].tolist()))
    assert colours[3], "no deep liquid generated"
    assert colours[3] == {worldgen.DEEP_COLOR}                 # the middle of a lake is the plain deep colour
    def near(found, base, tolerance):
        return all(max(abs(a - b) for a, b in zip(c, base)) <= tolerance for c in found)
    assert near(colours[1], worldgen.SHALLOW_COLOR, 60)       # shallows are shallow-coloured, tinted by the shore
    assert near(colours[2], worldgen.DEEP_COLOR, 60) and not near(colours[2], worldgen.DEEP_COLOR, 0)   # half-way to the shallows
    assert len(colours[1]) > 10                                # a gradient, not one flat colour
    assert sum(worldgen.DEEP_COLOR) < sum(worldgen.SHALLOW_COLOR)  # deep is the darker of the two


def test_kinds_are_whole_numbers_between_impure_and_acidic():
    kinds = set()
    for tiles in _chunks(5, [(x, y) for x in range(-3, 4) for y in range(-3, 4)]).values():
        kinds.update(np.unique(tiles["liquid"]).tolist())
    assert kinds <= {0, 1, 2, 3} and {1} <= kinds


def test_describe_never_names_the_kind():
    for kind in (1, 2, 3):
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
