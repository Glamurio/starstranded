"""What the ground is made of: mining deposits, loose stones, sand and clay.

All of it is a pure function of the planet seed and the tile, so a rock you dig out is the same rock when you come back.
Rock in walls comes in *deposits* (5x5 tile cells): most are ordinary stone of the local biome's kinds, some are an ore
vein, a seam of coal, crystal or (rarely, and deeper) radioactive ore. Loose stones lie on the surface; sand and clay are
dug from shores and the right biomes.
"""
from __future__ import annotations

import random
from typing import Optional, Tuple

import biomes
from chunks import chunk_key, local
from materials import Material
from seeds import mix_seed

DEPOSIT_CELL = 5
ORE_CHANCE = 0.13
COAL_CHANCE = 0.08
CRYSTAL_CHANCE = 0.05
RADIOACTIVE_CHANCE = 0.025
DEEP_BONUS = 1.6
"""Caves hold richer deposits than the surface."""

SANDY_BIOMES = frozenset({"desert", "badlands", "savanna"})
CLAYEY_BIOMES = frozenset({"swamp", "bog", "jungle"})
DIG_TURNS_BARE = 3
DIG_TURNS_TOOL = 1


def biome_key_at(game_world, z: int, x: int, y: int) -> str:
    """The biome of surface tile (x, y); caves and upper floors count as bare rock ("grey")."""
    if z != 0:
        return "temperate_forest"
    import shafts
    env = shafts.environment(game_world.master_seed, chunk_key(x, y))
    lx, ly = local(x, y)
    return biomes.BIOME_IDS[int(env["biome"][lx, ly])]


def ambient_temperature(game_world, z: int, x: int, y: int, now: int) -> float:
    """Degrees C at the tile right now: the biome's noon temperature plus the planet's offset, colder at night and
    constant underground (caves hold the planet's mean)."""
    import lighting
    planet = game_world.planet
    offset = planet.temp_offset if planet is not None else 0
    if z < 0:
        return 12.0 + offset
    biome = biomes.BIOMES[biome_key_at(game_world, z, x, y)]
    light = lighting.daylight(now, game_world.engine.config) if z == 0 else 1.0
    return biome.ambient + offset - biome.night_drop * (1.0 - light)


def deposit_rng(master: int, z: int, x: int, y: int) -> random.Random:
    return random.Random(mix_seed(master, z, x // DEPOSIT_CELL, y // DEPOSIT_CELL, 77))


def wall_material(planet, master: int, z: int, x: int, y: int, biome_key: str) -> Material:
    """The material in the rock face at (x, y): the deposit of its 5x5 cell (stone variants are picked per tile)."""
    rng = deposit_rng(master, z, x, y)
    bonus = DEEP_BONUS if z < 0 else 1.0
    roll = rng.random()
    limits = (ORE_CHANCE * bonus, COAL_CHANCE * bonus, CRYSTAL_CHANCE * bonus, RADIOACTIVE_CHANCE * bonus * (2.0 if z < 0 else 0.0))
    if roll < limits[0] and planet.ore_ids:
        return planet.material(rng.choice(planet.ore_ids))
    roll -= limits[0]
    if 0 <= roll < limits[1]:
        return planet.material(planet.coal_id)
    roll -= limits[1]
    if 0 <= roll < limits[2]:
        crystals = [m for m in planet.stones_for_biome("crystalline") if m.family.value == "crystal"]
        if crystals:
            return crystals[rng.randrange(len(crystals))]
    roll -= limits[2]
    if 0 <= roll < limits[3]:
        return planet.material(planet.radioactive_id)
    stones = planet.stones_for_biome(biome_key)
    stones = [m for m in stones if m.family.value == "stone" and m.id.split(":")[1] not in ("flint", "porous")] or stones
    tile_rng = random.Random(mix_seed(master, z, x, y, 78))
    return stones[tile_rng.randrange(len(stones))]


def surface_stone(planet, master: int, x: int, y: int, salt: int, biome_key: str) -> Material:
    """A loose stone found lying at (x, y) (flint and light pumice are among them everywhere)."""
    stones = planet.stones_for_biome(biome_key)
    rng = random.Random(mix_seed(master, x, y, salt, 79))
    return stones[rng.randrange(len(stones))]


def ground_material(planet, game_world, world, x: int, y: int) -> Optional[Tuple[str, Material]]:
    """`(form, material)` that can be dug from the ground at (x, y): sand or clay, else None (just soil)."""
    biome_key = biome_key_at(game_world, world.z, x, y)
    near_water = any(world.tile_at(x + dx, y + dy) is not None and world.tile_at(x + dx, y + dy)["liquid"]
                     for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    rng = random.Random(mix_seed(game_world.master_seed, world.z, x // 3, y // 3, 80))
    if biome_key in SANDY_BIOMES or (near_water and rng.random() < 0.5):
        return "sand", planet.material(planet.sand_id)
    if biome_key in CLAYEY_BIOMES or near_water:
        return "clay", planet.material(planet.clay_id)
    return None


def mine_difficulty(rock: Material) -> float:
    """The head hardness needed to break the rock: its own hardness, less a little (ores are crumbly)."""
    return rock.hardness - 0.5
