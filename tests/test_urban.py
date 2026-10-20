"""Urban regions: districts are laid out from world coordinates, so they do not depend on the chunk that draws them."""
import numpy as np
import pytest

import biomes
import regions
import urban
import worldgen
from chunks import CHUNK_H, CHUNK_W

URBAN = [k for k, b in biomes.BIOMES.items() if b.urban is not None]


def _density(w, h):
    return np.full((w, h), 0.7)


def _layout(style, x0, y0, w, h, region=12345):
    xs, ys = urban._grid(x0, y0, w, h)
    return urban.layout(7, style, xs, ys, np.full((w, h), region, dtype=np.int64), _density(w, h))


@pytest.mark.parametrize("key", URBAN)
def test_a_layout_is_the_same_whichever_rectangle_asks(key):
    style = biomes.BIOMES[key].urban
    big = _layout(style, -80, -60, 200, 140)
    small = _layout(style, 10, -5, 70, 40)
    for name in ("road", "ring", "fallen", "door", "inside", "tower", "factory", "corner"):
        assert np.array_equal(getattr(big, name)[90:160, 55:95], getattr(small, name)), name


def test_streets_form_a_grid_and_buildings_stand_on_blocks_between_them():
    style = biomes.BIOMES["abandoned_district"].urban
    lay = _layout(style, 0, 0, 200, 150)
    px, py = style.pitch
    assert lay.road.mean() == pytest.approx(1 - (1 - style.road / px) * (1 - style.road / py), abs=0.03)
    assert not (lay.ring & lay.road).any() and not (lay.tower & lay.road).any()
    assert lay.ring.any() and lay.tower.any() and lay.door.any() and lay.fallen.any()
    assert not (lay.fallen & lay.door).any() and (lay.door <= lay.ring).all()
    assert lay.lane_h.any() and lay.lane_v.any() and lay.crossing.any()


def test_a_district_is_denser_in_its_heart():
    style = biomes.BIOMES["abandoned_district"].urban
    xs, ys = urban._grid(0, 0, 300, 220)
    region = np.full((300, 220), 5, dtype=np.int64)
    thin = urban.layout(7, style, xs, ys, region, np.full((300, 220), 0.1))
    thick = urban.layout(7, style, xs, ys, region, np.full((300, 220), 1.0))
    assert (thick.ring | thick.tower).sum() > 1.5 * (thin.ring | thin.tower).sum()


def test_huts_have_no_streets():
    lay = _layout(biomes.BIOMES["ancient_settlement_remains"].urban, 0, 0, 200, 150)
    assert not lay.road.any() and lay.ring.any()


def _find(noise, key, span=2400):
    for y in range(-span, span, 90):
        for x in range(-span, span, 90):
            if regions.biome_at(noise, x, y) == key:
                kinds = worldgen.base_terrain(noise, x - 35, y - 20, 70, 40)
                env = worldgen.environment_for(noise, x - 35, y - 20, 70, 40, kinds)
                if (env["biome"] == biomes.BIOME_INDEX[key]).mean() > 0.6:
                    return x - 35, y - 20
    return None


def test_painting_makes_streets_and_solid_towers_and_leaves_no_trees_on_them():
    noise = worldgen.TerrainNoise(1)
    spot = None
    for seed in (1, 2, 3, 4, 5, 6):
        noise = worldgen.TerrainNoise(seed)
        spot = _find(noise, "abandoned_district") or _find(noise, "industrial_ruins")
        if spot:
            break
    assert spot, "no city found in six seeds"
    with worldgen.seeded_rng(1):
        tiles, trees = worldgen.generate_terrain(noise, spot[0], spot[1], 70, 40)
    kinds = worldgen.base_terrain(noise, spot[0], spot[1], 70, 40)
    env = worldgen.environment_for(noise, spot[0], spot[1], 70, 40, kinds)
    xs, ys = urban._grid(spot[0], spot[1], 70, 40)
    style = biomes.BIOMES[biomes.BIOME_IDS[int(np.bincount(env["biome"].ravel()).argmax())]].urban
    lay = urban.layout(noise.floor_seed, style, xs, ys, env["region"], urban.density_field(noise, spot[0], spot[1], 70, 40))
    towers = lay.tower & (env["biome"] == biomes.BIOME_INDEX[biomes.BIOME_IDS[int(np.bincount(env["biome"].ravel()).argmax())]]) & (kinds == 1)
    assert towers.any()
    assert not tiles["walkable"][towers].any() and not tiles["transparent"][towers].any()
    assert not trees[lay.road & (kinds == 1)].any()


def test_a_city_chunk_is_walled_wrecked_and_empty_of_people(new_engine):
    import debug
    from components.unit import Unit
    from crafting import Wall
    import scenery
    engine = new_engine
    noise = engine.game_world.world_at(0).source.noise
    spot = None
    for key in ("abandoned_district", "industrial_ruins", "overgrown_city"):
        spot = _find(noise, key)
        if spot:
            break
    if spot is None:
        pytest.skip("no city near the start of this world")
    debug._enabled = True
    debug.teleport(engine, spot[0] + 35, spot[1] + 20)
    world = engine.game_map
    walls = [e for e in world.entities if isinstance(e, Wall)]
    assert len(walls) > 20
    assert any(getattr(e, "scenery_key", "") in ("lamp_post", "signpost", "wreck_car", "wreck_truck", "rubble") for e in world.entities)
    assert not [e for e in world.entities if isinstance(e, Unit) and e is not engine.player and e.kind.faction == "federation"]
    debug._enabled = False
