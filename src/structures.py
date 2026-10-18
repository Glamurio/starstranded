"""Places on the map: the crash site (ship, wreckage, cargo pod) and the precursor ruins and gate.

Structures are entities that block movement and are *used* (`F`): `interact(user, engine)` does the work and may return an
input handler to open (the cargo pod's contract screen). Their positions are deterministic: the crash site is laid out
around the spawn point, the ruins in chunks picked from the planet seed.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

import color
import exceptions
import species as defs
from entity import Entity
from knowledge import Fact, Know
from seeds import mix_seed
from skills import Skill

SHIP_NEEDS: Tuple[Tuple[str, str, int], ...] = (
    ("hull_plate", "hull plates", 4), ("nav_unit", "navigation unit", 1), ("power_cell", "power cell", 1))
"""What the ship needs before it can fly: (item kind key, label, count)."""
FLY_ENGINEERING = 4
RUIN_COUNT = 3
RUIN_DIFFICULTY = (3, 3, 4)
STUDY_COOLDOWN = 60       # turns between study sessions that can teach
EXCAVATE_TURNS = (6, 2)   # by hand, with a digging tool

WRECK_LOOT: Tuple[Tuple[Tuple[str, int], ...], ...] = (
    (("ration", 2), ("medkit", 1)),
    (("hull_plate", 2),),
    (("circuit", 1), ("wire", 2), ("lens", 1)),
    (("ration", 2), ("ammo", 1)),
    (("ingot", 3), ("wire", 1)),
    (("medkit", 1), ("cloth", 2)),
)
WRECK_NAMES = ("cargo section", "hull section", "avionics rack", "galley wreck", "engine nacelle", "crew pod")


class Structure(Entity):
    object_type = "Structure"

    def __init__(self, kind: defs.ItemKind):
        Entity.__init__(self, kind)
        self.color = self.shade = kind.color
        self.blocks_movement = True

    def interact(self, user, engine):
        raise exceptions.Impossible("Nothing happens.")

    def resistances(self):
        return ()


# ── the crash site ─────────────────────────────────────────────────────────────────────────────────────────────
class Ship(Structure):
    object_type = "Ship"

    def __init__(self):
        Structure.__init__(self, defs.SHIP)

    def get_title(self, exclude_attributes: bool = False) -> str:
        return "crashed shuttle"

    def interact(self, user, engine):
        run = engine.game_world.run
        lines = ship_status(user, run)
        installed = run.flags.setdefault("ship", {})
        log = engine.message_log
        put_in = []
        for key, label, count in SHIP_NEEDS:
            need = count - installed.get(key, 0)
            for item in [i for i in user.inventory.items if getattr(getattr(i, "kind", None), "key", None) == key][:max(0, need)]:
                user.inventory.remove(item)
                installed[key] = installed.get(key, 0) + 1
                put_in.append(label)
        if put_in:
            log.add_message(f"You fit {', '.join(sorted(set(put_in)))} into the ship.", color.orange)
            engine.game_world.pass_time(unit=user, time=2 * len(put_in))
        lines = ship_status(user, run)
        for ok, text in lines:
            log.add_message(("[+] " if ok else "[ ] ") + text, color.white if ok else color.impossible)
        if all(ok for ok, _ in lines):
            import endings
            endings.finish(engine, "repair_flight")
        elif not put_in:
            raise exceptions.Impossible("The ship is not ready to fly.")


def can_fly(user) -> bool:
    caps = user.capabilities
    return caps.has("pilot_training") or user.skills.level(Skill.ENGINEERING) >= FLY_ENGINEERING


def ship_status(user, run) -> List[Tuple[bool, str]]:
    installed = run.flags.get("ship", {})
    lines = [(installed.get(key, 0) >= count, f"{label}: {installed.get(key, 0)}/{count} fitted") for key, label, count in SHIP_NEEDS]
    lines.append((can_fly(user), "someone who can fly her: pilot training or Engineering 4"))
    return lines


class Wreckage(Structure):
    object_type = "Wreckage"

    def __init__(self, index: int):
        Structure.__init__(self, defs.WRECKAGE)
        self.index = index % len(WRECK_LOOT)
        self.stripped = False

    def get_title(self, exclude_attributes: bool = False) -> str:
        return WRECK_NAMES[self.index] + (" (stripped)" if self.stripped else "")

    def interact(self, user, engine):
        import characters
        import crafting
        import items as items_module
        if self.stripped:
            raise exceptions.Impossible("There is nothing left to take.")
        tags = set(crafting.unit_tags(user))
        if not ("salvaging" in tags or {"hammering", "cutting"} <= tags):
            raise exceptions.Impossible("You need a salvage tool, or a hammer and a knife, to take this apart.")
        stat = user.capabilities.stat("salvage_yield")
        made = []
        for key, count in WRECK_LOOT[self.index]:
            for _ in range(max(1, int(count * stat + 0.5))):
                made.append(salvage_piece(key, user))
        if len(user.inventory.items) + len(made) > user.inventory.capacity:
            raise exceptions.Impossible("Your inventory would be full.")
        for item in made:
            user.inventory.add(item)
        self.stripped = True
        self.blocks_movement = False
        self.color = self.shade = (90, 90, 100)
        user.practice(Skill.ENGINEERING, 1)
        engine.message_log.add_message(f"You strip the {WRECK_NAMES[self.index].lower()}: " +
                                       ", ".join(sorted({i.get_title() for i in made})) + ".", color.orange)
        engine.game_world.pass_time(unit=user, time=3)


def salvage_piece(key: str, user):
    """One recovered part, built like the crafted equivalent from standard-issue stuff."""
    import characters
    import species as d
    from components.consumable import Ration
    from items import Ammo, Made, Stuff
    inv = user.inventory
    if key == "ration":
        return Ration(inv)
    if key == "ammo":
        return Ammo(inv, 6)
    if key == "wire":
        return Stuff(d.PIECE_WIRE, characters.ISSUE_STEEL.replace(id="issue:wire", name="drawn wire"), inv)
    if key == "ingot":
        return Stuff(d.PIECE_INGOT, characters.ISSUE_STEEL, inv)
    if key == "cloth":
        return Stuff(d.PIECE_FIBER, characters.ISSUE_CLOTH, inv)
    kinds = {"medkit": d.MEDKIT, "hull_plate": d.HULL_PLATE, "circuit": d.CIRCUIT, "lens": d.LENS}
    parts = {"medkit": {"bandage": characters.ISSUE_CLOTH, "vial": characters.ISSUE_GLASS},
             "hull_plate": {"plate": characters.ISSUE_STEEL}, "circuit": {"traces": characters.ISSUE_CIRCUIT},
             "lens": {"glass": characters.ISSUE_GLASS}}[key]
    return Made(kinds[key], parts, 1.0, key, {}, {}, next(iter(parts)), parent=inv)


class CargoPod(Structure):
    """The sponsor's supply pod beside the wreck: hand in contracts, buy supplies."""
    object_type = "Cargo pod"

    def __init__(self):
        Structure.__init__(self, defs.CARGO_POD)

    def get_title(self, exclude_attributes: bool = False) -> str:
        return "sponsor cargo pod"

    def interact(self, user, engine):
        import input_handlers
        return input_handlers.PodHandler(engine)


# ── the precursors ─────────────────────────────────────────────────────────────────────────────────────────────
INSCRIPTIONS = (
    "Three keys wake the door; one for each who built it.",
    "The first key sleeps where the sun is last to leave.",
    "Bring them together, and the door will open on the road between the stars.",
)


def inscription_fact(index: int) -> Fact:
    return Fact("inscription", Skill.LINGUISTICS, RUIN_DIFFICULTY[index % RUIN_COUNT], INSCRIPTIONS[index % RUIN_COUNT],
                hint="Strange glyphs; a pattern repeats.", capability="universal_translator")


class Ruin(Structure):
    object_type = "Ruin"

    def __init__(self, index: int):
        Structure.__init__(self, defs.RUIN)
        self.index = index
        self.relic_taken = False
        self.studied_at = -STUDY_COOLDOWN   # glyph study only teaches once per cooldown, so it cannot be ground at the stone
        self.color = self.shade = (170, 200, 190)

    def get_title(self, exclude_attributes: bool = False) -> str:
        return f"Precursor ruin {self.index + 1}"

    @property
    def subject(self) -> str:
        return f"ruin:{self.index}"

    def interact(self, user, engine):
        from items import Artifact
        run = engine.game_world.run
        log = engine.message_log
        fact = inscription_fact(self.index)
        learned = run.knowledge.scan(self.subject, [fact], user.skills, user.capabilities)
        level = run.knowledge.level(self.subject, "inscription")
        if level is Know.FULL:
            if learned:
                log.add_message(f"You read the inscription: \"{fact.value}\"", color.orange)
        else:
            now = engine.game_world.current_time
            if now - self.studied_at >= STUDY_COOLDOWN and user.practice(Skill.LINGUISTICS, 1):
                log.add_message("Something clicks: you read the glyphs better now.", color.orange)
            if now - self.studied_at >= STUDY_COOLDOWN:
                self.studied_at = now
            log.add_message("You puzzle over the glyphs." + ("" if level is Know.UNKNOWN else " The sense is almost there."))
        if not self.relic_taken:
            digging = "digging" in __import__("crafting").unit_tags(user)
            if len(user.inventory.contents) + 2 > user.inventory.capacity:
                raise exceptions.Impossible("You need room for two finds in your inventory.")
            self.relic_taken = True
            user.inventory.add(Artifact(user.inventory, f"Precursor key {self.index + 1}", self.index, is_key=True))
            user.inventory.add(Artifact(user.inventory, "Precursor curio", self.index))
            log.add_message("You dig a humming key and a carved curio out of the rubble.", color.orange)
            engine.game_world.pass_time(unit=user, time=EXCAVATE_TURNS[1 if digging else 0])
        else:
            engine.game_world.pass_time(unit=user, time=5)


class Gate(Structure):
    object_type = "Gate"

    def __init__(self):
        Structure.__init__(self, defs.GATE)

    def get_title(self, exclude_attributes: bool = False) -> str:
        return "Precursor gate"

    def interact(self, user, engine):
        from items import Artifact
        run = engine.game_world.run
        log = engine.message_log
        keys = {a.index for a in user.inventory.items if isinstance(a, Artifact) and a.is_key}
        read = [i for i in range(RUIN_COUNT) if run.knowledge.level(f"ruin:{i}", "inscription") is Know.FULL]
        lines = [(len(keys) >= RUIN_COUNT, f"keys: {len(keys)}/{RUIN_COUNT}"),
                 (len(read) >= RUIN_COUNT, f"inscriptions read: {len(read)}/{RUIN_COUNT}")]
        for ok, text in lines:
            log.add_message(("[+] " if ok else "[ ] ") + text, color.white if ok else color.impossible)
        if not all(ok for ok, _ in lines):
            raise exceptions.Impossible("The gate stays dark.")
        import endings
        endings.finish(engine, "ancient_gate")


# ── layout ─────────────────────────────────────────────────────────────────────────────────────────────────────
RUIN_RING = [(dx, dy) for dx in range(-3, 4) for dy in range(-2, 3) if max(abs(dx), abs(dy)) >= 2]


def ruin_chunks(master: int) -> Dict[Tuple[int, int], int]:
    """Chunk key -> site index (0..2 ruins, 3 the gate), chosen from the seed."""
    rng = random.Random(mix_seed(master, 909))
    picks = rng.sample(RUIN_RING, RUIN_COUNT + 1)
    return {pick: index for index, pick in enumerate(picks)}


def _free(world, x, y) -> bool:
    if not world.in_bounds(x, y) or not world.is_walkable(x, y) or world.is_blocked(x, y):
        return False
    tile = world.tile_at(x, y)
    return not int(tile["liquid"]) and not [e for e in world.get_entities_at_location(x, y) if e.blocks_movement]


def _roomy(world, x, y) -> bool:
    """A site needs room around it to stand next to (and not to be walled in by trees or water)."""
    return sum(_free(world, x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy) >= 4


def free_tile_near(world, x: int, y: int, rng, radius_min: int = 0, radius_max: int = 12, taken=()):
    cells = [(x + dx, y + dy) for dx in range(-radius_max, radius_max + 1) for dy in range(-radius_max, radius_max + 1)
             if radius_min <= max(abs(dx), abs(dy)) <= radius_max]
    rng.shuffle(cells)
    for cx, cy in cells:
        if (cx, cy) not in taken and _free(world, cx, cy) and _roomy(world, cx, cy):
            return cx, cy
    return None


def place_crash_site(world, spawn: Tuple[int, int], master: int) -> Dict[str, Tuple[int, int]]:
    """Ship, cargo pod and wreckage around the spawn point: the ship 4-6 tiles away, the pod beside it, pieces scattered."""
    rng = random.Random(mix_seed(master, 808))
    taken = {spawn}
    sx, sy = spawn
    ship_at = free_tile_near(world, sx, sy, rng, 4, 6, taken) or free_tile_near(world, sx, sy, rng, 2, 14, taken)
    placed: Dict[str, Tuple[int, int]] = {}
    if ship_at is None:
        return placed
    taken.add(ship_at)
    world.add_entity(Ship(), *ship_at)
    placed["ship"] = ship_at
    pod_at = free_tile_near(world, ship_at[0], ship_at[1], rng, 2, 3, taken) or free_tile_near(world, sx, sy, rng, 2, 14, taken)
    if pod_at:
        taken.add(pod_at)
        world.add_entity(CargoPod(), *pod_at)
        placed["pod"] = pod_at
    for index in range(len(WRECK_LOOT)):
        at = free_tile_near(world, ship_at[0], ship_at[1], rng, 2, 8, taken)
        if at is None:
            continue
        taken.add(at)
        world.add_entity(Wreckage(index), *at)
    return placed


def place_ruin(world, chunk, master: int, index: int):
    rng = random.Random(mix_seed(master, 707, index))
    cx, cy = chunk.x0 + 35, chunk.y0 + 20
    at = free_tile_near(world, cx, cy, rng, 0, 14)
    if at is None:
        at = (cx, cy)
        world.modify_tile(cx, cy, walkable=True, transparent=True)
    world.add_entity(Gate() if index >= RUIN_COUNT else Ruin(index), *at)
    return at
