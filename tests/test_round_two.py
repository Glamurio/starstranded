"""Feedback round: caves are big blended regions, the biome is named in the panel, built tiles keep their colour, sprites have an outline,
the sprite editor lists the new things, and the window can be borderless."""
import numpy as np
import pygame
import pytest

import atlas
import biomes
import regions
import settings
import spriteconfig
import tile_types
import underground as ug
import worldgen
from chunks import CHUNK_H, CHUNK_W


def test_cave_regions_are_large_and_change_gradually():
    for seed in (1, 2, 3):
        strip = np.concatenate([ug.field(seed, -1, (kx, 0)) for kx in range(-14, 15)])      # 2000 tiles across the world, one chunk row
        runs = int((np.diff(strip[:, CHUNK_H // 2]) != 0).sum())
        assert runs <= 12, (seed, runs)
    biome, other, edge = ug.blended(2, -1, (3, 3))
    assert edge.min() >= 0 and edge.max() <= 0.5 and (edge[biome == other] == 0).all()


def test_cave_colours_run_into_each_other_at_a_region_border():
    found = False
    for seed in range(1, 8):
        for kx in range(-8, 9):
            biome, other, edge = ug.blended(seed, -1, (kx, 0), 0)
            if ((edge > 0.2) & (biome != other)).any():
                landscape = np.full(biome.shape, tile_types.cave_floor.get_array(), dtype=tile_types.tile_dt)
                floor = np.ones(biome.shape, dtype=bool)
                ug.paint(landscape, biome, floor, ~floor, np.random.default_rng(1), other, edge)
                colours = {tuple(c) for c in landscape["light"]["fg"][floor & (edge > 0.2) & (biome != other)].tolist()}
                pure = {tuple(int(v) for v in ug.UBIOMES[k].floor) for k in ug.UBIOME_IDS}
                assert colours - pure, "border tiles are a mix, not one biome's colour"
                found = True
                break
        if found:
            break
    assert found


def test_surface_regions_are_in_provinces_of_kin():
    noise = worldgen.TerrainNoise(3)
    a = regions.province_family(noise, 10.0, 10.0)
    assert a == regions.province_family(noise, 20.0, 40.0) and a in biomes.FAMILIES
    assert regions.CELL >= 250 and regions.BORDER >= 30


def test_the_panel_names_the_biome_on_the_surface_and_below(new_engine):
    import resources
    engine = new_engine
    gw = engine.game_world
    p = engine.player
    assert resources.biome_label(gw, 0, p.x, p.y)
    assert resources.biome_label(gw, -1, p.x, p.y) in {u.name for u in ug.UBIOMES.values()}
    assert resources.biome_label(gw, 1, p.x, p.y) == ""


def test_built_tiles_are_flagged_and_keep_their_own_colour():
    for name in ("path", "bridge", "built_floor", "street", "farmland", "bridge_vertical", "bridge_h_mid"):
        assert getattr(tile_types, name).get_array()["built"], name
    assert not tile_types.floor.get_array()["built"] and not tile_types.cave_floor.get_array()["built"]


def test_every_sprite_has_a_one_pixel_black_outline_inside_its_cell():
    pygame.init()
    plain = atlas.load_alpha_sheet(_sheet_path())
    sheet = atlas.add_outline(plain)
    a0 = pygame.surfarray.array_alpha(plain)
    a1 = pygame.surfarray.array_alpha(sheet)
    rgb = pygame.surfarray.array3d(sheet)
    ring = (a1 > 0) & ~(a0 > 0)
    assert ring.any() and (rgb[ring] == 0).all() and (a1[ring] == 255).all()
    assert ((a0 > 0) <= (a1 > 0)).all()
    # a sprite never draws outline into the cell next to it: an empty cell stays empty
    cells = (a1[: a1.shape[0] // 24 * 24, : a1.shape[1] // 24 * 24] > 0).reshape(a1.shape[0] // 24, 24, a1.shape[1] // 24, 24).any(axis=(1, 3))
    lit = (a0[: a1.shape[0] // 24 * 24, : a1.shape[1] // 24 * 24] > 0).reshape(a1.shape[0] // 24, 24, a1.shape[1] // 24, 24).any(axis=(1, 3))
    assert (cells == lit).all()


def _sheet_path():
    return "urizen_white.png"


def test_the_sprite_editor_lists_cave_animals_scenery_ground_and_the_city():
    keys = spriteconfig.catalog()
    kinds = {k.split(".", 1)[0] for k in keys}
    assert {"fauna", "scenery", "ground", "city", "cave"} <= kinds
    assert {"fauna.cave_bat", "fauna.cave_beetle", "fauna.cave_moth"} <= set(keys)
    assert "scenery.wreck_car.0" in keys and "city.tower.0" in keys and "city.lane_h" in keys and "ground.plains.cover.0" in keys
    assert not [k for k in keys if k.startswith("item.scenery_")]


def test_changing_a_ground_or_scenery_sprite_applies_at_once():
    import scenery
    before = scenery.CELLS["pebbles"][0]
    spriteconfig._apply_live("scenery.pebbles.0", (9, 9))
    assert scenery.CELLS["pebbles"][0] == (9, 9)
    spriteconfig._apply_live("scenery.pebbles.0", before)
    cover = biomes.BIOMES["plains"].cover
    spriteconfig._apply_live("ground.plains.cover.0", (9, 9))
    assert biomes.BIOMES["plains"].cover[0] == (9, 9)
    spriteconfig._apply_live("ground.plains.cover.0", cover[0])
    assert biomes.BIOMES["plains"].cover == cover


def test_borderless_is_a_setting_and_tabbing_out_does_not_minimise():
    s = settings.Settings(borderless=1).clamp()
    assert s.borderless is True and settings.Settings().borderless is False
    import display
    import os
    display.Display(headless=True)
    assert os.environ.get("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS") == "0"
