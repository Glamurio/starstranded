"""What a creature does on its turn: one decision routine shared by every tier of the simulation.

Order of priority:

1. **Flee** from a living creature that hunts my kind (see `preys_on`).
2. **Hostile creatures** chase and attack the nearest creature of an enemy faction (`allegiance`) that they can see - the player is only
   one of them. Out of sight they head for where they last saw it for a few turns (`MEMORY_TURNS`), then give up.
3. **Needs:** hungry or thirsty -> eat what I carry -> look for food (ground food, carrion, fruiting plants and, for
   meat eaters, live prey) -> approach it -> eat it / attack it.
4. Otherwise idle: keep walking a wander path, or wait.

`cheap=True` is the NEAR-tier version (no pathfinding: greedy steps, no walking paths); the decisions and the
interactions (eating, attacking) are the same code, so a rabbit in a chunk you cannot see still gets hunted.
"""
from __future__ import annotations

import random
from typing import Optional, Tuple, TYPE_CHECKING

import exceptions
from entity import EntityCategory
from species import Diet

if TYPE_CHECKING:
    from components.ai import BaseAI
    from entity import Entity, Unit

SEEK_THRESHOLD = 90
"""Creatures look for food at or below this hunger/thirst (of 100)."""
FLEE_SIGHT = 4
"""How far away a creature notices something that hunts it."""
SIGHT = 12
"""How far a hostile creature sees, as `engine.can_see` counts it (that subtracts 2: ten tiles). It needs a clear line, so walls and
trees hide you."""
MEMORY_TURNS = 15
"""How many turns a hostile keeps heading for the place it last saw its target before it gives up."""
FOLLOW_RANGE = 8
"""Hostiles this close to the player when he takes stairs follow him to the other layer."""
STAIRS_CHANCE = 0.04
"""Chance per turn that an idle creature standing on a staircase uses it."""

DIRECTIONS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


# ── relations ──────────────────────────────────────────────────────────────────────
def is_hungry(unit: Unit) -> bool:
    return unit.hunger <= SEEK_THRESHOLD or unit.thirst <= SEEK_THRESHOLD


def ignores_player(unit: Entity, other: Entity) -> bool:
    """God Mode: no creature notices, hunts or flees from the player."""
    import debug
    engine = getattr(unit, "engine", None)
    return other is getattr(engine, "player", None) and debug.is_god(engine)


def preys_on(hunter: Entity, other: Entity) -> bool:
    """Does `hunter` hunt `other`? Meat eaters (carnivores and omnivores, the player included) hunt living
    herbivores."""
    if ignores_player(hunter, other):
        return False
    return (other is not hunter and other.category is EntityCategory.UNIT and other.is_alive
            and hunter.category is EntityCategory.UNIT and hunter.is_alive
            and hunter.diet in (Diet.CARNIVORE, Diet.OMNIVORE) and other.diet is Diet.HERBIVORE)


def edible_in(unit: Unit, source: Entity) -> Optional[Entity]:
    """The food `unit` can eat that is `source` itself (ground food) or inside it (a corpse, a fruiting plant)."""
    from components.consumable import FoodConsumable
    if isinstance(source, FoodConsumable):
        return source if unit.can_eat(source) else None
    inventory = getattr(source, "inventory", None)
    if inventory is None or not (source.category is EntityCategory.PLANT or not getattr(source, "is_alive", True)):
        return None
    return next((i for i in inventory.items if isinstance(i, FoodConsumable) and unit.can_eat(i)), None)


# ── perception ─────────────────────────────────────────────────────────────────────
def hunters(world) -> list:
    """The meat eaters on `world` (the player included), cached until an entity is added or removed."""
    stamp = world.entity_version
    cached = getattr(world, "_hunters", None)
    if cached is None or cached[0] != stamp:
        cached = (stamp, [u for u in world.units if u.diet is not Diet.HERBIVORE])
        world._hunters = cached
    return cached[1]


def find_threat(unit: Unit, radius: int = FLEE_SIGHT) -> Optional[Entity]:
    """A living creature within `radius` that hunts `unit`'s kind (looked up among the few hunters, not by scanning)."""
    x, y = unit.x, unit.y
    for other in hunters(unit.game_map):
        if abs(other.x - x) <= radius and abs(other.y - y) <= radius and preys_on(other, unit):
            return other
    return None


def find_food(unit: Unit, radius: int) -> Optional[Tuple[Entity, str]]:
    """Nearest (ring by ring) thing to eat: `(entity, kind)` with kind "item" / "corpse" / "plant" / "prey"."""
    world = unit.game_map
    for r in range(0, radius + 1):
        for other in world.entities_on_ring(unit.x, unit.y, r):
            if other is unit:
                continue
            category = other.category
            if category is EntityCategory.UNIT:
                if preys_on(unit, other):
                    return other, "prey"
                if not other.is_alive and edible_in(unit, other):
                    return other, "corpse"
            elif category is EntityCategory.PLANT:
                if not other.dead and edible_in(unit, other):
                    return other, "plant"
            elif edible_in(unit, other):
                return other, "item"
    return None


# ── the decision ───────────────────────────────────────────────────────────────────
def act(unit: Unit, ai: BaseAI, cheap: bool = False) -> None:
    """One turn of `unit` (already upkept). May raise `exceptions.Impossible` (a blocked step; callers ignore it)."""
    engine = ai.engine

    if not ai.is_hostile and _answer_attacker(unit, ai, cheap):
        return

    if unit.diet is Diet.HERBIVORE or unit.diet is Diet.OMNIVORE:
        threat = find_threat(unit)
        if threat is not None and not ai.is_hostile:
            return _flee(unit, ai, threat, cheap)

    if ai.is_hostile and _hunt(unit, ai, cheap):
        return

    thirsty = unit.thirst <= SEEK_THRESHOLD and unit.thirst <= unit.hunger
    if thirsty and _drink(unit, ai, cheap):
        return

    if is_hungry(unit) and _feed(unit, ai, cheap):
        return

    if ai.is_hostile and _search(unit, ai, cheap):
        return

    if not ai.is_hostile and use_stairs(unit):
        return

    _idle(unit, ai, cheap)


GRUDGE_RANGE = 12
"""A peaceful creature stops running from whoever hurt it once it is this far away."""


def _answer_attacker(unit, ai, cheap) -> bool:
    """A peaceful creature that was hurt hits back when its attacker is next to it, and runs from it otherwise."""
    from actions import MeleeAction
    attacker = getattr(ai, "grudge", None)
    if attacker is None:
        return False
    gap = max(abs(attacker.x - unit.x), abs(attacker.y - unit.y))
    if not attacker.is_alive or gap > GRUDGE_RANGE or attacker.game_map is not unit.game_map or ignores_player(unit, attacker):
        ai.grudge = None
        return False
    if gap <= 1 and unit.power > 0:
        MeleeAction(unit, attacker.x, attacker.y).perform()
        return True
    _flee(unit, ai, attacker, cheap)
    return True


def use_stairs(unit) -> bool:
    """An idle creature on a staircase sometimes takes it. True if it did."""
    world = unit.game_map
    tile = world.tile_at(unit.x, unit.y)
    if tile is None or not int(tile["stairs"]) or random.random() > STAIRS_CHANCE:
        return False
    game_world = world.engine.game_world
    game_world.send(unit, world.z + int(tile["stairs"]))
    return True


def _flee(unit, ai, threat, cheap):
    if cheap:
        step_towards(ai.engine, unit, threat.x, threat.y, away=True)
    elif ai.path and _gap(ai.path[-1], threat) > _gap((unit.x, unit.y), threat):
        _walk(unit, ai)  # keep running to the spot already chosen: it is farther from the threat than I am
    else:
        ai.flee(threat, unit.radius)


def _gap(point, other) -> int:
    return max(abs(point[0] - other.x), abs(point[1] - other.y))


def find_enemy(unit) -> Optional[Entity]:
    """The nearest creature that `unit` would attack (by faction) and can see, or None."""
    import allegiance
    engine = unit.game_map.engine
    best = None
    for other in unit.game_map.units:
        if other is unit or not other.is_alive:
            continue
        gap = max(abs(other.x - unit.x), abs(other.y - unit.y))
        if gap > SIGHT - 2 or (best is not None and gap >= best[0]):
            continue
        if ignores_player(unit, other) or not allegiance.will_attack(unit, other):
            continue
        if engine.can_see(unit.x, unit.y, other.x, other.y, SIGHT):
            best = (gap, other)
    return None if best is None else best[1]


def _hunt(unit, ai, cheap) -> bool:
    """Go for an enemy in sight (and remember where it was). False when there is none."""
    target = find_enemy(unit)
    if target is None:
        return False
    ai.memory = [target.x, target.y, MEMORY_TURNS]
    return _pursue(unit, ai, cheap, target.x, target.y, target)


def _search(unit, ai, cheap) -> bool:
    """Head for the place an enemy was last seen; forget it on arrival or when the memory runs out."""
    memory = getattr(ai, "memory", None)
    if not memory:
        return False
    x, y, turns = memory
    if turns <= 0 or max(abs(x - unit.x), abs(y - unit.y)) <= 1:
        ai.memory = None
        ai.path = []
        return False
    memory[2] -= 1
    return _pursue(unit, ai, cheap, x, y, None)


def _pursue(unit, ai, cheap, x: int, y: int, target: Optional[Entity]) -> bool:
    """One turn of closing in on (x, y): hit `target` when next to it, else walk (planned path, or greedy steps with a planned detour
    when stuck)."""
    from actions import MeleeAction
    engine = ai.engine
    distance = max(abs(x - unit.x), abs(y - unit.y))
    if target is not None and distance <= 1:
        MeleeAction(unit, target.x, target.y).perform()
        return True
    end = ai.path[-1] if ai.path else None
    needs_plan = end is None or max(abs(end[0] - x), abs(end[1] - y)) > 2
    if not cheap:
        if needs_plan:
            ai.path = ai.get_path(x, y)
        if ai.path:
            _walk(unit, ai)
            return True
    elif ai.path and not needs_plan:
        try:
            _walk(unit, ai)
            return True
        except exceptions.Impossible:
            pass
    # Greedy steps; two without progress mean an obstacle (a lake, a wall): plan a real path round it.
    step_towards(engine, unit, x, y)
    after = max(abs(x - unit.x), abs(y - unit.y))
    ai.stuck = 0 if after < distance else getattr(ai, "stuck", 0) + 1
    if ai.stuck >= 2:
        ai.stuck = 0
        ai.path = ai.get_path(x, y)
    return True


def _feed(unit, ai, cheap) -> bool:
    """Eat from the inventory, or find food and go for it. False if there is nothing to be done about hunger."""
    from actions import MeleeAction

    carried = next((i for i in unit.inventory.items if unit.can_eat(i) and hasattr(i, "consume")), None)
    if carried is not None:
        _announce(unit, f"{unit.get_title()} has eaten the {carried.get_title()}.")
        carried.consume(unit)
        return True

    found = find_food(unit, unit.radius)
    if found is None:
        return False
    target, kind = found
    adjacent = max(abs(target.x - unit.x), abs(target.y - unit.y)) <= 1

    if adjacent:
        if kind == "prey":
            MeleeAction(unit, target.x, target.y).perform()
            return True
        food = edible_in(unit, target)
        if food is None:  # eaten by someone else in the meantime
            return False
        unit.inventory.loot(food)
        _announce(unit, f"{unit.get_title()} begins eating the {food.get_title()}.")
        if cheap:
            food.consume(unit)
        return True

    if cheap:
        step_towards(ai.engine, unit, target.x, target.y)
        return True
    destination = _approach_tile(unit, target, kind)
    if destination is None:
        return False
    end = ai.path[-1] if ai.path else None
    if end is None or max(abs(end[0] - destination[0]), abs(end[1] - destination[1])) > (1 if kind == "prey" else 0):
        ai.path = ai.get_path(*destination)
    if not ai.path:
        return False
    _walk(unit, ai)
    return True


def find_liquid(unit: Unit, radius: int) -> Optional[Tuple[int, int]]:
    """The closest drinkable (impure, never toxic or acidic) liquid tile within `radius`, or None."""
    import liquids
    world = unit.game_map
    best = None
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            tile = world.tile_at(unit.x + dx, unit.y + dy)
            if tile is None or int(tile["liquid"]) != int(liquids.LiquidKind.IMPURE):
                continue
            d = max(abs(dx), abs(dy))
            if best is None or d < best[0]:
                best = (d, unit.x + dx, unit.y + dy)
    return None if best is None else best[1:]


def _drink(unit, ai, cheap) -> bool:
    """Go to the nearest drinkable liquid and drink. False if there is none in reach."""
    import liquids
    found = find_liquid(unit, min(unit.radius, 24))
    if found is None:
        return False
    lx, ly = found
    if max(abs(lx - unit.x), abs(ly - unit.y)) <= 1:
        unit.handle_thirst(liquids.SIP_THIRST)
        return True
    if cheap:
        step_towards(ai.engine, unit, lx, ly)
        return True
    engine = ai.engine
    options = [t for t in engine.get_adjacent_tiles(lx, ly) if engine.can_move(*t)]
    if not options:
        return False
    destination = engine.get_closest_tile(options, unit.x, unit.y)
    if not ai.path or ai.path[-1] != destination:
        ai.path = ai.get_path(*destination)
    if not ai.path:
        return False
    _walk(unit, ai)
    return True


def _approach_tile(unit, target, kind) -> Optional[Tuple[int, int]]:
    """Where to walk to: onto ground food, next to anything that blocks (trees, creatures, corpses)."""
    world = unit.game_map
    if kind == "item" or (target.category is not EntityCategory.PLANT and not target.blocks_movement):
        return target.x, target.y
    engine = world.engine
    options = [t for t in engine.get_adjacent_tiles(target.x, target.y) if engine.can_move(*t)]
    if not options:
        return None
    return engine.get_closest_tile(options, unit.x, unit.y)


def _idle(unit, ai, cheap) -> None:
    from actions import WaitAction
    if cheap:
        if random.getrandbits(1):
            random_step(ai.engine, unit)
        return
    if ai.path:
        _walk(unit, ai)
    elif random.getrandbits(1):
        WaitAction(unit).perform()
    else:
        ai.wander()


def _walk(unit, ai) -> None:
    """Take the next step of `ai.path`; a blocked step drops the path (and is reported to the caller)."""
    from actions import MovementAction
    try:
        MovementAction(unit, *ai.path[-1], ai.path).perform()
    except exceptions.Impossible:
        ai.path = []
        raise


def _announce(unit, text: str) -> None:
    """Log what a creature does, but only if the player can see it."""
    engine = unit.game_map.engine
    player = engine.player
    if player is not None and engine.can_see(player.x, player.y, unit.x, unit.y, player.radius):
        engine.message_log.add_message(text)


# ── greedy movement (NEAR tier, no pathfinding) ───────────────────────────────────
def free_step(engine, x: int, y: int) -> bool:
    """Can a creature step onto (x, y)? Creatures know better than to wade through acid (the player does not)."""
    if not engine.can_move(x, y):
        return False
    tile = engine.game_map.tile_at(x, y)
    return tile is None or int(tile["liquid"]) != 3


def random_step(engine, unit) -> None:
    dx, dy = random.choice(DIRECTIONS)
    if free_step(engine, unit.x + dx, unit.y + dy):
        unit.move(unit.x + dx, unit.y + dy)


def step_towards(engine, unit, x: int, y: int, away: bool = False) -> None:
    """Greedy step: the free neighbouring tile that most reduces (or, `away`, increases) the Chebyshev distance.

    With no such tile (an obstacle in the way) it sidesteps to a random free tile that does not make things worse,
    so creatures work their way around trees and walls instead of standing still.
    """
    best = None
    sideways = []
    current = max(abs(x - unit.x), abs(y - unit.y))
    for dx, dy in DIRECTIONS:
        nx, ny = unit.x + dx, unit.y + dy
        if not free_step(engine, nx, ny):
            continue
        distance = max(abs(x - nx), abs(y - ny))
        better = distance > current if away else distance < current
        if better:
            score = -distance if away else distance
            if best is None or score < best[0]:
                best = (score, nx, ny)
        elif distance == current:
            sideways.append((nx, ny))
    if best is not None:
        unit.move(best[1], best[2])
    elif sideways:
        unit.move(*random.choice(sideways))
    else:
        random_step(engine, unit)
