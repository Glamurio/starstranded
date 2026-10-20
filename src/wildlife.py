"""Wildlife that lasts: animals are kept with their chunk, hunted-out ground recovers and herds breed, also while you are away.

Every surface chunk remembers how many wild animals it can carry (`chunk.wild_capacity`, set when it is populated) and when it was last
settled (`chunk.wild_stamp`). Whenever a chunk is simulated or comes back from storage, `settle` plays the days that have passed
since, one day at a time and in the same way for both (so distant ground is abstracted: nothing runs there, but the result is as if
a day of breeding and moving in had happened for each day away):

- **Breeding.** Each species with two or more well fed adults in the chunk may bear one young a day (`BIRTH_CHANCE`), as long as the chunk
  holds fewer than `OVERFLOW` times its capacity. The young is a new animal of the same species next to a parent.
- **Recovery.** A chunk below its capacity may draw one animal a day (`IMMIGRATION_CHANCE`) from the species its ground suits (the same
  table as at generation), placed out of the player's sight. A hunted-out chunk therefore fills up again over a few days.

It is deliberately small: no ages, no genes, no herd movement. Only the surface's own planet species take part (not Selenites, robots,
settlers or cave animals)."""
from __future__ import annotations

import random
from typing import List

from chunks import CHUNK_H, CHUNK_W
from entity import EntityCategory

BIRTH_CHANCE = 0.35
IMMIGRATION_CHANCE = 0.5
OVERFLOW = 1.5
MIN_CAPACITY = 3
FED = 0.4                 # a parent must have at least this share of its food and water
MAX_DAYS = 30             # the longest absence that is played out day by day (more counts as this much)
SIGHT = 14                # immigrants appear no closer than this to the player
BIRTH_RADIUS = 3


def is_wild(entity) -> bool:
    key = getattr(getattr(entity, "kind", None), "key", None) or ""
    return key.startswith("planet:fauna:") and ":cave_" not in key


def wild_animals(chunk) -> List:
    return [e for e in chunk.by_category[EntityCategory.UNIT] if is_wild(e) and e.is_alive]


def _now(world) -> int:
    game_world = getattr(world.engine, "game_world", None)
    return int(game_world.current_time) if game_world is not None else 0


def note(world, chunk, placed: int) -> None:
    """A chunk has just been populated with `placed` wild animals: that (at least `MIN_CAPACITY`) is what it can carry."""
    chunk.wild_capacity = max(placed, MIN_CAPACITY)
    chunk.wild_stamp = _now(world)


def settle(world, chunk, now: int) -> int:
    """Play the whole days since the chunk was last settled; returns how many animals were born or came in."""
    stamp = chunk.wild_stamp
    if stamp is None or chunk.wild_capacity <= 0:
        chunk.wild_stamp = now if chunk.wild_capacity > 0 else None
        return 0
    day = world.engine.config.day_length if getattr(world, "engine", None) is not None else 480
    days = min((now - stamp) // day, MAX_DAYS)
    if days <= 0:
        return 0
    chunk.wild_stamp = stamp + (now - stamp) // day * day         # (the rest of a day stays for next time)
    added = 0
    for n in range(days):
        rng = random.Random(hash((getattr(world.source, "floor_seed", 0), chunk.key, stamp // day + n)) & 0xFFFFFFFF)
        added += _breed(world, chunk, rng, now) + _recover(world, chunk, rng, now)
    return added


def _free_tile(world, chunk, rng, near=None, radius=BIRTH_RADIUS, out_of_sight_of=None):
    for _ in range(40):
        if near is not None:
            x, y = near[0] + rng.randint(-radius, radius), near[1] + rng.randint(-radius, radius)
        else:
            x, y = chunk.x0 + rng.randrange(CHUNK_W), chunk.y0 + rng.randrange(CHUNK_H)
        if not chunk.contains(x, y) or not world.is_walkable(x, y) or world.is_blocked(x, y) or world.tile_at(x, y)["liquid"]:
            continue
        if out_of_sight_of is not None and max(abs(x - out_of_sight_of.x), abs(y - out_of_sight_of.y)) < SIGHT:
            continue
        return x, y
    return None


def _breed(world, chunk, rng, now: int) -> int:
    from components.unit import Unit
    animals = wild_animals(chunk)
    if len(animals) >= chunk.wild_capacity * OVERFLOW:
        return 0
    born = 0
    by_species = {}
    for animal in animals:
        if animal.hunger >= FED * animal.max_hunger and animal.thirst >= FED * animal.max_thirst:
            by_species.setdefault(animal.kind.key, []).append(animal)
    for key in sorted(by_species):
        parents = by_species[key]
        if len(parents) < 2 or len(animals) + born + 1 > chunk.wild_capacity * OVERFLOW or rng.random() >= BIRTH_CHANCE:
            continue
        parent = rng.choice(parents)
        spot = _free_tile(world, chunk, rng, near=(parent.x, parent.y))
        if spot is not None:
            young = Unit(parent.kind)
            young.last_upkeep = now
            world.add_entity(young, *spot)
            born += 1
    return born


def _recover(world, chunk, rng, now: int) -> int:
    from components.unit import Unit
    import shafts
    source = world.source
    planet = getattr(source, "planet", None)
    if planet is None or getattr(source, "floor", 1) != 1 or len(wild_animals(chunk)) >= chunk.wild_capacity or rng.random() >= IMMIGRATION_CHANCE:
        return 0
    player = getattr(world.engine, "player", None)
    spot = _free_tile(world, chunk, rng, out_of_sight_of=player if player is not None and player.parent is world else None)
    if spot is None:
        return 0
    env = shafts.environment(source.floor_seed, chunk.key)
    lx, ly = spot[0] - chunk.x0, spot[1] - chunk.y0
    pool, weights = planet.fauna_weights({k: v[lx:lx + 1, ly:ly + 1] for k, v in env.items()})
    column = weights[:, 0, 0].tolist() if len(pool) else []
    if not column or sum(column) <= 0:
        return 0
    animal = Unit(rng.choices(pool, weights=column)[0])
    animal.last_upkeep = now
    world.add_entity(animal, *spot)
    return 1


def tick(world, chunks, now: int) -> None:
    """Settle the loaded chunks given (called each turn by the simulation; a chunk only does something once a day has passed)."""
    for chunk in chunks:
        if chunk.wild_capacity and chunk.wild_stamp is not None:
            day = world.engine.config.day_length
            if now - chunk.wild_stamp >= day:
                settle(world, chunk, now)

