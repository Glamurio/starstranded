"""The crash site, the three escape routes and their endings."""
import random

import pytest

import actions
import characters
import endings
import exceptions
import setup_game
import species as defs
import sponsors
import structures
from items import Artifact, Made
from knowledge import Know
from skills import Skill


def new_game(seed=1, race="human", background="survivalist", sponsor="heavy_industries"):
    random.seed(seed)
    player = characters.create_character("T", race, background, sponsor=sponsor)
    return setup_game.new_game(player)


def things(engine, cls):
    return [e for e in engine.game_map.entities if isinstance(e, cls)]


def adjacent(engine, structure):
    """Put the player next to a structure."""
    p = engine.player
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if (dx or dy) and engine.game_map.is_walkable(structure.x + dx, structure.y + dy) \
                    and not engine.game_map.is_blocked(structure.x + dx, structure.y + dy):
                p.place(structure.x + dx, structure.y + dy, engine.game_map)
                return
    raise AssertionError("no free tile")


def stuff(player, key, count=1):
    for _ in range(count):
        player.inventory.add(structures.salvage_piece(key, player))


@pytest.mark.parametrize("seed", range(1, 9))
def test_every_planet_has_a_crash_site_near_the_spawn(seed):
    e = new_game(seed)
    ship, pod = things(e, structures.Ship), things(e, structures.CargoPod)
    wrecks = things(e, structures.Wreckage)
    assert len(ship) == 1 and len(pod) == 1 and len(wrecks) >= 4
    p = e.player
    assert max(abs(ship[0].x - p.x), abs(ship[0].y - p.y)) <= 15
    assert e.game_world.run.wreck == (ship[0].x, ship[0].y) and e.game_world.run.pod == (pod[0].x, pod[0].y)


def test_crash_site_and_ruin_layout_is_deterministic():
    a, b = new_game(3), new_game(3)
    assert [(e.x, e.y) for e in things(a, structures.Wreckage)] == [(e.x, e.y) for e in things(b, structures.Wreckage)]
    assert structures.ruin_chunks(77) == structures.ruin_chunks(77)
    assert len(set(structures.ruin_chunks(77).values())) == structures.RUIN_COUNT + 1


def test_wreckage_needs_a_tool_and_gives_parts_once():
    e = new_game(2)
    wreck = next(w for w in things(e, structures.Wreckage) if w.index == 1)  # hull section
    adjacent(e, wreck)
    p = e.player
    for item in list(p.inventory.items):
        if "cutting" in getattr(item, "tool_tags", ()) or "hammering" in getattr(item, "tool_tags", ()):
            p.inventory.remove(item)
    p.equipment.weapon = None
    with pytest.raises(exceptions.Impossible):
        wreck.interact(p, e)  # no tool
    characters.issue_item("salvage_tool", p)
    before = len(p.inventory.items)
    wreck.interact(p, e)
    assert sum(getattr(i.kind, "key", "") == "hull_plate" for i in p.inventory.items) == 2
    assert wreck.stripped and not wreck.blocks_movement
    with pytest.raises(exceptions.Impossible):
        wreck.interact(p, e)


def test_salvager_recovers_more():
    e = new_game(2, background="salvager")
    wreck = next(w for w in things(e, structures.Wreckage) if w.index == 1)
    adjacent(e, wreck)
    wreck.interact(e.player, e)
    assert sum(getattr(i.kind, "key", "") == "hull_plate" for i in e.player.inventory.items) == 3


def test_repair_route_end_to_end():
    e = new_game(4, background="pilot")
    p = e.player
    p.inventory.capacity = 60
    ship = things(e, structures.Ship)[0]
    adjacent(e, ship)
    with pytest.raises(exceptions.Impossible):
        ship.interact(p, e)  # nothing to fit yet
    stuff(p, "hull_plate", 2)
    cell = Made(defs.POWER_CELL, {"core": characters.ISSUE_STEEL}, 1.0, "power_cell", {}, {}, "core", parent=p.inventory)
    nav = Made(defs.NAV_UNIT, {"circuits": characters.ISSUE_CIRCUIT}, 1.0, "nav_unit", {}, {}, "circuits", parent=p.inventory)
    p.inventory.add(cell)
    p.inventory.add(nav)
    ship.interact(p, e)  # partial: fits what it can
    assert e.game_world.run.ending is None
    assert e.game_world.run.flags["ship"]["hull_plate"] == 2
    stuff(p, "hull_plate", 2)
    ship.interact(p, e)
    assert e.game_world.run.ending == "repair_flight"


def test_repair_needs_someone_who_can_fly():
    e = new_game(4, background="translator")
    p = e.player
    ship = things(e, structures.Ship)[0]
    adjacent(e, ship)
    e.game_world.run.flags["ship"] = {"hull_plate": 4, "nav_unit": 1, "power_cell": 1}
    assert not structures.can_fly(p)
    with pytest.raises(exceptions.Impossible):
        ship.interact(p, e)
    p.skills = p.skills.combine(__import__("skills").SkillSet({Skill.ENGINEERING: 4}))
    ship.interact(p, e)
    assert e.game_world.run.ending == "repair_flight"


def test_corporate_rescue_needs_trust_then_a_beacon_then_time():
    e = new_game(5)
    p = e.player
    run = e.game_world.run
    beacon = Made(defs.BEACON, {"circuit": characters.ISSUE_CIRCUIT}, 1.0, "beacon", {}, {}, "circuit", parent=p.inventory)
    p.inventory.add(beacon)
    with pytest.raises(exceptions.Impossible) as info:
        beacon.activate(p)
    assert "reputation" in info.value.args[0]
    run.reputation["heavy_industries"] = sponsors.RESCUE_REPUTATION
    run.completed = ["heavy_industries:0:0", "heavy_industries:1:0"]
    beacon.activate(p)
    assert beacon not in p.inventory.items and run.flags["rescue_due"] == e.game_world.current_time + endings.RESCUE_DELAY
    e.game_world.current_time += endings.RESCUE_DELAY - 1
    endings.tick(e)
    assert run.ending is None
    e.game_world.current_time += 1
    endings.tick(e)
    assert run.ending == "rescue_heavy_industries"


def test_each_sponsor_has_its_own_rescue_ending():
    for key in sponsors.SPONSORS:
        assert f"rescue_{key}" in endings.ENDINGS
    assert len(endings.ENDINGS) >= 8
    assert len({e.text for e in endings.ENDINGS.values()}) == len(endings.ENDINGS)


def visit(engine, x, y):
    """Load the chunk of a site, stand next to it and return it (far chunks unload when the player moves away)."""
    from chunks import chunk_key
    engine.game_map.load_chunk(chunk_key(x, y))
    site = next(t for t in engine.game_map.get_entities_at_location(x, y) if isinstance(t, structures.Structure))
    adjacent(engine, site)
    return site


def test_ancient_route_needs_three_keys_and_the_inscriptions_read():
    e = new_game(6, background="archaeologist")
    p = e.player
    p.inventory.capacity = 40
    p.skills = p.skills.combine(__import__("skills").SkillSet({Skill.LINGUISTICS: 3}))
    run = e.game_world.run
    for key in structures.ruin_chunks(e.game_world.master_seed):
        e.game_map.load_chunk(key)
    sites = dict(run.flags["sites"])
    assert set(sites) == {0, 1, 2, 3}
    gate = visit(e, *sites[3])
    assert isinstance(gate, structures.Gate)
    with pytest.raises(exceptions.Impossible):
        gate.interact(p, e)
    for index in range(3):
        ruin = visit(e, *sites[index])
        assert isinstance(ruin, structures.Ruin) and ruin.index == index
        ruin.interact(p, e)
        assert run.knowledge.level(f"ruin:{index}", "inscription") is Know.FULL  # skill 3 + scanner 1 reads difficulty 3-4
    assert sum(isinstance(i, Artifact) and i.is_key for i in p.inventory.items) == 3
    gate = visit(e, *sites[3])
    gate.interact(p, e)
    assert run.ending == "ancient_gate"


def test_a_stranger_has_to_study_the_glyphs_before_reading_them():
    e = new_game(6, background="chemist")
    p = e.player
    ruin = structures.Ruin(0)
    e.game_map.add_entity(ruin, p.x, p.y + 1)
    run = e.game_world.run
    ruin.interact(p, e)
    assert run.knowledge.level("ruin:0", "inscription") is not Know.FULL
    for _ in range(25):
        e.game_world.current_time += structures.STUDY_COOLDOWN   # study sessions are spaced out
        ruin.interact(p, e)
    assert run.knowledge.level("ruin:0", "inscription") is Know.FULL
    assert p.skills.level(Skill.LINGUISTICS) >= 2


def test_pressing_f_at_the_stone_does_not_grind_the_skill():
    e = new_game(6, background="chemist")
    p = e.player
    ruin = structures.Ruin(0)
    e.game_map.add_entity(ruin, p.x, p.y + 1)
    for _ in range(8):                       # each visit costs a few turns, well under the cooldown
        ruin.interact(p, e)
    assert p.skill_practice.get(Skill.LINGUISTICS, 0) <= 1


def test_epilogue_describes_the_run():
    e = new_game(7)
    endings.finish(e, "repair_flight")
    text = "\n".join(endings.epilogue(e))
    assert "Under Your Own Power" in text and "survived" in text
