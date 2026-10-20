"""Staying alive: cold and heat, bad air, and sleep.

Everything is deterministic and computed from the tile and the clock:

* **Temperature** (`effective_temperature`): the biome's ambient temperature (colder at night, constant underground, see
  `resources.ambient_temperature`) plus what keeps you warm: worn insulation, a lit fire within `FIRE_RADIUS`, being
  enclosed by walls, resting on a bed. Below `COMFORT` you chill (`unit.cold` counts up) and lose health at a rate that
  grows with the deficit; above `HEAT` you lose water faster. Warm up and the chill fades.
* **Bad air** (`gas_at`): pockets of foul gas in caves two or more levels down. You can hold your breath for the
  `breath_turns` stat (Selenites three times longer), then you suffocate until you leave.
* **Sleep** (`actions.SleepAction`): on a bed, heals, and in Casual mode saves your game.
"""
from __future__ import annotations

from typing import Optional, Tuple

import color
import resources
from seeds import mix_seed

COMFORT = 8.0
HEAT = 33.0
INSULATION_WARMTH = 1.5      # degrees per point of worn insulation (0..10)
FIRE_RADIUS = 3
FIRE_WARMTH = 14.0
TORCH_RADIUS = 2
TORCH_WARMTH = 4.0
SHELTER_WARMTH = 6.0
BED_WARMTH = 3.0
GAS_CELL = 6
GAS_CHANCE = 0.14
GAS_MIN_DEPTH = 2
SUFFOCATION_DAMAGE = 2


def worn_insulation(unit) -> float:
    armor = unit.equipment.armor if unit.equipment else None
    return float(getattr(armor, "insulation", 0.0)) if armor is not None else 0.0


def fire_warmth(world, x: int, y: int) -> float:
    """Warmth from the best lit fire in reach (a campfire is much warmer than a torch)."""
    from crafting import Campfire, Torch
    best = 0.0
    for dx in range(-FIRE_RADIUS, FIRE_RADIUS + 1):
        for dy in range(-FIRE_RADIUS, FIRE_RADIUS + 1):
            for thing in world.get_entities_at_location(x + dx, y + dy):
                if isinstance(thing, Campfire) and thing.is_placed and thing.emits_light:
                    near = max(abs(dx), abs(dy))
                    if isinstance(thing, Torch):
                        if near <= TORCH_RADIUS:
                            best = max(best, TORCH_WARMTH)
                    else:
                        best = max(best, FIRE_WARMTH)
    return best


def enclosure(world, x: int, y: int) -> float:
    """0..1: how much of the ring around (x, y) is solid (walls you built, rock). 6 of 8 counts as a shelter."""
    solid = 0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if not (dx or dy):
                continue
            if not world.is_walkable(x + dx, y + dy):
                solid += 1
    return solid / 8.0


def shelter_warmth(world, x: int, y: int) -> float:
    ring = enclosure(world, x, y)
    return SHELTER_WARMTH * min(1.0, ring / 0.75) if ring >= 0.5 else 0.0


def effective_temperature(engine, unit, sleeping: bool = False) -> float:
    world, gw = unit.game_map, engine.game_world
    ambient = resources.ambient_temperature(gw, world.z, unit.x, unit.y, gw.current_time)
    warmth = worn_insulation(unit) * INSULATION_WARMTH
    warmth += fire_warmth(world, unit.x, unit.y)
    warmth += shelter_warmth(world, unit.x, unit.y)
    if sleeping:
        warmth += BED_WARMTH
    if getattr(unit, "wet", 0) > 0:
        import liquids
        warmth -= liquids.WET_CHILL        # a wet body loses heat
    return ambient + warmth


def temperature_word(effective: float):
    """(label, colour) for the side panel: how the body feels at this effective temperature."""
    if effective < COMFORT - 15:
        return "Freezing", color.enemy_atk
    if effective < COMFORT:
        return "Cold", color.yellow
    if effective > HEAT:
        return "Hot", color.enemy_atk
    return "Fine", color.green


def status_lines(engine):
    """Side-panel lines for the player: [(text, colour)] for temperature, held breath, rescue countdown and credits."""
    unit, run = engine.player, engine.game_world.run
    lines = []
    label, shade = temperature_word(effective_temperature(engine, unit, sleeping=getattr(unit, "sleeping", False)))
    lines.append((label, shade))
    if getattr(unit, "wet", 0) > 0:
        lines.append(("Wet", color.light_blue))
    due = run.flags.get("rescue_due")
    if due is not None:
        lines.append((f"Rescue {max(0, due - engine.game_world.current_time)}", color.green))
    if run.sponsor:
        lines.append((f"{run.credits} cr", color.menu_text))
    return lines


def gas_at(master: int, z: int, x: int, y: int) -> bool:
    """Is (x, y) inside a pocket of bad air? Deterministic from the seed; only deep caves have them."""
    if z > -GAS_MIN_DEPTH:
        return False
    cell = mix_seed(master, z, x // GAS_CELL, y // GAS_CELL, 31)
    return (cell % 1000) / 1000.0 < GAS_CHANCE


def soak(unit, tile) -> None:
    """The player stepped onto `tile`: wading or swimming leaves them wet for a while."""
    import liquids
    if tile is None or not int(tile["liquid"]) or int(tile["liquid"]) == liquids.LiquidKind.LAVA:
        return
    unit.wet = max(unit.wet, liquids.WET_SWIM if liquids.swimmable(tile) else liquids.WET_SHALLOW)


def is_swimming(unit) -> bool:
    import liquids
    return unit.game_map is not None and liquids.swimmable(unit.game_map.tile_at(unit.x, unit.y))


def tick(engine, unit, turns: int = 1) -> None:
    """Apply `turns` turns of cold/heat and breathing to the player (called from `GameWorld.pass_time`)."""
    for _ in range(turns):
        if not unit.is_alive:
            return
        _temperature_turn(engine, unit)
        _breath_turn(engine, unit)
        _wet_turn(engine, unit)


def _say(engine, text: str, fg=color.impossible) -> None:
    engine.message_log.add_message(text, fg)


HEAT_THIRST_PERIOD = 15
"""Turns between the extra points of thirst the heat costs (the normal rate is `simulation.THIRST_PERIOD`)."""


def _temperature_turn(engine, unit) -> None:
    effective = effective_temperature(engine, unit, sleeping=getattr(unit, "sleeping", False))
    deficit = COMFORT - effective
    if deficit > 0:
        unit.cold += 1
        interval = max(2, 10 - int(deficit // 2))
        if unit.cold == 1:
            _say(engine, "You are cold. Find a fire or shelter, or wear something warmer.")
        if unit.cold % interval == 0:
            _say(engine, "The cold bites." if deficit < 15 else "You are freezing!", color.enemy_atk)
            unit.handle_health(-1, None, cause="the cold")
    else:
        unit.cold = max(0, unit.cold - 2)
    if effective > HEAT and engine.game_world.current_time % HEAT_THIRST_PERIOD == 0:
        unit.handle_thirst(-1)
        if engine.game_world.current_time % (HEAT_THIRST_PERIOD * 10) == 0:
            _say(engine, "The heat parches you.")


def _wet_turn(engine, unit) -> None:
    """Wetness dries off (three times as fast beside a fire) once you are out of the water."""
    if unit.wet <= 0:
        return
    if is_swimming(unit):
        return
    dry = 3 if fire_warmth(unit.game_map, unit.x, unit.y) > 0 else 1
    unit.wet = max(0, unit.wet - dry)
    if unit.wet == 0:
        _say(engine, "You have dried off.", color.green)


def _breath_turn(engine, unit) -> None:
    world = unit.game_map
    capacity = unit.capabilities.stat("breath_turns")
    in_gas = gas_at(engine.game_world.master_seed, world.z, unit.x, unit.y)
    diving = is_swimming(unit)
    if in_gas or diving:
        if unit.breath is None:
            unit.breath = capacity
            _say(engine, "You take a breath and go under." if diving else "The air here is thick and foul. You hold your breath.")
        unit.breath -= 1
        if unit.breath <= 0:
            _say(engine, "You are drowning!" if diving else "You choke on the foul air!", color.enemy_atk)
            unit.handle_health(-SUFFOCATION_DAMAGE, None, cause="suffocation")
    elif unit.breath is not None:
        unit.breath = min(capacity, unit.breath + 2)
        if unit.breath >= capacity:
            unit.breath = None
