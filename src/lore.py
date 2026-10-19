"""Discovery in play: what can be scanned, how things are named before and after you know them, and the codex.

`knowledge` decides *how much* a given observer learns from a fact (scanner tier + skill + tags). This module supplies the
facts for the game's things (materials, creatures, plants, liquids), the names shown while they are still unidentified
(`naming.provisional`: "red rock", "grey animal"), and the lookup the codex screen uses. Standard-issue materials are known
from the start; materials you craft with are learned by handling them.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import naming
from knowledge import Fact, Know
from liquids import LiquidKind
from materials import PROPERTY_KEYS, PROPERTY_READING, Material
from skills import Skill

ALWAYS_KNOWN = ("issue:", "wood:generic", "hide:generic")


# ── subjects ────────────────────────────────────────────────────────────────────────────────────────────────
def material_subject(material: Material) -> str:
    return f"material:{material.id}"


def species_subject(kind) -> str:
    return f"species:{kind.key}"


def plant_subject(kind) -> str:
    return f"plant:{kind.key}"


def liquid_subject(kind: LiquidKind) -> str:
    return f"liquid:{int(kind)}"


def is_planetary(key: Optional[str]) -> bool:
    return bool(key) and key.startswith("planet:")


# ── facts ───────────────────────────────────────────────────────────────────────────────────────────────────
def name_fact(value: str) -> Fact:
    return Fact("name", Skill.SURVIVAL, 1, value)


def facts_for_material(material: Material, planet=None) -> List[Fact]:
    facts = [name_fact(material.name)]
    for prop in PROPERTY_KEYS:
        value = getattr(material, prop)
        if value > 0:
            skill, level = PROPERTY_READING[prop]
            facts.append(Fact(prop, skill, level, round(value, 1)))
    if material.refines_to and planet is not None:
        target = planet.material(material.refines_to)
        facts.append(Fact("refines_to", Skill.CHEMISTRY, 3, f"smelts to {target.name}", hint="Might hold metal.",
                          capability="chemical_analysis"))
    if material.melting_point:
        facts.append(Fact("melting_point", Skill.CHEMISTRY, 3, f"{material.melting_point} degrees C"))
    if material.burn_yield > 0:
        facts.append(Fact("fuel", Skill.CHEMISTRY, 2, f"burns {material.burn_duration} turns per piece", hint="Burns?"))
    return facts


def facts_for_unit(kind) -> List[Fact]:
    facts = [name_fact(kind.name),
             Fact("health", Skill.BIOLOGY, 1, kind.max_hp),
             Fact("diet", Skill.BIOLOGY, 2, kind.diet.value, capability="species_identification"),
             Fact("temper", Skill.BIOLOGY, 2, "hostile" if kind.ai.name == "HOSTILE" else "peaceable",
                  capability="species_identification"),
             Fact("attack", Skill.BIOLOGY, 2, f"{kind.power} {kind.damage_type} damage", hint="Has a bite?",
                  capability="species_identification")]
    if kind.hide is not None:
        facts.append(Fact("hide", Skill.BIOLOGY, 3, f"yields {kind.hide.name}", capability="species_identification"))
    return facts


def facts_for_plant(kind) -> List[Fact]:
    facts = [name_fact(kind.name), Fact("growth", Skill.BIOLOGY, 3, f"a cycle takes about {kind.growth_cycle} growth steps")]
    stuff = kind.material or kind.fiber
    if stuff is not None:
        facts.append(Fact("material", Skill.BIOLOGY, 2, f"gives {stuff.name}", capability="botanical_expertise"))
    if kind.fruit is not None:
        toxic = kind.fruit.toxicity > 0
        facts.append(Fact("fruit", Skill.BIOLOGY, 3, "toxic fruit" if toxic else "edible fruit", hint="Bears fruit.",
                          capability="botanical_expertise"))
    return facts


LIQUID_TEXT = {LiquidKind.IMPURE: "impure: boil it before drinking", LiquidKind.TOXIC: "toxic: never drink it",
               LiquidKind.ACIDIC: "acidic: burns what touches it", LiquidKind.HOT: "scalding: burns when waded; boil before drinking"}


def facts_for_liquid(kind: LiquidKind) -> List[Fact]:
    return [name_fact("Liquid"), Fact("nature", Skill.CHEMISTRY, 2, LIQUID_TEXT.get(kind, "clean"), hint="Unknown liquid.",
                                      capability="chemical_analysis")]


# ── names ───────────────────────────────────────────────────────────────────────────────────────────────────
def run_of(entity):
    """The run state of the game an entity is in (None for detached entities and old test worlds)."""
    node = getattr(entity, "parent", None)
    for _ in range(4):
        if node is None:
            return None
        try:
            engine = node.engine
        except Exception:
            engine = None
        if engine is not None:
            game_world = getattr(engine, "game_world", None)
            return getattr(game_world, "run", None)
        node = getattr(node, "parent", None)
    return None


def name_known(run, subject: str, always: bool = False) -> bool:
    return run is None or always or run.knowledge.level(subject, "name") > Know.UNKNOWN


def material_name(run, material: Material) -> str:
    """The material's real name once identified, otherwise what it looks like."""
    if run is None or material.id.startswith(ALWAYS_KNOWN) or name_known(run, material_subject(material)):
        return material.name
    covering = material.name.rsplit(" ", 1)[-1]
    if material.family.value == "hide" and covering in ("fur", "skin", "feathers", "chitin", "scales"):
        return f"{naming.hue_name(material.color)} {covering}"   # the covering is plain to see even before the name is known
    return naming.hue_name(material.color) + " " + {"wood": "wood", "stone": "rock", "metal": "metal", "fiber": "fibre",
                                                    "hide": "hide", "sand": "sand", "clay": "clay", "fuel": "coal",
                                                    "crystal": "crystal"}.get(material.family.value, material.family.value)


def species_name(run, kind) -> str:
    key = getattr(kind, "key", None)
    if run is None or not is_planetary(key):
        return kind.name
    subject = plant_subject(kind) if hasattr(kind, "category") else species_subject(kind)
    if name_known(run, subject):
        return kind.name
    colour = naming.hue_name(kind.color)
    if hasattr(kind, "category"):
        return f"{colour} {kind.category.name.lower()}"
    covered = {"fur": "furred ", "feather": "feathered ", "chitin": "armoured ", "scale": "scaly ", "skin": ""}
    return f"{colour} {covered.get(getattr(kind, 'covering', 'fur'), '') if kind.hide is not None else ''}animal"


def english_name(planet, title: str) -> Optional[str]:
    """`title` with every culture name in it replaced by its plain-English meaning ("Brubaab hide" -> "hard hopper hide"),
    or None when the planet speaks English or the title holds no foreign name (e.g. an unidentified "red furred animal")."""
    if planet is None or not getattr(planet, "glosses", None):
        return None
    lowered = title.lower()
    for name, gloss in sorted(planet.glosses, key=lambda p: -len(p[0])):
        at = lowered.find(name.lower())
        if at >= 0:
            return title[:at] + gloss + title[at + len(name):]
    return None


def property_known(run, material: Material, prop: str) -> bool:
    """Has the player read this property of this material exactly (or is it standard issue)?"""
    if run is None or material.id.startswith(ALWAYS_KNOWN):
        return True
    return run.knowledge.level(material_subject(material), prop) is Know.FULL


def learn_names(run, materials: Iterable[Material]) -> None:
    """Handling a material (crafting with it) teaches its name."""
    if run is None:
        return
    for material in materials:
        run.knowledge.learn(material_subject(material), "name", Know.FULL)


# ── scanning ────────────────────────────────────────────────────────────────────────────────────────────────
def subject_at(engine, x: int, y: int):
    """What a scan of tile (x, y) looks at: (subject key, title, facts) or None. Creatures first, then plants, loose
    items, liquid, and finally the rock face itself."""
    import resources
    from components.consumable import Fruit
    from items import Composite, Stuff
    world = engine.game_map
    planet = engine.game_world.planet
    player = engine.player
    for entity in world.stack_at(x, y):
        if entity is player:
            continue
        kind = getattr(entity, "kind", None)
        category = getattr(entity.category, "name", "")
        if category == "UNIT" and entity.is_alive and is_planetary(getattr(kind, "key", None)):
            return species_subject(kind), kind.name, facts_for_unit(kind)
        if category == "PLANT" and not getattr(entity, "dead", False) and is_planetary(getattr(kind, "key", None)):
            return plant_subject(kind), kind.name, facts_for_plant(kind)
        if isinstance(entity, Stuff):
            return material_subject(entity.substance), entity.substance.name, facts_for_material(entity.substance, planet)
        if isinstance(entity, Composite):
            return material_subject(entity.designation), entity.designation.name, facts_for_material(entity.designation, planet)
    tile = world.tile_at(x, y)
    if tile is not None and int(tile["liquid"]):
        liquid = LiquidKind(int(tile["liquid"]))
        return liquid_subject(liquid), "Liquid", facts_for_liquid(liquid)
    if planet is not None and tile is not None and not bool(tile["walkable"]):
        biome = resources.biome_key_at(engine.game_world, world.z, x, y)
        material = resources.wall_material(planet, engine.game_world.master_seed, world.z, x, y, biome)
        return material_subject(material), material.name, facts_for_material(material, planet)
    return None


def scan(engine, x: int, y: int):
    """Scan a tile with the player's scanner, skills and tags. Returns (title, newly learned [(fact, level)]) or None if
    there is nothing to read there. Learning something practises the skill it needed."""
    found = subject_at(engine, x, y)
    if found is None:
        return None
    subject, title, facts = found
    player = engine.player
    run = engine.game_world.run
    learned = run.knowledge.scan(subject, facts, player.skills, player.capabilities)
    for fact, level in learned:
        if level is Know.FULL and fact.key != "name":
            player.practice(fact.domain, 1)
    return title, learned


def describe_lines(run, subject: str, facts: Iterable[Fact]) -> List[str]:
    """Codex text for one subject: every fact at the level known (unknown ones are shown as '???')."""
    from knowledge import format_fact
    lines = []
    for fact, level, text in run.knowledge.view(subject, facts):
        label = fact.key.replace("_", " ")
        lines.append(f"{label}: {text if text is not None else '???'}")
    return lines


def codex_entries(engine) -> Dict[str, List[Tuple[str, str, List[Fact]]]]:
    """Everything the player has learned something about, by category: {category: [(subject, title, facts)]}."""
    planet = engine.game_world.planet
    run = engine.game_world.run
    out: Dict[str, List[Tuple[str, str, List[Fact]]]] = {"Materials": [], "Creatures": [], "Plants": [], "Liquids": [],
                                                         "Sites": []}
    if planet is None:
        return out
    known = set(run.knowledge.to_dict())
    for _, material in planet.materials:
        subject = material_subject(material)
        if subject in known:
            out["Materials"].append((subject, material.name if name_known(run, subject) else "unidentified " + material_name(run, material),
                                     facts_for_material(material, planet)))
    for kind in planet.fauna:
        if species_subject(kind) in known:
            out["Creatures"].append((species_subject(kind), species_name(run, kind), facts_for_unit(kind)))
    for kind in planet.flora:
        if plant_subject(kind) in known:
            out["Plants"].append((plant_subject(kind), species_name(run, kind), facts_for_plant(kind)))
    for liquid in (LiquidKind.IMPURE, LiquidKind.TOXIC, LiquidKind.ACIDIC, LiquidKind.HOT):
        if liquid_subject(liquid) in known:
            out["Liquids"].append((liquid_subject(liquid), "Liquid", facts_for_liquid(liquid)))
    import structures
    for index in range(structures.RUIN_COUNT):
        subject = f"ruin:{index}"
        if subject in known:
            out["Sites"].append((subject, f"Precursor ruin {index + 1}", [structures.inscription_fact(index)]))
    return out
