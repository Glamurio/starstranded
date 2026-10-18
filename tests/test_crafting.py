"""Property-based crafting: thresholds, derived properties, resource accounting, efficiency, refining, acquisition paths."""
import pytest

import acquisition
import capabilities
import crafting
import exceptions
import materials
import recipes
import species as defs
from capabilities import grants
from items import Gear, Made, Stuff
from materials import Family
from material_helpers import make_material
from planet import generate_planet
from skills import Skill, skills


def piece(kind, material, inventory):
    item = crafting.make_piece(kind, material)
    inventory.add(item)
    return item


@pytest.fixture
def player(small_world):
    e = small_world()
    inv = e.player.inventory
    for item in list(inv.items):
        inv.remove(item)
    inv.capacity = 40
    e.player.equipment.weapon = e.player.equipment.armor = None
    return e.player


FLINT = make_material("flint", Family.STONE, hardness=8.5, toughness=3, density=6, abrasivity=5)
SOFT = make_material("chalk", Family.STONE, hardness=3, toughness=3, density=4, abrasivity=6)
OAK = make_material("oak", Family.WOOD, hardness=4, toughness=6.5, tenacity=4, density=4, flammability=6, combustibility=6,
                    burn_yield=45.0, burn_duration=8)
REED = make_material("reed", Family.FIBER, toughness=2.5, tenacity=6.5, insulation=3, flammability=7, combustibility=4,
                     burn_yield=10.0, burn_duration=3)


def stock_hatchet(player, head=FLINT):
    inv = player.inventory
    piece(defs.PIECE_STONE, head, inv)
    piece(defs.BRANCH, OAK, inv)
    piece(defs.PIECE_FIBER, REED, inv)


def test_recipe_catalogue_is_valid():
    recipes.validate_recipes()
    capabilities.validate_content()


def test_a_head_that_is_too_soft_is_rejected_with_the_reason(player):
    stock_hatchet(player, SOFT)
    plan = crafting.check(recipes.BY_KEY["hatchet"], player)
    assert not plan.ok
    assert any("hardness >= 6" in reason for reason in plan.reasons)
    with pytest.raises(exceptions.Impossible):
        crafting.craft(recipes.BY_KEY["hatchet"], player)
    assert len(player.inventory.items) == 3  # nothing consumed


def test_hatchet_is_made_from_the_chosen_parts_and_inherits_their_properties(player):
    stock_hatchet(player)
    (axe,) = crafting.craft(recipes.BY_KEY["hatchet"], player)
    assert isinstance(axe, Gear) and axe.damage_type.value == "sharp"
    assert axe.parts["head"] is FLINT and axe.parts["handle"] is OAK
    assert axe.props["hardness"] == pytest.approx(FLINT.hardness * axe.quality)  # head dominates hardness
    assert axe.props["toughness"] == pytest.approx(min(FLINT.toughness, OAK.toughness) * axe.quality)  # weakest link
    assert "flint" in axe.get_title().lower() and "hatchet" in axe.get_title().lower()
    assert axe.dull and "dull" in axe.get_title()
    assert axe in player.inventory.items and len(player.inventory.items) == 1  # parts consumed


def test_dull_tool_hits_weaker_until_sharpened_on_a_whetstone(player):
    import actions
    stock_hatchet(player)
    (axe,) = crafting.craft(recipes.BY_KEY["hatchet"], player)
    dull_power = axe.power_bonus
    with pytest.raises(exceptions.Impossible):
        actions.SharpenAction(player, axe).perform()  # no whetstone yet
    piece(defs.PIECE_STONE, SOFT, player.inventory)  # abrasivity 6
    actions.SharpenAction(player, axe).perform()
    assert not axe.dull and axe.power_bonus > dull_power


def test_better_material_gives_a_better_weapon(player):
    iron = make_material("ironish", Family.METAL, hardness=7, toughness=7.5, tenacity=7.5, density=7.5)
    inv = player.inventory
    for head in (FLINT, iron):
        piece(defs.PIECE_STONE if head is FLINT else defs.PIECE_INGOT, head, inv)
    piece(defs.BRANCH, OAK, inv); piece(defs.BRANCH, OAK, inv)
    piece(defs.PIECE_FIBER, REED, inv); piece(defs.PIECE_FIBER, REED, inv)
    weak = crafting.craft(recipes.BY_KEY["hatchet"], player, {"head": FLINT.id})[0]
    strong = crafting.craft(recipes.BY_KEY["hatchet"], player, {"head": iron.id})[0]
    assert strong.delivery() > weak.delivery()
    assert strong.props["toughness"] > weak.props["toughness"]


def test_unmet_tools_and_skill_are_listed(player):
    plan = crafting.check(recipes.BY_KEY["circuit"], player)
    texts = " | ".join(plan.reasons)
    assert "workbench" in texts and "Engineering 2" in texts


def test_race_efficiency_trims_counts_but_never_thresholds_or_below_one(player):
    player.extra_grants = grants("improved_crafting")
    stairs = recipes.BY_KEY["stairs"]
    plan = crafting.check(stairs, player)
    assert plan.counts["boards"] == 3  # 4 * 0.75
    for r in recipes.RECIPES:
        for need in r.needs:
            assert crafting.scaled_count(r, need, player) >= 1
    inv = player.inventory
    for _ in range(3):
        piece(defs.BRANCH, OAK, inv)
    crafting.craft(stairs, player)
    assert not [i for i in inv.items if i.object_type == "Branch"]
    # a branch that fails the toughness threshold is still refused
    weak_wood = make_material("pulp", Family.WOOD, toughness=1, hardness=1, density=1)
    for _ in range(3):
        piece(defs.BRANCH, weak_wood, inv)
    assert not crafting.check(stairs, player).ok


def test_cord_from_fibre_and_inventory_full_check(player):
    inv = player.inventory
    piece(defs.PIECE_FIBER, REED, inv); piece(defs.PIECE_FIBER, REED, inv)
    (cord,) = crafting.craft(recipes.BY_KEY["cord"], player)
    assert cord.form == "Cord" and cord.substance is REED and len(inv.items) == 1


def test_substances_are_never_mixed_inside_one_role(player):
    inv = player.inventory
    other = make_material("ash", Family.WOOD, hardness=4, toughness=6, tenacity=4, density=4, flammability=6, combustibility=6,
                          burn_yield=40.0, burn_duration=8)
    piece(defs.BRANCH, OAK, inv); piece(defs.BRANCH, other, inv); piece(defs.BRANCH, OAK, inv); piece(defs.BRANCH, other, inv)
    plan = crafting.check(recipes.BY_KEY["stairs"], player)  # needs 4 of one wood: only 2 + 2 here
    assert not plan.ok
    piece(defs.BRANCH, OAK, inv); piece(defs.BRANCH, OAK, inv)
    plan = crafting.check(recipes.BY_KEY["stairs"], player)
    assert plan.ok and {m.id for m in plan.parts.values()} == {OAK.id}


@pytest.mark.parametrize("seed", range(1, 9))
def test_every_recipe_has_an_acquisition_path_on_every_planet(seed):
    planet = generate_planet(seed)
    done, pieces, tags = acquisition.reachable(planet)
    missing = [r.key for r in recipes.RECIPES if r.key not in done]
    assert not missing, f"seed {seed}: unreachable {missing}"


def test_acquisition_check_notices_a_missing_resource():
    planet = generate_planet(3)
    # a planet whose only metals are soft cannot make hull plates: emulate by stripping hard metals
    from dataclasses import replace
    soft = tuple((k, m.replace(hardness=1, toughness=1) if m.family is Family.METAL else m) for k, m in planet.materials)
    done, _, _ = acquisition.reachable(replace(planet, materials=soft))
    assert "hull_plate" not in done
