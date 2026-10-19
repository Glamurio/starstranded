"""Wildlife that lasts: animals persist with their chunk, emptied ground recovers, herds breed, also over days away."""
import random

import pytest

import wildlife
from chunks import chunk_key
from test_lore import new_game


def _populated(engine, exclude):
    """A loaded surface chunk other than `exclude` that carries wildlife (capacity noted at generation) and has land."""
    world = engine.game_map
    for _ in range(6):
        for chunk in list(world.chunks.values()):
            if chunk.key != exclude and chunk.wild_capacity and wildlife.wild_animals(chunk):
                return chunk
        world.load_chunk((exclude[0] + random.randint(-3, 3), exclude[1] + random.randint(-3, 3)))
    pytest.skip("no populated chunk found")


@pytest.fixture
def game():
    random.seed(3)
    engine = new_game(seed=41)
    engine.update_fov()
    return engine


def _kill_all(world, chunk):
    for animal in wildlife.wild_animals(chunk):
        world.remove_entity(animal) if hasattr(world, "remove_entity") else animal.die(None, quiet=True)


def test_a_populated_chunk_remembers_its_capacity_and_time(game):
    chunk = _populated(game, chunk_key(game.player.x, game.player.y))
    assert chunk.wild_capacity >= wildlife.MIN_CAPACITY and chunk.wild_stamp is not None


def test_animals_come_back_from_storage_as_they_were(game):
    world = game.game_map
    chunk = _populated(game, chunk_key(game.player.x, game.player.y))
    key = chunk.key
    before = sorted((a.kind.key, a.x, a.y, a.hp) for a in wildlife.wild_animals(chunk))
    world.unload_chunk(key)
    game.game_world.current_time += 10                 # (ten turns: no day has passed)
    back = world.load_chunk(key)
    after = sorted((a.kind.key, a.x, a.y, a.hp) for a in wildlife.wild_animals(back))
    assert after == before


def test_hunted_out_ground_fills_up_again_over_the_days_away(game):
    world = game.game_map
    chunk = _populated(game, chunk_key(game.player.x, game.player.y))
    key, capacity = chunk.key, chunk.wild_capacity
    for animal in wildlife.wild_animals(chunk):
        animal.die(None, quiet=True)
    assert not wildlife.wild_animals(chunk)
    world.unload_chunk(key)
    game.game_world.current_time += game.config.day_length * 12
    back = world.load_chunk(key)
    now = len(wildlife.wild_animals(back))
    assert 0 < now <= capacity * wildlife.OVERFLOW


def test_a_short_absence_changes_nothing_and_a_long_one_is_capped(game):
    world = game.game_map
    chunk = _populated(game, chunk_key(game.player.x, game.player.y))
    count = len(wildlife.wild_animals(chunk))
    assert wildlife.settle(world, chunk, chunk.wild_stamp + game.config.day_length - 1) == 0
    assert len(wildlife.wild_animals(chunk)) == count
    added = wildlife.settle(world, chunk, chunk.wild_stamp + game.config.day_length * 10_000)
    assert added <= 2 * wildlife.MAX_DAYS


def test_two_well_fed_animals_of_a_species_breed_up_to_the_limit(game):
    from components.unit import Unit
    world = game.game_map
    chunk = _populated(game, chunk_key(game.player.x, game.player.y))
    for animal in wildlife.wild_animals(chunk):
        animal.die(None, quiet=True)
    species = next(s for s in game.game_world.planet.fauna if s.habitat is not None)
    spots = [(chunk.x0 + x, chunk.y0 + y) for x in range(70) for y in range(40)
             if world.is_walkable(chunk.x0 + x, chunk.y0 + y) and not world.is_blocked(chunk.x0 + x, chunk.y0 + y)
             and not world.tile_at(chunk.x0 + x, chunk.y0 + y)["liquid"]][:2]
    for spot in spots:
        world.add_entity(Unit(species), *spot)
    chunk.wild_capacity = 4
    stamp = chunk.wild_stamp
    wildlife.settle(world, chunk, stamp + game.config.day_length * 20)
    count = len(wildlife.wild_animals(chunk))
    assert 2 < count <= 4 * wildlife.OVERFLOW


def test_hungry_animals_do_not_breed(game):
    from components.unit import Unit
    world = game.game_map
    chunk = _populated(game, chunk_key(game.player.x, game.player.y))
    for animal in wildlife.wild_animals(chunk):
        animal.die(None, quiet=True)
    species = next(s for s in game.game_world.planet.fauna if s.habitat is not None)
    spots = [(chunk.x0 + x, chunk.y0 + y) for x in range(70) for y in range(40)
             if world.is_walkable(chunk.x0 + x, chunk.y0 + y) and not world.is_blocked(chunk.x0 + x, chunk.y0 + y)
             and not world.tile_at(chunk.x0 + x, chunk.y0 + y)["liquid"]][:2]
    for spot in spots:
        unit = Unit(species)
        unit.hunger = 0
        world.add_entity(unit, *spot)
    chunk.wild_capacity = 6
    rng = random.Random(1)
    assert sum(wildlife._breed(world, chunk, rng, game.game_world.current_time) for _ in range(30)) == 0


def test_only_planet_wildlife_takes_part():
    from components.unit import Unit
    import species as defs
    assert not wildlife.is_wild(Unit(defs.SELENITE)) and not wildlife.is_wild(Unit(defs.ROBOT))


def test_the_turn_settles_loaded_chunks_once_a_day_has_passed(game):
    import simulation
    world = game.game_map
    chunk = _populated(game, chunk_key(game.player.x, game.player.y))
    day = game.config.day_length
    game.game_world.current_time = chunk.wild_stamp + 2 * day + 5
    simulation.run_turn(game)
    assert chunk.wild_stamp >= game.game_world.current_time - day      # (it was settled, not left two days behind)
