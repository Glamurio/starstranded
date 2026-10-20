"""Tiered simulation.

Tiers are defined around the player's chunk (see `GameConfig`):

- ACTIVE: chunks within `active_radius` (default 0 = the player's chunk): every actor runs its full AI every turn.
- NEAR: loaded chunks within `GameConfig.sim_radius` (default 2): every `near_interval` turns each actor gets its upkeep and one
  the same decisions as the full AI with greedy steps (`near_step`): no pathfinding.
- FAR: not loaded (or loaded but beyond the simulated radius: frozen). Nothing runs.

Survival upkeep (hunger, thirst, plant growth) is accounted *per entity* with `last_upkeep`: `upkeep(entity, now)`
applies every step in `(last_upkeep, now]`. One elapsed turn runs the original per-turn code; longer gaps (an entity
coming back from a frozen or unloaded chunk) are applied analytically in one go.
"""
from __future__ import annotations

import random
from heapq import heappop, heappush
from typing import Optional, Tuple, TYPE_CHECKING

import exceptions
from chunks import chebyshev, chunk_key
from entity import EntityCategory

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

HUNGER_DAYS, THIRST_DAYS = 7, 3
"""Full hunger lasts this many days of `GameConfig.day_length` (480 turns) with nothing eaten, full thirst this many without drinking: then you die."""
HUNGER_PERIOD = -(-HUNGER_DAYS * 480 // 100)  # hunger -1 every 34th turn (a little over 7 days from 100 to 0)
THIRST_PERIOD = -(-THIRST_DAYS * 480 // 100)  # thirst -1 every 15th turn (a little over 3 days)
GROWTH_PERIOD = 2  # plants grow every 2nd turn


def steps_between(last: int, now: int, period: int) -> int:
    """How many multiples of `period` lie in (last, now]."""
    return now // period - last // period


# ── upkeep ─────────────────────────────────────────────────────────────────────────
def upkeep(entity: Entity, now: int) -> None:
    """Bring `entity`'s hunger/thirst (units) or growth (plants) up to time `now`."""
    last = getattr(entity, "last_upkeep", None)
    if last is None:
        last = now - 1  # never simulated: one ordinary turn, exactly like the old per-turn upkeep
    if now <= last:
        return
    entity.last_upkeep = now
    elapsed = now - last
    if entity.category is EntityCategory.PLANT:
        _plant_upkeep(entity, last, now, elapsed)
    elif entity.category is EntityCategory.UNIT:
        _unit_upkeep(entity, last, now, elapsed)


def _unit_upkeep(unit, last: int, now: int, elapsed: int) -> None:
    hunger_steps = steps_between(last, now, HUNGER_PERIOD)
    thirst_steps = steps_between(last, now, THIRST_PERIOD)
    if elapsed == 1:
        if hunger_steps:
            unit.handle_hunger(-1)
        if thirst_steps:
            unit.handle_thirst(-1)
        unit.tick_poison(1)
        return
    if not unit.is_alive:
        return
    unit.tick_poison(elapsed)
    # A long absence: assume the unit kept itself fed if its chunk has food (the full simulation lets animals forage;
    # without this every animal left behind for ~400 turns would starve).
    world = unit.game_map
    chunk = world.chunks.get(chunk_key(unit.x, unit.y)) if world is not None else None
    foraged = elapsed > 2 * world.config.near_interval and chunk is not None and chunk.has_food()
    unit.hunger, hunger_damage = _bulk(unit.hunger, hunger_steps, unit.max_hunger if foraged else 0)
    unit.thirst, thirst_damage = _bulk(unit.thirst, thirst_steps, unit.max_thirst if foraged else 0)
    if (hunger_damage or thirst_damage) and unit.is_alive:       # (a unit left to starve or dehydrate dies of it)
        unit.last_harm = (None, None, "starvation" if hunger_damage else "thirst")
        unit.die(None, quiet=True)


def _bulk(value: int, steps: int, foraged_max: int) -> Tuple[int, int]:
    """Value and starvation damage after `steps` calls of `handle_*(-1)` (damage 1 per call at 0).

    With `foraged_max`, the value does not fall below half of it (or its current value, if lower) and causes no damage.
    """
    new = max(0, value - steps)
    if foraged_max:
        return max(new, min(value, foraged_max // 2)), 0
    return new, max(0, steps - max(value - 1, 0))


def _plant_upkeep(plant, last: int, now: int, elapsed: int) -> None:
    if not plant.fruit or plant.dead:
        return
    steps = steps_between(last, now, GROWTH_PERIOD)
    cycle = int(plant.avg_cycle) + 1  # a step completes the cycle once growth > avg_cycle
    cycles, plant.growth = divmod(plant.growth + steps, cycle)
    for _ in range(cycles):
        plant.complete_cycle()
    world = plant.parent
    if world is not None:
        world.plant_queue.schedule(plant, now)


class PlantQueue:
    """Plants do nothing between harvests, so instead of polling every plant every turn a world keeps the time of
    each plant's next completed growth cycle in a heap. `run(now)` brings only the due plants up to date.

    Entries are validated lazily when they pop (the plant must still be on this world with the same due time), so
    removed, unloaded or rescheduled plants need no cleanup. It is rebuilt from the plants themselves when a chunk
    is restored; nothing is saved.
    """

    def __init__(self, world) -> None:
        self.world = world
        self._heap: list = []
        self._counter = 0

    def __len__(self) -> int:
        return len(self._heap)

    def schedule(self, plant, now: int) -> None:
        if not plant.fruit or plant.dead:
            plant.due = None
            return
        plant.due = GROWTH_PERIOD * (now // GROWTH_PERIOD + plant.steps_to_harvest())
        self._counter += 1
        heappush(self._heap, (plant.due, self._counter, plant))

    def track(self, plant, now: int) -> None:
        """A plant joined the world: a new one starts its clock now, a restored one has been caught up already."""
        if plant.last_upkeep is None:
            plant.last_upkeep = now
        elif plant.last_upkeep < now:
            upkeep(plant, now)  # (re)loaded after an absence: catch up, which also schedules it
            return
        self.schedule(plant, now)

    def run(self, now: int) -> None:
        heap = self._heap
        while heap and heap[0][0] <= now:
            due, _, plant = heappop(heap)
            if plant.parent is not self.world or plant.due != due:
                continue
            upkeep(plant, now)  # reschedules


# ── the turn ───────────────────────────────────────────────────────────────────────
def run_turn(engine: Engine) -> None:
    """Simulate one turn after the player acted: ACTIVE actors fully, NEAR chunks on their interval."""
    world = engine.game_map
    config = engine.config
    now = engine.game_world.current_time
    player = engine.player
    center = world.center_key()
    active, near = [], []
    for key, chunk in world.chunks.items():
        distance = chebyshev(key, center)
        if distance <= config.active_radius:
            active.append(chunk)
        elif distance <= config.load_radius:
            near.append(chunk)

    world.plant_queue.run(now)
    import wildlife
    wildlife.tick(world, active + near, now)
    import decay
    decay.tick(world, active + near, now)
    import worldgen
    worldgen.regrow_flowers(world, active + near, now)

    for chunk in active:
        for entity in list(chunk.actors):  # snapshot: AIs may add/remove/move entities
            if entity is player or not entity.ai or entity.parent is not world:
                continue
            try:
                entity.ai.perform()
            except exceptions.Impossible:
                pass  # Ignore impossible action exceptions from AI.

    if config.near_interval > 0 and now % config.near_interval == 0:
        for chunk in near:
            for entity in list(chunk.actors):
                if entity is player or not entity.ai or entity.parent is not world:
                    continue
                near_step(engine, entity, now)


def near_step(engine: Engine, entity: Entity, now: int) -> None:
    """Upkeep plus one cheap step (`behavior.act(cheap=True)`) for an actor in a NEAR chunk."""
    upkeep(entity, now)
    if entity.category is not EntityCategory.UNIT or not entity.is_alive or not entity.ai:
        return
    import behavior
    try:
        behavior.act(entity, entity.ai, cheap=True)
    except exceptions.Impossible:
        pass
