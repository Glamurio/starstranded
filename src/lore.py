"""Discovery in play: what can be scanned, how things are named before and after you know them, and the codex.

`knowledge` decides *how much* a given observer learns from a fact (scanner tier + skill + tags). This module supplies the
facts for the game's things (materials, creatures, plants, liquids), the names shown while they are still unidentified
(`naming.provisional`: "red rock", "grey animal"), and the lookup the codex screen uses. Standard-issue materials are known
from the start; materials you craft with are learned by handling them.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import color
import naming
from knowledge import Fact, Know
from liquids import LiquidKind
from materials import PROPERTY_KEYS, PROPERTY_READING, Material
from skills import Skill

ALWAYS_KNOWN = ("issue:", "wood:generic", "hide:generic", "bone:")


# ── subjects ────────────────────────────────────────────────────────────────────────────────────────────────
def material_subject(material: Material) -> str:
    return f"material:{material.id}"


def species_subject(kind) -> str:
    return f"species:{kind.key}"


def plant_subject(kind) -> str:
    return f"plant:{kind.key}"


def fruit_subject(kind) -> str:
    """Fruits and blooms are scanned on their own, one subject per plant species that bears them."""
    return f"fruit:{kind.parent_key}"


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
        value = getattr(material, prop)           # (every property is listed, even a tiny or zero one)
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
             Fact("diet", Skill.BIOLOGY, 2, kind.diet.name.lower(), capability="species_identification"),
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


def facts_for_fruit(kind, planet=None) -> List[Fact]:
    """What a scan of a fruit (or bloom) can tell: its name, how filling it is, whether it is safe, and what bears it."""
    parent = next((s for s in getattr(planet, "flora", ()) if s.key == kind.parent_key), None)
    facts = [name_fact(kind.species),
             Fact("nutrition", Skill.BIOLOGY, 1, f"restores {kind.hunger_amount} hunger, {kind.thirst_amount} thirst", hint="Edible?")]
    facts.append(Fact("safety", Skill.BIOLOGY, 2, "toxic: it poisons" if kind.toxicity > 0 else "safe to eat",
                      hint="Might be harmful?", capability="botanical_expertise"))
    if parent is not None:
        facts.append(Fact("grows on", Skill.BIOLOGY, 2, parent.name, hint="Grows on a plant."))
    return facts


LIQUID_TEXT = {LiquidKind.IMPURE: "impure: boil it before drinking", LiquidKind.TOXIC: "toxic: never drink it",
               LiquidKind.ACIDIC: "acidic: burns what touches it", LiquidKind.HOT: "scalding: burns when waded; boil before drinking",
               LiquidKind.LAVA: "molten rock: certain death to touch"}


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


PROVISIONAL_FORMS = {      # what an unidentified plant looks like, by template (see planet.FORMS for the real words)
    "broadleaf": "broadleaf tree", "acacia": "flat-topped tree", "willow": "drooping tree", "conifer": "needle tree",
    "cypress": "slender tree", "palm": "palm-like tree", "coast_palm": "palm-like tree", "fungal_tree": "giant fungus",
    "cactus": "spined succulent", "barrel_cactus": "spined succulent", "reeds": "reed-like plant", "bush": "bush", "thorns": "thorny shrub",
    "spore_bush": "puffy fungus", "shard_bush": "glassy shrub", "ash_shrub": "scorched shrub", "dead_tree": "dead tree",
    "beach_grass": "tufted grass", "meadow_flower": "flower", "meadow_bloom": "flower", "marsh_flower": "flower",
    "dry_flower": "flower", "crystal_bloom": "frosted flower", "frost_tree": "rimed tree", "rime_shrub": "frosted shrub", "frost_bloom": "frosted flower",
    "glowcap": "glowing mushroom", "rot_cap": "mushroom", "giant_cap": "giant mushroom", "spore_flower": "spore flower",
    "crop": "crop plant", "tallgrass": "tall grass", "golden_grass": "tall grass", "fern": "fern", "ivy": "climbing vine",
    "vine_creeper": "climbing vine", "creeper": "climbing vine", "weed": "weed", "agave": "spiked succulent", "saltbush": "grey-leaved shrub",
    "glass_cactus": "glassy succulent", "bone_thorn": "thorny shrub", "flesh_pod": "fleshy pod plant", "lumen_frond": "frond",
    "glow_reed": "reed-like plant", "algae_mat": "slimy mat", "ancient_oak": "broadleaf tree", "jungle_giant": "towering tree",
    "amber_tree": "broadleaf tree", "thorn_tree": "thorny tree", "petrified_tree": "stone-like tree", "crystal_tree": "glassy tree",
    "cinder_tree": "scorched tree", "tendril_tree": "tendril tree", "mangrove": "tangled tree", "ember_bloom": "flower",
    "iris_bloom": "flower", "toxic_bloom": "flower",
}


def provisional_plant(kind) -> str:
    """"green needle tree": colour and general shape, before the plant has been identified."""
    parts = kind.key.split(":")
    form = PROVISIONAL_FORMS.get(parts[2] if len(parts) > 2 else "", kind.category.name.lower())
    return f"{naming.hue_name(kind.color)} {form}"


def fruit_name(run, kind) -> str:
    """The fruit's name once identified; before that its colour and "fruit" (or "bloom")."""
    if run is None or not kind.parent_key or name_known(run, fruit_subject(kind)):
        return kind.species
    last = kind.species.split()[-1] if kind.species else ""
    noun = last if last in ("bloom", "blossom", "bud") else "bloom" if kind.bloom else "fruit"      # (a flower's bloom stays a bud or a blossom until it is identified)
    return f"{naming.hue_name(kind.color)} {noun}"


def species_name(run, kind) -> str:
    key = getattr(kind, "key", None)
    if run is None or not is_planetary(key):
        return kind.name
    subject = plant_subject(kind) if hasattr(kind, "category") else species_subject(kind)
    if name_known(run, subject):
        return kind.name
    colour = naming.hue_name(kind.color)
    if hasattr(kind, "category"):
        return provisional_plant(kind)
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
def subject_of(engine, entity):
    """What scanning `entity` looks at: (subject key, title, facts) or None. A creature (alive or a corpse), a plant, a piece
    of material, or meat (which teaches about the animal it came from)."""
    from components.consumable import Fruit, Meat
    from items import Composite, Stuff
    planet = engine.game_world.planet
    kind = getattr(entity, "kind", None)
    category = getattr(entity.category, "name", "")
    if category == "UNIT" and entity is not engine.player and is_planetary(getattr(kind, "key", None)):
        return species_subject(kind), kind.name, facts_for_unit(kind)
    if category == "PLANT" and is_planetary(getattr(kind, "key", None)):
        return plant_subject(kind), kind.name, facts_for_plant(kind)
    if isinstance(entity, Fruit) and getattr(entity.kind, "parent_key", None):
        return fruit_subject(entity.kind), entity.kind.species, facts_for_fruit(entity.kind, planet)
    if isinstance(entity, Stuff):
        return material_subject(entity.substance), entity.substance.name, facts_for_material(entity.substance, planet)
    if isinstance(entity, Composite):
        return material_subject(entity.designation), entity.designation.name, facts_for_material(entity.designation, planet)
    source = getattr(entity, "source", None) if isinstance(entity, Meat) else None
    if source is not None and is_planetary(getattr(source, "key", None)):
        return species_subject(source), source.name, facts_for_unit(source)
    return None


def scan_state(engine, entity) -> Optional[str]:
    """How well the player knows `entity`: None if a scanner cannot read it, "unscanned", "partly scanned" (the scanner or your
    skills can still tell you more) or "scanned" (nothing more can be learned with what you have)."""
    run = engine.game_world.run
    found = subject_of(engine, entity)
    if found is None or run is None:
        return None
    from knowledge import reveal_level
    subject, _, facts = found
    player = engine.player
    if not run.knowledge.is_known(subject):
        return "unscanned"
    more = any(reveal_level(f, player.skills, player.capabilities) > run.knowledge.level(subject, f.key) for f in facts)
    return "partly scanned" if more else "scanned"


def subject_at(engine, x: int, y: int):
    """What a scan of tile (x, y) looks at: (subject key, title, facts) or None. Creatures first (the dead too), then plants,
    loose items, liquid, and finally the rock face itself."""
    import resources
    world = engine.game_map
    planet = engine.game_world.planet
    for entity in world.stack_at(x, y):
        found = subject_of(engine, entity)
        if found is not None:
            return found
    tile = world.tile_at(x, y)
    if tile is not None and int(tile["liquid"]):
        liquid = LiquidKind(int(tile["liquid"]))
        return liquid_subject(liquid), "Liquid", facts_for_liquid(liquid)
    if planet is not None and tile is not None and not bool(tile["walkable"]):
        biome = resources.biome_key_at(engine.game_world, world.z, x, y)
        material = resources.wall_material(planet, engine.game_world.master_seed, world.z, x, y, biome)
        return material_subject(material), material.name, facts_for_material(material, planet)
    return None


def scan(engine, x: int, y: int, entity=None):
    """Scan a tile (or, with `entity`, that one thing: an item in a pack, a corpse on the ground) with the player's scanner,
    skills and tags. Returns (title, newly learned [(fact, level)]) or None if there is nothing to read there. Learning
    something practises the skill it needed."""
    found = subject_of(engine, entity) if entity is not None else subject_at(engine, x, y)
    if found is None:
        return None
    subject, title, facts = found
    player = engine.player
    run = engine.game_world.run
    learned = run.knowledge.scan(subject, facts, player.skills, player.capabilities)
    if subject.startswith("fruit:"):
        link_fruit_to_plant(run, subject)
    for fact, level in learned:
        if level is Know.FULL and fact.key != "name":
            if player.practice(fact.domain, 1):       # a skill that rises reads more next time: say so, it is not luck
                engine.message_log.add_message(f"Your {fact.domain.value} skill rose to {player.skills.level(fact.domain)}: scan again to read more.", color.orange)
    return title, learned


def link_fruit_to_plant(run, fruit_subj: str) -> None:
    """Once a fruit is known to come from a plant, that plant lists "fruit: ???" (and what the fruit's safety reveals)."""
    plant = "plant:" + fruit_subj[len("fruit:"):]
    run.knowledge.note(plant, "fruit")
    safety = run.knowledge.level(fruit_subj, "safety")
    if safety:
        run.knowledge.learn(plant, "fruit", safety)


def describe_lines(run, subject: str, facts: Iterable[Fact]) -> List[str]:
    """Codex text for one subject: every fact at the level known (unknown ones are shown as '???')."""
    from knowledge import format_fact
    lines = []
    for fact, level, text in run.knowledge.view(subject, facts):
        label = fact.key.replace("_", " ")
        lines.append(f"{label}: {text if text is not None else '???'}")
    return lines


def _material_picture(material):
    """A piece that looks like the material (an ore chunk, a lump of coal, a pile of sand ...), tinted in its colour."""
    import species as defs
    from materials import Family
    from tile_types import sprite_id
    family = material.family
    if material.refines_to or material.id.startswith("ore:"):
        kind = defs.PIECE_ORE
    else:
        kind = {Family.WOOD: defs.BRANCH, Family.FIBER: defs.PIECE_FIBER, Family.HIDE: defs.PIECE_HIDE, Family.CLAY: defs.PIECE_CLAY,
                Family.SAND: defs.PIECE_SAND, Family.FUEL: defs.PIECE_COAL, Family.GLASS: defs.PIECE_GLASS,
                Family.METAL: defs.PIECE_INGOT}.get(family, defs.PIECE_STONE)
    return sprite_id(*kind.sprite) if isinstance(kind.sprite, tuple) else int(kind.sprite), tuple(material.color)


def codex_pictures(engine) -> Dict[str, Tuple[int, tuple]]:
    """A picture for every codex subject: {subject: (sprite id, tint)} - the creature or plant itself, a piece for a material."""
    from tile_types import sprite_id
    planet = engine.game_world.planet
    out: Dict[str, Tuple[int, tuple]] = {}
    if planet is None:
        return out
    for _, material in planet.materials:
        out[material_subject(material)] = _material_picture(material)
    for kind in planet.fauna:
        out[species_subject(kind)] = (sprite_id(*kind.sprite) if isinstance(kind.sprite, tuple) else int(kind.sprite), tuple(kind.color))
    for kind in planet.flora:
        out[plant_subject(kind)] = (sprite_id(*kind.sprite) if isinstance(kind.sprite, tuple) else int(kind.sprite), tuple(kind.color))
    for liquid in LiquidKind:
        out[liquid_subject(liquid)] = (sprite_id(2, 41), {LiquidKind.LAVA: (230, 90, 30), LiquidKind.TOXIC: (110, 200, 60),
                                                         LiquidKind.ACIDIC: (190, 210, 60), LiquidKind.HOT: (120, 170, 220)}.get(liquid, (60, 110, 180)))
    import structures
    for index in range(structures.RUIN_COUNT):
        out[f"ruin:{index}"] = (sprite_id(0, 2), (150, 145, 140))
    return out


# ── codex: descriptions and drops ──────────────────────────────────────────────────────────────────────────────
COVERING_WORDS = {"fur": "fur", "feather": "feathers", "chitin": "exoskeleton", "scale": "scales", "skin": "skin"}
"""What covers a creature's body, in the sentence "It has hard, tough <covering>"."""
TRAITS = (      # (property, at least, adjective, what it lets the thing do)
    ("hardness", 5.5, "hard", ""), ("toughness", 5.5, "tough", ""), ("density", 5.5, "dense", ""), ("elasticity", 5.5, "springy", ""),
    ("abrasivity", 4.5, "rough", ""), ("insulation", 5.0, "thickly insulating", "can even thrive in a cold climate"),
    ("thermal_conductivity", 5.0, "heat-shedding", "copes with a hot climate"), ("flammability", 7.0, "flammable", ""),
)


def _join(words: List[str]) -> str:
    return words[0] if len(words) < 2 else ", ".join(words[:-1]) + " and " + words[-1]


def _traits(material, covering: str = "") -> Tuple[List[str], List[str]]:
    """The adjectives and abilities a material's standout properties suggest (at most two adjectives, strongest first). For a body
    covering "standout" is high for that kind of covering (fur is always warm, so only unusually warm fur counts)."""
    import planet as pl
    ranges = pl.COVERING_RANGES.get(covering, {})
    found = []
    for prop, low, adjective, ability in TRAITS:
        value = getattr(material, prop)
        if prop in ranges:
            lo, hi = ranges[prop]
            score = (value - lo) / (hi - lo + 0.01)
            if score < 0.65:
                continue
        elif value < low:
            continue
        else:
            score = value / 10
        found.append((score, adjective, ability))
    found.sort(reverse=True)
    return [a for _, a, _ in found][:2], [b for _, _, b in found if b][:1]


def _climate(habitat) -> str:
    """"cold", "warm" or "" from the middle of the temperature range a species lives in."""
    if habitat is None:
        return ""
    low, high = habitat.temperature
    middle = (low + high) / 2
    return "cold" if middle < -0.3 else "hot" if middle > 0.45 else ""


def describe_unit(kind) -> str:
    """A short description made from the creature's body covering, its highest properties and how it behaves."""
    covering = COVERING_WORDS.get(getattr(kind, "covering", "skin"), "skin")
    adjectives, abilities = _traits(kind.hide, getattr(kind, "covering", "")) if kind.hide is not None else ([], [])
    article = "a " if covering == "exoskeleton" else ""
    body = f"It has {article}{_join(adjectives)} {covering}" if adjectives else f"It has {article}plain {covering}"
    climate = _climate(kind.habitat)
    if abilities:
        body += " and " + abilities[0]
    elif climate:
        body += f" and lives in {climate} country"
    temper = "hostile" if kind.ai.name == "HOSTILE" else "peaceable"
    diet = {"herbivore": "eats plants", "carnivore": "hunts for meat", "omnivore": "eats anything"}.get(kind.diet.name.lower(), "")
    return f"{body}. It is {temper} and {diet}." if diet else f"{body}. It is {temper}."


def describe_plant(kind) -> str:
    stuff = kind.material or kind.fiber
    adjectives, abilities = _traits(stuff) if stuff is not None else ([], [])
    noun = "wood" if kind.material is not None else "fibre"
    text = f"Its {noun} is {_join(adjectives)}" if adjectives else f"Its {noun} is plain"
    climate = _climate(kind.habitat)
    if abilities:
        text += f"; it {abilities[0]}"
    elif climate:
        text += f"; it grows in {climate} country"
    if kind.fruit is not None:
        safe = "poisonous" if kind.fruit.toxicity > 0 else "edible"
        last = kind.fruit.species.lower().split(" ")[-1]
        if kind.category.name == "FLOWER":                              # (a flower's bloom is the flower: "its bud is poisonous")
            text += f". Its {last if last in ('bud', 'blossom', 'bloom') else 'bloom'} is {safe}"
        else:
            text += f". It bears {safe} {kind.fruit.species.lower()}"
    return text + "."


def _top_properties(material, count: int = 4) -> List[str]:
    values = sorted(((getattr(material, p), p) for p in PROPERTY_KEYS if getattr(material, p) > 0), reverse=True)
    return [p for _, p in values[:count]]


def _material_lines(run, label: str, material, planet) -> List[Tuple[str, bool]]:
    """One drop made of a planet material: its name and its strongest properties as far as they are known. [(text, known)]"""
    subject = material_subject(material)
    shown = {f.key: text for f, _, text in run.knowledge.view(subject, facts_for_material(material, planet))}
    lines = [(f"{label}: {material_name(run, material)}", True)]
    for prop in _top_properties(material):
        text = shown.get(prop)
        lines.append((f"    {prop.replace('_', ' ')}: {text if text is not None else '???'}", text is not None))
    return lines


def drops_of(engine, subject: str) -> List[Tuple[str, bool]]:
    """What a creature or plant of this codex entry can leave behind, with the properties of each; [] for other kinds of entry.
    Things with properties of their own per piece (meat, bones) are given as ranges."""
    import decay
    from components.consumable import MEAT_HUNGER
    planet, run = engine.game_world.planet, engine.game_world.run
    if planet is None or run is None:
        return []
    out: List[Tuple[str, bool]] = []
    for kind in planet.fauna:
        if species_subject(kind) == subject:
            out.append((f"Meat: restores {min(MEAT_HUNGER)}-{max(MEAT_HUNGER)} hunger, varies by carcass", True))
            if kind.hide is not None:
                out += _material_lines(run, "Hide", kind.hide, planet)
            ranges = decay.BONE_RANGES
            out.append((f"Bones: {', '.join(f'{p} {lo}-{hi}' for p, (lo, hi) in ranges.items())} (rolled for each bone)", True))
            return out
    for kind in planet.flora:
        if plant_subject(kind) == subject:
            if kind.material is not None:
                out += _material_lines(run, "Branches", kind.material, planet)
            if kind.fiber is not None:
                out += _material_lines(run, "Fibre", kind.fiber, planet)
            if kind.fruit is not None:
                shown = {f.key: text for f, _, text in run.knowledge.view(fruit_subject(kind.fruit), facts_for_fruit(kind.fruit, planet))}
                out.append((f"Fruit: {kind.fruit.species}", True))
                out.append((f"    nutrition: {shown.get('nutrition') or '???'}", shown.get("nutrition") is not None))
                out.append((f"    safety: {shown.get('safety') or '???'}", shown.get("safety") is not None))
            return out
    return out


def description_of(engine, subject: str) -> str:
    planet = engine.game_world.planet
    if planet is None:
        return ""
    for kind in planet.fauna:
        if species_subject(kind) == subject:
            return describe_unit(kind)
    for kind in planet.flora:
        if plant_subject(kind) == subject:
            return describe_plant(kind)
    return ""


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
    for liquid in (LiquidKind.IMPURE, LiquidKind.TOXIC, LiquidKind.ACIDIC, LiquidKind.HOT, LiquidKind.LAVA):
        if liquid_subject(liquid) in known:
            out["Liquids"].append((liquid_subject(liquid), "Liquid", facts_for_liquid(liquid)))
    import structures
    for index in range(structures.RUIN_COUNT):
        subject = f"ruin:{index}"
        if subject in known:
            out["Sites"].append((subject, f"Precursor ruin {index + 1}", [structures.inscription_fact(index)]))
    return out
