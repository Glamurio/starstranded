"""Ways the run ends: three escapes (repair the ship, corporate rescue, the precursor gate) with several endings, and death.

`finish(engine, key)` records the ending on the run state; the input handler notices `run.ending` after the action and
shows `epilogue(...)`. The rescue is two steps: build a beacon (`recipes`: "beacon") and use it once your sponsor trusts you
(`sponsors.rescue_ready`); the ship arrives `RESCUE_DELAY` turns later and you must survive until it does.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import exceptions
import sponsors

RESCUE_DELAY = 60


@dataclass(frozen=True)
class Ending:
    key: str
    title: str
    text: str
    victory: bool = True


ENDINGS: Dict[str, Ending] = {e.key: e for e in (
    Ending("repair_flight", "Under Your Own Power",
           "The hull holds, the nav unit hums, and the old drives catch on the third try. Nobody sent for you. You lift out of "
           "the crater yourself, owing the sector nothing, and set a course for anywhere with a harbour."),
    Ending("rescue_agricultural_monopoly", "Harvest Contract",
           "The Monopoly's seed freighter drops through the clouds, hold open. They sign you on as a field surveyor before the "
           "ramp is up: the next planet needs someone who has already starved on one."),
    Ending("rescue_heavy_industries", "Priority Cargo",
           "A Heavy Industries tug docks with the beacon, and the foreman reads out your delivery record like a debt "
           "settled in iron. You leave on a shift roster; the planet's ore goes with you in the hold."),
    Ending("rescue_relic_collectors", "A Collector's Guest",
           "The Collectors send a yacht, all brass and velvet. You are the best field agent they never hired, and they "
           "want you alive to ask about every relic you did not sell them."),
    Ending("rescue_retail_megacorp", "Brand Ambassador",
           "The Megacorp's rescue ship has a gift shop. By the time you reach orbit your survival story has a sponsor, a "
           "slogan, and a merchandise line."),
    Ending("rescue_government_agency", "Official Inquiry",
           "A Government cutter picks you up and begins the paperwork at once. Your catalogue entries open a new colony "
           "survey; your testimony opens three inquiries."),
    Ending("ancient_gate", "The Door Between Stars",
           "The three keys sing; the gate unfolds into a road of light. You step through carrying only what you learned "
           "to read, and the planet that tried to kill you falls away behind a door that closes on its own."),
    Ending("death", "Left Behind",
           "The planet keeps what it takes. Somewhere above, a corporate ledger marks the crash site 'no survivors' and "
           "moves on to the next quarter.", victory=False),
)}


def finish(engine, key: str) -> None:
    """Record the ending; the input handler shows it once the action that caused it returns."""
    engine.game_world.run.ending = key


def rescue_ending_key(run) -> str:
    return f"rescue_{run.sponsor}"


def activate_beacon(user, item):
    """Use a beacon: if the sponsor trusts you enough the rescue ship is called (arrives in `RESCUE_DELAY` turns)."""
    engine = user.engine
    run = engine.game_world.run
    if run.flags.get("rescue_due") is not None:
        raise exceptions.Impossible("The beacon is already broadcasting. Survive until the ship arrives.")
    if not run.sponsor:
        raise exceptions.Impossible("You have no sponsor to answer a beacon.")
    spec = sponsors.SPONSORS[run.sponsor]
    if not sponsors.rescue_ready(run):
        done = sum(1 for c in run.completed if c.startswith(run.sponsor + ":"))
        raise exceptions.Impossible(
            f"{spec.name} does not answer yet: reputation {run.reputation.get(run.sponsor, 0)}/{sponsors.RESCUE_REPUTATION}, "
            f"contracts finished {done}/{sponsors.RESCUE_CONTRACTS}.")
    user.inventory.remove(item)
    run.flags["rescue_due"] = engine.game_world.current_time + RESCUE_DELAY
    engine.message_log.add_message(
        f"{spec.name} acknowledges. A ship is on its way: hold out for {RESCUE_DELAY} turns.", (255, 200, 120))
    return None


def tick(engine) -> None:
    """Called after every player turn: a called-in rescue arrives when due."""
    run = engine.game_world.run
    due = run.flags.get("rescue_due")
    if due is not None and run.ending is None and engine.game_world.current_time >= due:
        finish(engine, rescue_ending_key(run))


def epilogue(engine) -> List[str]:
    """The ending text plus what the run looked like (derived from the run state, so every ending reads differently)."""
    run = engine.game_world.run
    ending = ENDINGS[run.ending]
    player = engine.player
    lines = [ending.title, "", ending.text, ""]
    from clock import days_survived
    lines.append(f"{player.name}, a {player.kind.name} {player.background or 'castaway'}: survived {days_survived(engine)} day{'s' if days_survived(engine) != 1 else ''}.")
    done = len(run.completed)
    if done:
        lines.append(f"Contracts completed: {done}. Credits held: {run.credits}.")
    import sponsors as s
    known = s.knowledge_count(run)
    if known:
        lines.append(f"Catalogue entries: {known}.")
    allies = [s_.name for key, s_ in s.SPONSORS.items() if run.reputation.get(key, 0) >= s.RESCUE_REPUTATION]
    if len(allies) > 1:
        lines.append("Several sponsors would have taken you: " + ", ".join(allies) + ".")
    if run.mode == "casual":
        lines.append("Mode: Casual.")
    return lines
