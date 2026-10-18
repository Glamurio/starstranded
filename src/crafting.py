"""Crafting: recipes are lists of *needs* (a role, the forms of piece that fit it, and property thresholds), plus the tools,
station, skill, heat and time the job takes. Nothing is a fixed ingredient list: whatever you carry whose material meets the
thresholds can fill a role, and the thing you build derives its own properties from the materials you chose
(`items.Composite`, `materials.derive_properties`).

`check(recipe, unit)` produces a `Plan` that says, line by line, what is satisfied and what is not (the crafting screen shows
it); `craft(recipe, unit)` consumes exactly the pieces the plan picked and returns what was made. The recipe data
lives in `recipes.py`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, TYPE_CHECKING

import capabilities
import exceptions
import materials
import species as defs
import tile_types
from components.consumable import Consumable
from components.equippable import Equippable
from components.inventory import Inventory
from entity import Constructable, Entity, Item
from items import (Composite, DEFAULT_LEATHER, DEFAULT_WOOD, Gear, Made, Placed, Stuff, carried_tags, station_tags)
from materials import Family, Material
from skills import Skill
from utilities import get_gaussian_shade, get_shade

if TYPE_CHECKING:
    from components.plant import Plant


# ─── Gathered pieces (legacy names kept: a Branch is a piece of wood, Leather a piece of old-style hide) ──────────────

class Branch(Stuff):
    """A branch dropped by `source`: a piece of the plant's wood (plants without a material of their own give plain wood)."""

    def __init__(self, source: Optional[Plant] = None, substance: Optional[Material] = None, parent=None):
        wood = substance or (getattr(source.kind, "material", None) if source is not None else None) or DEFAULT_WOOD
        Stuff.__init__(self, defs.BRANCH, wood, parent)
        if source is not None and getattr(source.kind, "material", None) is None:
            self.material = source.species.split()[0]  # old-style plants: named after the plant
            self.color = get_shade(source.color)
            self.shade = get_gaussian_shade(self.color, self.kind.shade_sigma)

    def get_title(self, exclude_attributes: bool = False) -> str:
        from items import noun_title
        return noun_title(self.material, "Branch") if self.substance is not DEFAULT_WOOD else f"{self.material} Branch"


class Leather(Stuff):
    """A piece of leather from the creature `source_species` (the old rabbit; planet creatures give `Hide`)."""

    def __init__(self, source_species: str = "", parent=None):
        Stuff.__init__(self, defs.LEATHER, DEFAULT_LEATHER, parent)
        self.material = source_species or None

    def get_title(self, exclude_attributes: bool = False) -> str:
        return f"{self.material} Leather" if self.material else "Leather"


def make_piece(kind: defs.ItemKind, substance: Material, parent=None) -> Stuff:
    """One piece of `substance` in the form `kind` (a Branch for wood, Stuff for everything else)."""
    if kind is defs.BRANCH:
        return Branch(substance=substance, parent=parent)
    return Stuff(kind, substance, parent)


# ─── Crafted: Flask (carries liquid) ─────────────────────────────────

class Flask(Item):
    """A leather flask: three sips of one liquid. What the liquid really is stays unknown until it is drunk."""

    def __init__(self, parent=None):
        Item.__init__(self, defs.FLASK)
        self.parent = parent
        self.liquid: int = 0  # liquids.LiquidKind of the contents (0 = empty)
        self.sips: int = 0
        self.boiled: bool = False

    def get_title(self, exclude_attributes: bool = False) -> str:
        if not self.sips:
            return "Leather flask (empty)"
        what = "boiled liquid" if self.boiled else "liquid"
        return f"Leather flask ({what}, {self.sips} sip{'s' if self.sips != 1 else ''})"

    def activate(self, user):
        from actions import UseFlaskAction
        return UseFlaskAction(user, self)


# ─── Crafted: Wooden Spear (the old fixed-stat weapon; new spears are `items.Gear`) ──────

class WoodenSpear(Equippable):
    def __init__(self, parent=None):
        Equippable.__init__(self, defs.WOODEN_SPEAR, parent)


# ─── Fires: campfire and torch (Constructable, placeable light sources that burn fuel) ──────

class Campfire(Constructable):
    """A placeable fire. It is lit with a spark and burns fuel: each piece of fuel keeps it lit for that material's
    `burn_duration` turns (`materials.burn_turns`). `is_lit` stays as the on/off state; `burn_until` (game time) is when the
    fuel runs out (None: burns until put out, as before fuel existed)."""

    def __init__(self, parent=None, kind: defs.ItemKind = defs.CAMPFIRE):
        Constructable.__init__(self, kind)
        self.parent = parent
        self.is_lit: bool = False
        self.burn_until: Optional[int] = None
        self.shade = self.kind.color
        self.parts: Dict[str, Material] = {}

    def _now(self) -> Optional[int]:
        world = self.parent
        game_world = getattr(getattr(world, "engine", None), "game_world", None)
        return None if game_world is None else game_world.current_time

    @property
    def emits_light(self) -> bool:
        if not (self.is_lit and self.is_placed):
            return False
        if self.burn_until is not None:
            now = self._now()
            if now is not None and now >= self.burn_until:
                self._go_out()
                return False
        return True

    def _go_out(self) -> None:
        self.is_lit = False
        self.burn_until = None
        self.color = self.shade = self.kind.color

    def turns_left(self) -> Optional[int]:
        now = self._now()
        if not self.is_lit or self.burn_until is None or now is None:
            return None
        return max(0, self.burn_until - now)

    def toggle(self) -> str:
        """Toggle the campfire on/off (no fuel needed). Returns a message string."""
        self.is_lit = not self.is_lit
        self.burn_until = None
        if self.is_lit:
            self.color = self.shade = self.kind.lit_color
            return "You light the campfire. Warm light fills the area."
        else:
            self.color = self.shade = self.kind.color
            return "You extinguish the campfire."

    def add_fuel(self, turns: int) -> None:
        """Keep the fire going `turns` longer (lighting it if it is out)."""
        now = self._now() or 0
        start = self.burn_until if (self.is_lit and self.burn_until is not None) else now
        self.burn_until = start + turns
        if not self.is_lit:
            self.is_lit = True
            self.color = self.shade = self.kind.lit_color

    def get_title(self, exclude_attributes: bool = False) -> str:
        noun = self.kind.object_type
        left = self.turns_left()
        state = "lit" if self.is_lit else "unlit"
        if left is not None:
            state += f", {left} turns of fuel"
        return f"{noun} ({state})"


class Torch(Campfire):
    """A torch stuck in the ground: a small light with its own fuel (the wood and wick it was made of)."""

    def __init__(self, parent=None):
        Campfire.__init__(self, parent, defs.TORCH)
        self.stock: int = 0  # turns of burn it was made with; the first lighting uses them all

    def stock_turns(self) -> int:
        return self.stock


# ─── Crafted: building pieces (they change the terrain instead of becoming an entity) ──────

class BuildingPiece(Constructable):
    """A constructable that is built into the terrain of a tile next to the player and used up."""

    def can_place_at(self, game_map, x: int, y: int) -> Optional[str]:
        """None if the piece can be built at (x, y) of `game_map`, otherwise the reason it cannot."""
        raise NotImplementedError

    def build(self, game_map, x: int, y: int) -> None:
        raise NotImplementedError

    def place_on_map(self, x: int, y: int, game_map) -> None:
        if isinstance(self.parent, Inventory):
            self.parent.remove(self)
        self.build(game_map, x, y)


def floor_problem(game_map, x: int, y: int) -> Optional[str]:
    tile = game_map.tile_at(x, y)
    if tile is None or not tile["open"]:
        return "There is nothing to build on there: floors go where there is open air."
    return None


def stairs_problem(game_map, x: int, y: int) -> Optional[str]:
    tile = game_map.tile_at(x, y)
    if tile is None or not tile["walkable"] or tile["stairs"] or game_map.get_entities_at_location(x, y, True):
        return "Stairs need a free floor tile."
    above = game_map.engine.game_world.tile_on_layer(game_map.z + 1, x, y)
    if above is None or not (above["open"] or above["walkable"]) or above["stairs"]:
        return "There is no room above for the stairs to lead to."
    return None


def build_floor(game_map, x: int, y: int) -> None:
    game_map.set_tile(x, y, tile_types.built_floor.get_array())


def build_stairs(game_map, x: int, y: int) -> None:
    game_map.set_tile(x, y, tile_types.up_stairs.get_array())
    game_map.engine.game_world.edit_tile(game_map.z + 1, x, y, tile_types.down_stairs.get_array())


class WoodenFloor(BuildingPiece):
    """Lays a floor where there is none (open air above a lower layer), so that you can walk there."""

    def __init__(self, parent=None):
        Constructable.__init__(self, defs.WOODEN_FLOOR)
        self.parent = parent

    def can_place_at(self, game_map, x: int, y: int) -> Optional[str]:
        return floor_problem(game_map, x, y)

    def build(self, game_map, x: int, y: int) -> None:
        build_floor(game_map, x, y)


class WoodenStairs(BuildingPiece):
    """A staircase up from a floor tile to the layer above (which gets the way down at the same place)."""

    def __init__(self, parent=None):
        Constructable.__init__(self, defs.WOODEN_STAIRS)
        self.parent = parent

    def can_place_at(self, game_map, x: int, y: int) -> Optional[str]:
        return stairs_problem(game_map, x, y)

    def build(self, game_map, x: int, y: int) -> None:
        build_stairs(game_map, x, y)


class BuiltFloor(Composite, BuildingPiece):
    """A floor built of chosen materials (what it is made of matters for the shelter it gives)."""

    def __init__(self, kind, parts, quality, recipe_key, rules=None, weights=None, designation="head", parent=None):
        Constructable.__init__(self, defs.WOODEN_FLOOR)
        self.parent = parent
        self.init_composite(parts, quality, recipe_key, rules, weights, designation)

    def can_place_at(self, game_map, x, y):
        return floor_problem(game_map, x, y)

    def build(self, game_map, x, y):
        build_floor(game_map, x, y)


class BuiltStairs(Composite, BuildingPiece):
    def __init__(self, kind, parts, quality, recipe_key, rules=None, weights=None, designation="head", parent=None):
        Constructable.__init__(self, defs.WOODEN_STAIRS)
        self.parent = parent
        self.init_composite(parts, quality, recipe_key, rules, weights, designation)

    def can_place_at(self, game_map, x, y):
        return stairs_problem(game_map, x, y)

    def build(self, game_map, x, y):
        build_stairs(game_map, x, y)


class Wall(Entity):
    """A wall built on a tile: it blocks movement and sight, has hit points from its material and quality, and keeps the
    heat in according to its insulation. Attack it (or salvage it) to take it down."""

    object_type = "Wall"
    is_structure = True

    def __init__(self, parts: Mapping[str, Material], quality: float, kinds: Mapping[str, Tuple[str, int]]):
        Entity.__init__(self, defs.WALL_BLOCK)
        self.parts = dict(parts)
        self.quality = quality
        self.consumed = dict(kinds)
        self.material: Material = next(iter(self.parts.values()))
        self.max_hp = materials.wall_hit_points(self.material, quality)
        self.hp = self.max_hp
        self.color = self.shade = self.material.color
        self._ground = None
        self.dead = False
        self.blocks_movement = True
        self.blocks_sight = True

    @property
    def insulation(self) -> float:
        return materials.shelter_insulation(self.material)

    def resistances(self):
        return ()

    def on_added_to_map(self, game_map) -> None:
        tile = game_map.tile_at(self.x, self.y)
        if self._ground is None:
            self._ground = (bool(tile["walkable"]), bool(tile["transparent"]), tile["dark"].item())
        game_map.modify_tile(self.x, self.y, transparent=False, walkable=False)

    def handle_health(self, amount: int, attacker=None) -> None:
        self.hp = max(0, min(self.max_hp, self.hp + amount))
        if self.hp == 0 and not self.dead:
            self.collapse()

    def collapse(self) -> None:
        world = self.parent
        self.dead = True
        if world is None:
            return
        x, y = self.x, self.y
        world.remove_entity(self)
        if self._ground is not None:
            walkable, transparent, dark = self._ground
            world.modify_tile(x, y, walkable=walkable, transparent=transparent, dark=dark)
        if world.is_visible(x, y):
            world.engine.message_log.add_message(f"The {self.get_title()} collapses.")

    def get_title(self, exclude_attributes: bool = False) -> str:
        from items import noun_title
        return noun_title(self.material.name, "wall")


# ─── Recipe system ───────────────────────────────────────────────────

def material_of(item) -> Optional[Material]:
    """The material an item counts as when it fills a role: a piece's own, a crafted thing's main one."""
    if isinstance(item, Stuff):
        return item.substance
    if isinstance(item, Composite):
        return item.designation
    return None


@dataclass(frozen=True)
class Need:
    """One role of a recipe: `count` pieces of the given `forms` whose material meets every `minimum` (property >= value)
    and `maximum`; all pieces of a role are of one material."""

    role: str
    label: str
    forms: Tuple[str, ...]
    count: int = 1
    minimum: Tuple[Tuple[str, float], ...] = ()
    maximum: Tuple[Tuple[str, float], ...] = ()
    families: Tuple[Family, ...] = ()

    def accepts(self, item) -> bool:
        if item.object_type not in self.forms:
            return False
        material = material_of(item)
        if material is None:
            return not (self.minimum or self.families)
        if self.families and material.family not in self.families:
            return False
        return (all(material.get(p) >= v for p, v in self.minimum) and all(material.get(p) <= v for p, v in self.maximum))

    def margin(self, material: Optional[Material]) -> float:
        """How far above its thresholds a material is (used to pick the best candidate)."""
        if material is None:
            return 0.0
        return sum(material.get(p) - v for p, v in self.minimum) + sum(v - material.get(p) for p, v in self.maximum)

    def requirement(self, count: Optional[int] = None) -> str:
        n = self.count if count is None else count
        conds = [f"{p.replace('_', ' ')} >= {v:g}" for p, v in self.minimum] + [f"{p.replace('_', ' ')} <= {v:g}" for p, v in self.maximum]
        what = " or ".join(f.lower() for f in self.forms)
        return f"{self.label}: {n} x {what}" + (f" ({', '.join(conds)})" if conds else "")


@dataclass(eq=False)
class Recipe:
    key: str
    name: str
    description: str
    stage: int
    needs: Tuple[Need, ...]
    builder: str                                  # gear | made | placed | fire | torch | floor | stairs | wall | flask | process
    result: Optional[defs.ItemKind] = None        # the kind built (gear, made, placed)
    tools: Tuple[str, ...] = ()                   # capability tags needed (carried tools or nearby stations)
    skill: Optional[Tuple[Skill, int]] = None     # (skill, minimum level)
    time: int = 1
    heat: float = 0.0                             # energy of fuel burned in a furnace
    min_temp: float = 0.0                         # furnace temperature needed (degrees C)
    rules: Mapping[str, Tuple[str, object]] = field(default_factory=dict)
    weights: Mapping[str, float] = field(default_factory=dict)  # colour weights by role
    designation: str = "head"                     # role whose material names the product
    process: str = ""                             # for builder == "process": cord | smelt | brick | glass | wire
    yields: int = 1
    is_placeable: bool = False
    efficiency: bool = True                       # can race crafting efficiency lower the counts?

    @property
    def ingredients(self) -> Dict[str, int]:
        """Counts by role (old name, used by the legacy tests and menus)."""
        return {need.role: need.count for need in self.needs}


@dataclass
class Line:
    ok: bool
    text: str


@dataclass
class Plan:
    recipe: Recipe
    ok: bool = True
    lines: List[Line] = field(default_factory=list)
    picks: Dict[str, List[Item]] = field(default_factory=dict)
    parts: Dict[str, Material] = field(default_factory=dict)
    fuel: List[Item] = field(default_factory=list)
    temperature: float = 0.0
    quality: float = 1.0
    counts: Dict[str, int] = field(default_factory=dict)

    @property
    def reasons(self) -> List[str]:
        return [line.text for line in self.lines if not line.ok]

    def add(self, ok: bool, text: str) -> None:
        self.lines.append(Line(ok, text))
        self.ok = self.ok and ok


def unit_skill(unit, skill: Skill) -> int:
    skills = getattr(unit, "skills", None)
    return skills.level(skill) if skills is not None else 0


def unit_tags(unit) -> set:
    """Every capability the unit has for crafting: its own (race, background), tools it carries, stations near it."""
    caps = unit.capabilities if hasattr(unit, "capabilities") else capabilities.EMPTY
    return set(caps.tags) | set(carried_tags(unit)) | set(station_tags(unit))


def scaled_count(recipe: Recipe, need: Need, unit) -> int:
    """How many pieces the role consumes for this unit: race efficiency (`craft_cost`) trims big counts, never below 1 each,
    and never changes a threshold."""
    if not recipe.efficiency or need.count <= 1:
        return need.count
    caps = unit.capabilities if hasattr(unit, "capabilities") else capabilities.EMPTY
    return max(1, round(need.count * caps.stat("craft_cost")))


FUEL_FORMS = ("Branch", "Coal", "Fibre")


def furnace_temperature(fuel: Sequence[Item]) -> float:
    """Degrees C a furnace reaches burning this fuel: the best fuel in it decides (wood ~1200, coal ~1575)."""
    best = max((material_of(f).combustibility for f in fuel), default=0.0)
    return 450.0 + 125.0 * best if fuel else 0.0


def fuel_candidates(unit) -> List[Item]:
    items = [i for i in unit.inventory.items if isinstance(i, Stuff) and i.form in FUEL_FORMS and i.substance.burn_yield > 0]
    return sorted(items, key=lambda i: -i.substance.combustibility)


def check(recipe: Recipe, unit, choices: Optional[Mapping[str, str]] = None) -> Plan:
    """Can `unit` do `recipe` now? The plan lists every requirement and whether it is met, and which pieces would be used."""
    plan = Plan(recipe)
    inventory = unit.inventory
    choices = choices or {}
    used: set = set()
    for need in recipe.needs:
        count = scaled_count(recipe, need, unit)
        plan.counts[need.role] = count
        candidates = [i for i in inventory.items if need.accepts(i) and id(i) not in used]
        groups: Dict[str, List[Item]] = {}
        for item in candidates:
            material = material_of(item)
            groups.setdefault(material.id if material else item.object_type, []).append(item)
        wanted = choices.get(need.role)
        usable = {k: v for k, v in groups.items() if len(v) >= count and (wanted is None or k == wanted)}
        if usable:
            best = max(usable.values(), key=lambda g: (need.margin(material_of(g[0])), len(g)))
            chosen = best[:count]
            used.update(id(i) for i in chosen)
            plan.picks[need.role] = chosen
            material = material_of(chosen[0])
            if material is not None:
                plan.parts[need.role] = material
            name = material.name if material else chosen[0].get_title()
            plan.add(True, f"{need.requirement(count)} -> {name}")
        else:
            have = max((len(v) for v in groups.values()), default=0)
            plan.add(False, f"{need.requirement(count)} (you have {have} that qualify)")
    tags = unit_tags(unit)
    for tag in recipe.tools:
        has = tag in tags
        plan.add(has, f"Needs {tag}" + ("" if has else " (a tool or station within reach)"))
    if recipe.skill is not None:
        skill, level = recipe.skill
        have_level = unit_skill(unit, skill)
        plan.add(have_level >= level, f"{skill.value.capitalize()} {level} (you: {have_level})")
    if recipe.heat > 0:
        fuel: List[Item] = []
        energy = 0.0
        for item in fuel_candidates(unit):
            if id(item) in used:
                continue
            if energy >= recipe.heat:
                break
            fuel.append(item)
            energy += materials.burn_energy(item.substance)
        plan.fuel = fuel
        plan.temperature = furnace_temperature(fuel)
        plan.add(energy >= recipe.heat, f"Fuel: {recipe.heat:g} energy of burnable pieces (you carry {energy:g})")
        if energy >= recipe.heat and (recipe.min_temp or recipe.process in ("smelt", "glass")):
            target = _melting_need(recipe, plan, unit)
            plan.add(plan.temperature >= target, f"Furnace heat >= {target:g}C (your fuel gives {plan.temperature:g}C)")
    level = unit_skill(unit, recipe.skill[0]) if recipe.skill else 0
    plan.quality = max(0.5, min(1.5, 0.9 + 0.1 * level + (0.1 if "workbench" in tags else 0.0)))
    return plan


def _melting_need(recipe: Recipe, plan: Plan, unit) -> float:
    """The temperature a heat recipe needs: its fixed minimum, or the melting point of what it works on (sand melts into
    glass, an ore must reach its metal's melting point)."""
    need = recipe.min_temp
    for material in plan.parts.values():
        if recipe.process == "glass":
            need = max(need, float(material.melting_point))
        elif recipe.process == "smelt" and material.refines_to:
            planet = unit.game_map.engine.game_world.planet
            need = max(need, float(planet.material(material.refines_to).melting_point))
    return need


def craft(recipe: Recipe, unit, choices: Optional[Mapping[str, str]] = None) -> List[Item]:
    """Do the recipe: consume what the plan picked (and the fuel), build the result(s) and add them to the inventory."""
    plan = check(recipe, unit, choices)
    if not plan.ok:
        raise exceptions.Impossible(plan.reasons[0] if plan.reasons else "You cannot make that.")
    inventory = unit.inventory
    consumed = {role: (items[0].kind.key, len(items)) for role, items in plan.picks.items()}
    results = _build(recipe, plan, unit, consumed)
    gone = [i for items in plan.picks.values() for i in items] + list(plan.fuel)
    room = inventory.capacity - (len(inventory.contents) - len(gone))
    if len(results) > room:
        raise exceptions.Impossible("Your inventory would be full.")
    for item in gone:
        inventory.remove(item)
    for result in results:
        inventory.add(result)
    return results


def _build(recipe: Recipe, plan: Plan, unit, consumed) -> List[Item]:
    parts, quality, key = plan.parts, plan.quality, recipe.key
    args = (parts, quality, key, dict(recipe.rules), dict(recipe.weights), recipe.designation)
    inventory = unit.inventory
    kind = recipe.result
    b = recipe.builder
    if b == "gear":
        item = Gear(kind, *args, parent=inventory)
    elif b == "made":
        item = Made(kind, *args, parent=inventory)
    elif b == "placed":
        item = Placed(kind, *args, parent=inventory)
    elif b == "fire":
        item = Campfire(inventory)
        item.parts = dict(parts)
    elif b == "torch":
        item = Torch(inventory)
        item.parts = dict(parts)
        item.stock = sum(materials.burn_turns(m) for m in parts.values() if m.burn_yield > 0)
    elif b == "floor":
        item = BuiltFloor(kind, *args, parent=inventory)
    elif b == "stairs":
        item = BuiltStairs(kind, *args, parent=inventory)
    elif b == "wall":
        item = BuiltWall(kind, *args, parent=inventory)
    elif b == "flask":
        item = Flask(inventory)
    elif b == "process":
        return _process(recipe, plan, unit)
    else:
        raise ValueError(f"unknown builder {b!r} in recipe {key}")
    if isinstance(item, Composite):
        item.consumed = dict(consumed)
    return [item]


def _process(recipe: Recipe, plan: Plan, unit) -> List[Item]:
    """Recipes that turn pieces into other pieces (cord, ingots, bricks, glass, wire)."""
    inventory = unit.inventory
    source = next(iter(plan.parts.values()))
    kind = recipe.result
    p = recipe.process
    if p == "cord":
        product = source
    elif p == "smelt":
        planet = unit.game_map.engine.game_world.planet
        product = materials.melt_and_cool(planet.material(source.refines_to))
    elif p == "brick":
        product = materials.fire_clay(source)
    elif p == "glass":
        product = materials.melt_and_cool(source)
    elif p == "wire":
        product = source
    else:
        raise ValueError(f"unknown process {p!r}")
    return [Stuff(kind, product, inventory) for _ in range(recipe.yields)]


class BuiltWall(Composite, BuildingPiece):
    """A wall piece in the inventory; building it puts a `Wall` entity on the tile."""

    def __init__(self, kind, parts, quality, recipe_key, rules=None, weights=None, designation="head", parent=None):
        Constructable.__init__(self, defs.WALL_BLOCK)
        self.parent = parent
        self.init_composite(parts, quality, recipe_key, rules, weights, designation)
        self.consumed: Dict[str, Tuple[str, int]] = {}

    def can_place_at(self, game_map, x, y):
        tile = game_map.tile_at(x, y)
        if tile is None or not tile["walkable"] or tile["stairs"] or tile["liquid"] or game_map.get_entities_at_location(x, y, True):
            return "Walls need a free, dry floor tile."
        return None

    def place_on_map(self, x, y, game_map):
        if isinstance(self.parent, Inventory):
            self.parent.remove(self)
        wall = Wall(self.parts, self.quality, self.consumed)
        game_map.add_entity(wall, x, y)


def get_recipes() -> List[Recipe]:
    from recipes import RECIPES
    return RECIPES


def options(recipe: Recipe, unit, role: str) -> List[Material]:
    """The materials the unit could use for `role` right now (enough qualifying pieces of one material), best first."""
    need = next(n for n in recipe.needs if n.role == role)
    count = scaled_count(recipe, need, unit)
    groups: Dict[str, List[Item]] = {}
    for item in unit.inventory.items:
        if need.accepts(item):
            material = material_of(item)
            if material is not None:
                groups.setdefault(material.id, []).append(item)
    usable = [g for g in groups.values() if len(g) >= count]
    usable.sort(key=lambda g: -need.margin(material_of(g[0])))
    return [material_of(g[0]) for g in usable]
