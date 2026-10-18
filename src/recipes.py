"""The recipe catalogue (data; the rules are in `crafting.py`).

Thresholds are on the material scale 0-10 (see `materials.py`). Stages: 1 handcraft, 2 basic tools and shelter, 3 refining
(furnace), 4 industrial parts, 5 electronics and power, 6 spacefaring equipment. A stage is only a description: what actually
limits you is the materials, tools, stations and skill each recipe asks for, so anything that meets the thresholds works.
"""
from __future__ import annotations

from typing import Dict, List

import species as defs
from crafting import Need, Recipe
from materials import Family
from skills import Skill

BIND = ("Cord", "Fibre", "Hide", "Leather")
HEADS = ("Stone", "Ingot")


def binding(minimum: float = 3.0) -> Need:
    return Need("binding", "Binding", BIND, 1, (("tenacity", minimum),))


def handle(minimum: float = 4.0, role: str = "handle", count: int = 1) -> Need:
    return Need(role, "Handle" if role == "handle" else role.capitalize(), ("Branch",), count, (("toughness", minimum),))


def head(hard: float, tough: float = 0.0, role: str = "head", label: str = "Head") -> Need:
    mins = (("hardness", hard),) + ((("toughness", tough),) if tough else ())
    return Need(role, label, HEADS, 1, mins)


_TOOL_RULES = {
    "hardness": ("role", "head"), "toughness": ("min", ("head", "handle")), "tenacity": ("min", ("binding", "handle")),
    "density": ("mean", {"head": 2, "handle": 1}),
}
_BLADE_RULES = {k: (v[0], tuple("blade" if r == "head" else r for r in v[1]) if v[0] == "min" else v[1]) for k, v in _TOOL_RULES.items()}
_BLADE_RULES["hardness"] = ("role", "blade")
_BLADE_RULES["density"] = ("mean", {"blade": 2, "handle": 1})
_ARMOR_RULES = {"toughness": ("role", "body"), "tenacity": ("min", ("body", "binding")), "insulation": ("role", "body"),
                "density": ("role", "body")}

RECIPES: List[Recipe] = [
    # ── 1. handcraft ──────────────────────────────────────────────────────────────────────────────────────────────
    Recipe("cord", "Cord", "Twist plant fibre or strips of hide into strong cord for binding.", 1,
           (Need("fibre", "Fibre", ("Fibre",), 2, (("tenacity", 3.0),)),), "process", defs.PIECE_CORD, process="cord"),
    Recipe("knife", "Knife", "A knapped blade on a wooden handle: sharp, once you have put an edge on it.", 1,
           (Need("blade", "Blade", HEADS, 1, (("hardness", 6.0),)), handle(3.0), binding()), "gear", defs.KNIFE,
           rules=_BLADE_RULES, weights={"blade": 3, "handle": 2, "binding": 1}, designation="blade", time=2),
    Recipe("hatchet", "Hatchet", "A stone or metal head lashed to a handle. Fells trees and cuts wood.", 1,
           (head(6.0, 2.0), handle(4.0), binding()), "gear", defs.HATCHET, rules=_TOOL_RULES,
           weights={"head": 3, "handle": 2, "binding": 1}, time=3),
    Recipe("pickaxe", "Pickaxe", "A hard point on a stout handle. Breaks rock: the head must be harder than the rock.", 1,
           (head(6.0, 2.0), handle(4.0), binding()), "gear", defs.PICKAXE, rules=_TOOL_RULES,
           weights={"head": 3, "handle": 2, "binding": 1}, time=3),
    Recipe("shovel", "Shovel", "A flat blade on a handle, for digging sand and clay.", 1,
           (Need("blade", "Blade", HEADS, 1, (("hardness", 3.0),)), handle(3.0), binding()), "gear", defs.SHOVEL,
           rules=_BLADE_RULES, weights={"blade": 3, "handle": 2, "binding": 1}, designation="blade", time=2),
    Recipe("club", "Club", "A heavy length of hard wood.", 1,
           (Need("head", "Head", ("Branch",), 2, (("density", 3.0), ("toughness", 4.0))),), "gear", defs.CLUB,
           rules={"density": ("role", "head"), "toughness": ("role", "head")}, time=1),
    Recipe("spear", "Spear", "A hard point lashed to a long shaft: reach and piercing power.", 1,
           (head(6.0, 2.0), handle(3.0, role="shaft"), binding()), "gear", defs.SPEAR,
           rules={"hardness": ("role", "head"), "toughness": ("min", ("head", "shaft")), "tenacity": ("min", ("binding", "shaft")),
                  "density": ("mean", {"head": 2, "shaft": 1})},
           weights={"head": 3, "shaft": 2, "binding": 1}, time=3),
    Recipe("campfire", "Campfire", "A fire for light, warmth and cooking. Needs fuel and a spark (carry a flint).", 1,
           (Need("fuel", "Fuel", ("Branch",), 3, (("combustibility", 3.0),)),), "fire", defs.CAMPFIRE, is_placeable=True,
           designation="fuel", time=2),
    Recipe("torch", "Torch", "Wood and a fibre wick: a small light that burns for a while.", 1,
           (Need("handle", "Handle", ("Branch",), 1, (("combustibility", 3.0),)),
            Need("wick", "Wick", ("Fibre",), 1, (("flammability", 4.0),))), "torch", defs.TORCH, is_placeable=True,
           designation="handle"),
    Recipe("flask", "Flask", "A hide flask. Use it next to a liquid to fill it, next to a lit fire to boil it, else to drink.", 1,
           (Need("hide", "Hide", ("Hide", "Leather"), 1, (("tenacity", 2.0),)),), "flask", defs.FLASK, designation="hide"),
    Recipe("hide_armor", "Hide armour", "Layers of hide bound with cord. Insulates too.", 1,
           (Need("body", "Body", ("Hide", "Leather"), 3, (("toughness", 2.0), ("tenacity", 3.0))),
            Need("binding", "Binding", ("Cord", "Fibre"), 1, (("tenacity", 3.0),))), "gear", defs.HIDE_ARMOR,
           rules=_ARMOR_RULES, designation="body", time=4),
    Recipe("bed", "Bed", "A frame and soft padding: sleep here to rest in warmth and safety.", 1,
           (Need("frame", "Frame", ("Branch",), 3, (("toughness", 4.0),)),
            Need("padding", "Padding", ("Fibre", "Hide", "Leather"), 2, (("insulation", 3.0),))), "placed", defs.BED,
           rules={"toughness": ("role", "frame"), "insulation": ("role", "padding")}, designation="frame", is_placeable=True, time=4),
    Recipe("floor", "Wooden floor", "A plank floor for open air: build it next to you, then walk out onto it.", 1,
           (Need("boards", "Boards", ("Branch",), 2, (("toughness", 3.0),)),), "floor", defs.WOODEN_FLOOR,
           designation="boards", is_placeable=True),
    Recipe("stairs", "Wooden stairs", "A staircase up to the layer above (the way down appears there too).", 1,
           (Need("boards", "Boards", ("Branch",), 4, (("toughness", 3.0),)),), "stairs", defs.WOODEN_STAIRS,
           designation="boards", is_placeable=True),
    Recipe("hammer", "Hammer", "A dense stone head on a handle: shapes and joins hard things.", 1,
           (Need("head", "Head", HEADS, 1, (("density", 5.0), ("toughness", 3.0))), handle(4.0), binding()), "gear",
           defs.HAMMER, rules=_TOOL_RULES, weights={"head": 3, "handle": 2, "binding": 1}, time=3),
    # ── 2. basic shelter and stations ────────────────────────────────────────────────────────────────────────────────
    Recipe("workbench", "Workbench", "A sturdy bench: lets you do careful assembly (and improves your work).", 2,
           (Need("frame", "Frame", ("Branch",), 4, (("toughness", 4.0),)),
            Need("binding", "Binding", ("Cord",), 1, (("tenacity", 3.0),))), "placed", defs.WORKBENCH,
           tools=("hammering",), rules={"toughness": ("role", "frame")}, designation="frame", is_placeable=True, time=5),
    Recipe("wall", "Wall", "A wall block from stone, brick or timber. Insulation and strength come from the material.", 2,
           (Need("block", "Block", ("Stone", "Brick", "Branch"), 2, (("toughness", 3.0), ("density", 3.0))),), "wall",
           defs.WALL_BLOCK, tools=("hammering",), rules={}, designation="block", is_placeable=True, time=3),
    Recipe("furnace", "Furnace", "A stone furnace: refines ore, fires clay and melts sand. Burns fuel from your pack.", 2,
           (Need("walls", "Walls", ("Stone", "Brick"), 5, (("hardness", 4.0),)),), "placed", defs.FURNACE,
           tools=("hammering",), designation="walls", is_placeable=True, time=6),
    # ── 3. refining (at a furnace) ──────────────────────────────────────────────────────────────────────────────────
    Recipe("smelt", "Smelt ore", "Burn ore in a furnace for a metal ingot. Harder metals need hotter fuel.", 3,
           (Need("ore", "Ore", ("Ore",), 2, (("hardness", 0.0),), (), (Family.STONE,)),), "process", defs.PIECE_INGOT,
           tools=("furnace",), heat=100.0, process="smelt", time=6, efficiency=False),
    Recipe("brick", "Fire bricks", "Fire clay in a furnace into hard, heat-resistant bricks.", 3,
           (Need("clay", "Clay", ("Clay",), 2),), "process", defs.PIECE_BRICK, tools=("furnace",), heat=60.0,
           min_temp=800.0, process="brick", yields=2, time=5, efficiency=False),
    Recipe("glass", "Glass", "Melt sand in a very hot furnace; it cools into glass.", 3,
           (Need("sand", "Sand", ("Sand",), 2, (("transparency", 1.0),)),), "process", defs.PIECE_GLASS, tools=("furnace",),
           heat=80.0, process="glass", time=5, efficiency=False),
    # ── 4. industrial parts ──────────────────────────────────────────────────────────────────────────────────────────
    Recipe("wire", "Wire", "Draw a conductive ingot into wire.", 4,
           (Need("metal", "Metal", ("Ingot",), 1, (("electrical_conductivity", 6.0),)),), "process", defs.PIECE_WIRE,
           tools=("workbench", "hammering"), process="wire", yields=3, time=3, efficiency=False),
    Recipe("hull_plate", "Hull plate", "Tough, dense plate for ship repair and heavy construction.", 4,
           (Need("plate", "Plate", ("Ingot",), 2, (("toughness", 6.0), ("density", 5.0))),), "made", defs.HULL_PLATE,
           tools=("workbench", "hammering"), rules={}, designation="plate", time=6),
    Recipe("lens", "Lens", "Ground glass: scanners, cameras and survey instruments need one.", 4,
           (Need("glass", "Glass", ("Glass",), 1, (("transparency", 6.0),)),), "made", defs.LENS,
           tools=("workbench",), designation="glass", time=4),
    Recipe("salvage_tool", "Salvage tool", "A pry-and-cut tool for taking constructed things apart for their parts.", 4,
           (Need("blade", "Blade", ("Ingot",), 1, (("hardness", 5.0), ("toughness", 4.0))), handle(4.0), binding()), "gear",
           defs.SALVAGE_TOOL, tools=("workbench", "hammering"), rules=_BLADE_RULES, designation="blade", time=5),
    Recipe("medkit", "Medkit", "Clean bandages and a vial of antiseptic: restores health.", 4,
           (Need("bandage", "Bandage", ("Fibre",), 2, (("tenacity", 3.0),)), Need("vial", "Vial", ("Glass",), 1)),
           "made", defs.MEDKIT, tools=("cutting",), designation="bandage", time=3),
    # ── 5. electronics and power ─────────────────────────────────────────────────────────────────────────────────────
    Recipe("circuit", "Circuit board", "Wire traces on an insulating board.", 5,
           (Need("board", "Board", ("Brick", "Glass"), 1, (), (("electrical_conductivity", 2.0),)),
            Need("traces", "Traces", ("Wire",), 2, (("electrical_conductivity", 6.0),))), "made", defs.CIRCUIT,
           tools=("workbench",), skill=(Skill.ENGINEERING, 2), rules={"electrical_conductivity": ("role", "traces")},
           designation="traces", time=6),
    Recipe("power_cell", "Power cell", "A radioactive core in a tough casing with wire leads.", 5,
           (Need("core", "Core", ("Ore",), 1, (("radioactivity", 6.0),)),
            Need("casing", "Casing", ("Ingot",), 1, (("toughness", 4.0),)),
            Need("leads", "Leads", ("Wire",), 1, (("electrical_conductivity", 6.0),))), "made", defs.POWER_CELL,
           tools=("workbench",), skill=(Skill.ENGINEERING, 2), rules={"radioactivity": ("role", "core")},
           designation="core", time=8),
    Recipe("survey_kit", "Survey kit", "A lens, a circuit and a frame: reveals biomes and sites around you.", 5,
           (Need("lens", "Lens", ("Lens",), 1), Need("circuit", "Circuit", ("Circuit board",), 1),
            handle(3.0, role="frame")), "made", defs.SURVEY_KIT, tools=("workbench",), skill=(Skill.ENGINEERING, 2),
           designation="circuit", time=6),
    Recipe("beacon", "Distress beacon", "A circuit, a power cell and a wire antenna: calls your sponsor's rescue ship once "
           "they trust you enough to send one.", 5,
           (Need("circuit", "Circuit", ("Circuit board",), 1), Need("cell", "Cell", ("Power cell",), 1),
            Need("antenna", "Antenna", ("Wire",), 1, (("electrical_conductivity", 5.0),))), "made", defs.BEACON,
           tools=("workbench",), skill=(Skill.ENGINEERING, 2), designation="circuit", time=6, efficiency=False),
    # ── 6. spacefaring ───────────────────────────────────────────────────────────────────────────────────────────────
    Recipe("nav_unit", "Navigation unit", "The brain of a ship: two circuits, a lens and a power cell.", 6,
           (Need("circuits", "Circuits", ("Circuit board",), 2), Need("lens", "Lens", ("Lens",), 1),
            Need("cell", "Cell", ("Power cell",), 1)), "made", defs.NAV_UNIT, tools=("workbench",),
           skill=(Skill.ENGINEERING, 3), designation="circuits", time=10, efficiency=False),
    Recipe("omnitool", "Omnitool", "Cuts, digs, hammers and salvages: one tool for everything.", 6,
           (Need("circuit", "Circuit", ("Circuit board",), 1), Need("cell", "Cell", ("Power cell",), 1),
            Need("body", "Body", ("Ingot",), 2, (("hardness", 5.0), ("toughness", 4.0)))), "gear", defs.OMNITOOL,
           tools=("workbench", "hammering"), skill=(Skill.ENGINEERING, 3), rules={},
           designation="body", time=10),
]

BY_KEY: Dict[str, Recipe] = {r.key: r for r in RECIPES}
assert len(BY_KEY) == len(RECIPES), "duplicate recipe key"


def validate_recipes() -> None:
    """Static consistency checks (also run by the tests): known property names, tags, forms, builders."""
    import capabilities
    import materials
    forms = {k.object_type for k in defs.ITEM_KINDS.values()} | {"Branch", "Hide", "Leather", "Fibre"}
    builders = {"gear", "made", "placed", "fire", "torch", "floor", "stairs", "wall", "flask", "process"}
    for r in RECIPES:
        assert r.builder in builders, f"{r.key}: unknown builder {r.builder}"
        assert r.needs, f"{r.key}: no needs"
        roles = [n.role for n in r.needs]
        assert len(set(roles)) == len(roles), f"{r.key}: duplicate role"
        for n in r.needs:
            assert n.count >= 1
            for f in n.forms:
                assert f in forms, f"{r.key}: unknown form {f}"
            for prop, _ in n.minimum + n.maximum:
                assert prop in materials.PROPERTY_KEYS, f"{r.key}: unknown property {prop}"
        for tag in r.tools:
            assert tag in capabilities.TAGS, f"{r.key}: unknown tool tag {tag}"
        if r.builder != "process" and r.builder not in ("flask",):
            assert r.result is not None, f"{r.key}: no result kind"
        if r.builder == "process":
            assert r.process and r.result is not None
        for prop, (rule, arg) in r.rules.items():
            assert prop in materials.PROPERTY_KEYS, f"{r.key}: unknown derived property {prop}"
            roles_used = [arg] if rule == "role" else list(arg)
            assert all(role in roles for role in roles_used), f"{r.key}: rule for {prop} names an unknown role"
        if r.heat:
            assert "furnace" in r.tools, f"{r.key}: heat needs a furnace"
        assert r.designation in roles or r.builder in ("process", "flask"), f"{r.key}: designation role missing"
