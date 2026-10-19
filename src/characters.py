"""Who you can be: races (with lore), backgrounds (skills, tags, starting kit) and character creation.

Race bodies come from `species` (capability grants); everything about *what a person was before the crash* lives here:
a `Background` adds trained skills, a few tags and a starting kit. Kits are built from standard-issue materials with
the same item classes crafting makes (`items.Gear`, `items.Made`), so a corporate knife behaves like one you would
craft: it is simply made of better stuff than you can make yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

import species as defs
from capabilities import Grant, grants
from materials import Family, Material
from skills import Skill, SkillSet

# ── standard-issue materials (what corporate kits are made of; not found on the planet) ────────────────────────
ISSUE_STEEL = Material(
    "issue:steel", "issue steel", Family.METAL, (170, 175, 185), hardness=7, toughness=7, tenacity=7, abrasivity=3, density=7,
    elasticity=4, insulation=1, electrical_conductivity=7, thermal_conductivity=7, melting_point=1500)
ISSUE_CLOTH = Material(
    "issue:cloth", "ballistic cloth", Family.FIBER, (150, 150, 160), hardness=1, toughness=5, tenacity=7, density=2,
    elasticity=5, insulation=5, thermal_conductivity=1, flammability=2, combustibility=2, burn_yield=10.0, burn_duration=3)
ISSUE_GLASS = Material(
    "issue:glass", "clear polymer", Family.GLASS, (200, 225, 240), hardness=4, toughness=3, density=3, insulation=2,
    transparency=9, is_amorphous=True, melting_point=800)
ISSUE_CIRCUIT = Material(
    "issue:circuit", "printed circuit", Family.COMPOSITE, (80, 200, 120), hardness=3, toughness=2, density=2,
    electrical_conductivity=8)


# ── races ───────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RaceInfo:
    species: defs.UnitSpecies
    lore: str
    ages: str
    strengths: Tuple[str, ...]
    weaknesses: Tuple[str, ...]


RACES: Dict[str, RaceInfo] = {r.species.key: r for r in (
    RaceInfo(
        defs.HUMAN,
        "Humans built the corporate shipping lanes and still run them. Adaptable, stubborn and wasteful, they carry "
        "more tools than any other people and are best at making a little go a long way.",
        "adult 20-60, long-lived", ("wastes less when crafting", "eats anything"),
        ("slowed in the dark",)),
    RaceInfo(
        defs.SELENITE_PEOPLE,
        "The Selenites are the gardeners of the old moon colonies: slight, chitin-plated, patient. They coax crops out "
        "of poor soil and can stop breathing for a long while, but their shells shatter under hard blows.",
        "adult 15-45, short-lived", ("plants yield and grow more for them", "hold their breath three times as long"),
        ("herbivores: meat is no food", "brittle shell takes extra blunt damage")),
    RaceInfo(
        defs.MAU,
        "The Mau came out of the burrow-cities of a dim, wet world: quick, clawed hunters who see in the near dark and "
        "dislike getting wet. Their old contracts with Heavy Industries make them natural bounty hunters.",
        "adult 12-40, short-lived", ("twice as fast", "darkvision", "claws"),
        ("carnivores: plants are no food", "will not wade into liquid")),
)}


# ── backgrounds ─────────────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Background:
    key: str
    name: str
    description: str
    skills: Tuple[Tuple[Skill, int], ...]
    grants: Tuple[Grant, ...] = ()
    kit: Tuple[str, ...] = ()           # extra items on top of `COMMON_KIT`, see `issue_item`


BACKGROUNDS: Dict[str, Background] = {b.key: b for b in (
    Background("bounty_hunter", "Bounty Hunter", "Tracks marked targets for corporate bounty boards. Armed, with a tracker.",
               ((Skill.MARKSMANSHIP, 3), (Skill.SURVIVAL, 1), (Skill.COMBAT, 2)), grants("target_tracker"), ("pistol", "ammo")),
    Background("biologist", "Biologist", "Field xenobiologist: knows animals and plants, and reads them with a scanner.",
               ((Skill.BIOLOGY, 3), (Skill.CHEMISTRY, 1)), grants("botanical_expertise", "species_identification"),
               ("medkit",)),
    Background("chemist", "Chemist", "Analyses liquids and compounds; knows what will kill you before you drink it.",
               ((Skill.CHEMISTRY, 3), (Skill.ENGINEERING, 1)), grants("chemical_analysis"), ("medkit",)),
    Background("surveyor", "Surveyor", "Maps terrain for claim offices. Carries a survey kit.",
               ((Skill.GEOLOGY, 3), (Skill.SURVIVAL, 1)), (), ("survey_kit", "pickaxe")),
    Background("salvager", "Salvager", "Strips wrecks for parts. Gets more out of every salvage.",
               ((Skill.ENGINEERING, 2), (Skill.GEOLOGY, 1)), grants("enhanced_salvaging"), ("salvage_tool",)),
    Background("translator", "Translator", "Speaks every tongue on the shipping lanes, living and dead.",
               ((Skill.LINGUISTICS, 3),), grants("universal_translator"), ()),
    # justified extras: each fills a gap in the escape routes
    Background("survivalist", "Survivalist", "Left alone on frontier worlds before. Fire, shelter and first aid.",
               ((Skill.SURVIVAL, 3), (Skill.BIOLOGY, 1), (Skill.COMBAT, 1)), grants("first_aid"), ("hatchet", "medkit")),
    Background("pilot", "Pilot", "Flew freight under contract. Knows a ship's systems: the repair route needs one.",
               ((Skill.ENGINEERING, 3),), grants("pilot_training"), ()),
    Background("archaeologist", "Archaeologist", "Digs up precursor sites for relic collectors.",
               ((Skill.LINGUISTICS, 2), (Skill.GEOLOGY, 1)), grants("archaeology"), ("shovel",)),
)}

DEFAULT_RACE = defs.HUMAN.key
DEFAULT_BACKGROUND = "survivalist"
COMMON_KIT = ("knife", "hide_armor", "ration", "ration", "ration", "flask")
EQUIPPED = ("knife", "hide_armor")


def _parts(key: str) -> Mapping[str, Material]:
    from items import DEFAULT_WOOD as tree
    steel = ISSUE_STEEL
    return {
        "knife": {"blade": steel, "handle": tree, "binding": ISSUE_CLOTH},
        "hatchet": {"head": steel, "handle": tree, "binding": ISSUE_CLOTH},
        "pickaxe": {"head": steel, "handle": tree, "binding": ISSUE_CLOTH},
        "shovel": {"blade": steel, "handle": tree, "binding": ISSUE_CLOTH},
        "salvage_tool": {"blade": steel, "handle": tree, "binding": ISSUE_CLOTH},
        "hide_armor": {"body": ISSUE_CLOTH, "binding": ISSUE_CLOTH},
        "medkit": {"bandage": ISSUE_CLOTH, "vial": ISSUE_GLASS},
        "survey_kit": {"lens": ISSUE_GLASS, "circuit": ISSUE_CIRCUIT, "frame": steel},
    }[key]


def issue_item(key: str, unit):
    """Build one starting item for `unit` and put it in the inventory."""
    import crafting
    import recipes
    from components.consumable import Ration
    from items import Ammo, DEFAULT_WOOD, Gear, Stuff
    inventory = unit.inventory
    if key == "ration":
        item = Ration(inventory)
    elif key == "ammo":
        item = Ammo(inventory, 12)
    elif key == "flask":
        item = crafting.Flask(inventory)
    elif key == "pistol":
        item = Gear(defs.PISTOL, {"barrel": ISSUE_STEEL, "grip": DEFAULT_WOOD}, 1.0, "pistol",
                    {"hardness": ("role", "barrel"), "toughness": ("role", "barrel"), "density": ("role", "barrel")},
                    {"barrel": 3, "grip": 1}, "barrel", parent=inventory)
    else:
        recipe = recipes.BY_KEY[key]
        plan = crafting.Plan(recipe, parts=dict(_parts(key)), quality=1.0)
        item = crafting._build(recipe, plan, unit, {})[0]
    if getattr(item, "dull", False):
        item.sharpen()
    inventory.add(item)
    return item


def create_character(name: Optional[str] = None, race: str = DEFAULT_RACE, background: str = DEFAULT_BACKGROUND,
                     sponsor: Optional[str] = None):
    """A new player of `race` with `background`'s skills, tags and kit, working for `sponsor` (a key, may be None)."""
    from components.unit import Player
    bg = BACKGROUNDS[background]
    player = Player(name, RACES[race].species)
    player.background = bg.key
    player.sponsor = sponsor
    player.skills = SkillSet(dict(bg.skills))
    player.extra_grants = tuple(bg.grants)
    for key in list(COMMON_KIT) + list(bg.kit):
        item = issue_item(key, player)
        if key in EQUIPPED:
            player.equipment.toggle_equip(item, add_message=False)
    return player


def describe(race: str, background: str) -> List[str]:
    """Text lines for the creation screen: what this combination is good and bad at."""
    info, bg = RACES[race], BACKGROUNDS[background]
    return [info.lore, "", "Strengths: " + ", ".join(info.strengths), "Weaknesses: " + ", ".join(info.weaknesses), "",
            f"{bg.name}: {bg.description}",
            "Skills: " + ", ".join(f"{s} {l}" for s, l in bg.skills)]
