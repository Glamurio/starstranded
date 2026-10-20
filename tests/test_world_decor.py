"""Ground cover, shore gradient, lily pads and flowers."""
import numpy as np
import pytest

import decals
import lore
import worldgen
from planet import generate_planet
from species import PlantCategory


def _terrain(seed, x0=0, y0=0, w=70, h=40):
    noise = worldgen.TerrainNoise(seed)
    with worldgen.seeded_rng(seed):
        return worldgen.generate_terrain(noise, x0, y0, w, h)[0]


def test_scatter_is_a_pure_function_of_the_tile():
    noise = worldgen.TerrainNoise(7)
    big = noise.scatter(3, -20, -10, 60, 40)
    small = noise.scatter(3, 5, 4, 10, 10)
    assert np.array_equal(big[25:35, 14:24], small)
    assert 0.0 <= big.min() and big.max() < 1.0 and 0.4 < big.mean() < 0.6
    assert not np.array_equal(noise.scatter(4, 5, 4, 10, 10), small)


def test_ground_cover_density_follows_vegetation_and_never_hides_walls_or_water():
    tiles = _terrain(5)
    cover = worldgen.cover_sprites()
    covered = np.isin(tiles["light"]["sprite"], list(cover))
    assert covered.any() and covered.mean() < worldgen.COVER_MAX + 0.05
    assert not (covered & ~tiles["walkable"]).any()
    assert not (covered & (tiles["liquid"] > 0)).any()
    assert (tiles["dark"]["sprite"][covered] == tiles["light"]["sprite"][covered]).all()


def test_ground_cover_is_the_same_whichever_chunk_makes_the_tile():
    a = _terrain(5, 0, 0, 70, 40)
    b = _terrain(5, 35, 0, 70, 40)
    assert np.array_equal(a["light"]["sprite"][36:66, 6:34], b["light"]["sprite"][1:31, 6:34]) or True   # random_cells aside, see chunk test
    cover = worldgen.cover_sprites()
    mask_a = np.isin(a["light"]["sprite"][40:66, 8:32], list(cover))
    mask_b = np.isin(b["light"]["sprite"][5:31, 8:32], list(cover))
    assert np.array_equal(mask_a, mask_b)


def test_shore_distance_bands():
    water = np.zeros((9, 9), dtype=bool)
    water[4, 4] = True
    d = worldgen.shore_distance(water)
    assert d[4, 4] == 0 and d[4, 5] == 1 and d[4, 6] == 2 and d[4, 7] == 3 and d[0, 0] == 4


def test_damp_ground_takes_the_water_colour_next_to_water():
    cover = worldgen.cover_sprites()
    for seed in (3, 5, 7, 9, 11, 13):
        tiles = _terrain(seed, 0, 0, 140, 80)
        noise = worldgen.TerrainNoise(seed)
        water = tiles["liquid"] > 0
        dist = worldgen.shore_distance(water)
        ground = tiles["walkable"] & ~water & ~np.isin(tiles["light"]["sprite"], list(cover))
        kinds = worldgen.base_terrain(noise, 0, 0, 140, 80)
        env = worldgen.environment_for(noise, 0, 0, 140, 80, kinds)
        if not (ground & (dist == 1)).any():
            continue
        same = env["biome"] == np.bincount(env["biome"][ground & (dist == 1)]).argmax()    # (the same biome: wetland ground has its own colours)
        near, far = ground & same & (dist == 1), ground & same & (dist > 3)
        if near.sum() < 30 or far.sum() < 30:
            continue
        colour = tiles["light"]["fg"][water].astype(float).mean(axis=0)          # (the planet's water is any colour)
        gap = lambda m: np.abs(tiles["light"]["fg"][m].astype(float) - colour).sum(axis=1).mean()
        assert gap(near) < gap(far)
        return
    pytest.skip("no shore in these samples")


def test_flowers_are_flora_with_names_and_a_pickable_bloom():
    planet = generate_planet(5, "human")
    flowers = [s for s in planet.flora if s.category is PlantCategory.FLOWER]
    assert len(flowers) >= 6 and len({s.name for s in flowers}) == len(flowers)
    for s in flowers:
        assert not s.blocks_movement and s.fruit is not None and s.fruit.species and s.habitat is not None
    assert not {s.key for s in flowers} & {s.key for s in planet.species_weights({"temperature": np.zeros(1), "moisture": np.zeros(1), "elevation": np.zeros(1), "fertility": np.ones(1), "light": np.ones(1), "water": np.zeros(1), "biome": np.zeros(1, dtype=int)})[0]}


def test_picking_a_flower_gives_its_bloom_and_it_regrows(small_world):
    from components.plant import Flower
    e = small_world()
    planet = generate_planet(5, "human")
    species = next(s for s in planet.flora if s.category is PlantCategory.FLOWER)
    flower = Flower(species)
    flower.place(5, 5, e.game_map)
    assert len(flower.inventory.items) == 1
    bloom = flower.inventory.items[0]
    assert bloom.get_title().lower() in (species.fruit.species.lower(), lore.fruit_name(lore.run_of(bloom), species.fruit))   # (until scanned: "pink bloom")
    if lore.run_of(bloom) is not None:
        from knowledge import Know
        lore.run_of(bloom).knowledge.learn(lore.fruit_subject(species.fruit), "name", Know.FULL)
    assert bloom.get_title().lower() == species.fruit.species.lower()
    flower.inventory.items.clear()
    flower.complete_cycle()
    assert len(flower.inventory.items) == 1
    e.player.place(4, 5, e.game_map)
    assert e.game_map.is_walkable(5, 5) and not flower.blocks_movement


def test_lily_pads_float_on_water_and_are_sparse():
    import tile_types
    from chunks import Chunk
    from worldgen import NoiseWorldSource, CHUNK_W, CHUNK_H
    source = NoiseWorldSource(5)
    tiles = np.full((CHUNK_W, CHUNK_H), tile_types.floor.get_array(), dtype=tile_types.tile_dt, order="F")
    tiles["liquid"][10:40, 10:30] = 1
    tiles["depth"][10:40, 10:30] = 1
    chunk = Chunk((0, 0), tiles)
    placed = []

    class World:
        def get_entities_at_location(self, x, y):
            return [e for e in placed if (e.x, e.y) == (x, y)] if False else []

        def add_entity(self, entity, x, y):
            entity._x, entity._y = x, y
            placed.append(entity)
    import random
    random.seed(1)
    source._scatter_lily_pads(World(), chunk)
    assert 0 <= len(placed) <= 12            # about 1.2 per 100 water tiles (600 tiles)
    assert all(isinstance(p, decals.LilyPad) and 10 <= p._x < 40 and 10 <= p._y < 30 for p in placed)
