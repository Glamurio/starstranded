"""Gathering, mining, fire, refining and building in a real generated world."""
import numpy as np
import pytest

import actions
import crafting
import exceptions
import materials
import recipes
import resources
import species as defs
import tile_types
from items import Stuff
from material_helpers import make_material
from materials import Family
from components.equippable import Equippable


def clear(player):
    inv = player.inventory
    for item in list(inv.items):
        inv.remove(item)
    player.equipment.weapon = player.equipment.armor = None
    inv.capacity = 60


def give(player, kind, material):
    item = crafting.make_piece(kind, material)
    player.inventory.add(item)
    return item


@pytest.fixture
def game(new_engine):
    clear(new_engine.player)
    return new_engine


def planet(game):
    return game.game_world.planet


def find_wall(game, radius=12):
    world, p = game.game_map, game.player
    for r in range(2, radius):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                x, y = p.x + dx, p.y + dy
                if actions.is_rock_face(world, x, y):
                    return x, y
    raise AssertionError("no rock face nearby")


def move_next_to(game, x, y):
    world, p = game.game_map, game.player
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if world.is_walkable(x + dx, y + dy) and not world.is_blocked(x + dx, y + dy):
            p.place(x + dx, y + dy, world)
            return
    raise AssertionError("wall not reachable")


def stone_pickaxe(game, hardness=8.0):
    head = make_material("headstone", Family.STONE, hardness=hardness, toughness=3, density=6)
    wood = make_material("haft", Family.WOOD, toughness=6, tenacity=5, density=4, hardness=4, flammability=6, combustibility=6,
                         burn_yield=40.0, burn_duration=8)
    rope = make_material("rope", Family.FIBER, tenacity=7)
    from items import Gear
    pick = Gear(defs.PICKAXE, {"head": head, "handle": wood, "binding": rope}, 1.0, "pickaxe", dict(recipes.BY_KEY["pickaxe"].rules))
    game.player.inventory.add(pick)
    return pick


def test_loose_stones_lie_on_the_ground_and_are_real_materials(game):
    stones = [i for i in game.game_map.items if isinstance(i, Stuff) and i.form == "Stone"]
    assert stones, "no loose stones were scattered around the start"
    known = {m.id for _, m in planet(game).materials}
    assert all(s.substance.id in known for s in stones)


def test_mining_needs_a_tool_and_a_hard_enough_head(game):
    x, y = find_wall(game)
    move_next_to(game, x, y)
    with pytest.raises(exceptions.Impossible, match="pickaxe"):
        actions.MineAction(game.player, x, y).perform()
    stone_pickaxe(game, hardness=1.0)
    with pytest.raises(exceptions.Impossible, match="too soft"):
        actions.MineAction(game.player, x, y).perform()


def test_mining_opens_the_tile_and_yields_the_deposit(game):
    x, y = find_wall(game)
    move_next_to(game, x, y)
    stone_pickaxe(game, hardness=10.0)
    biome = resources.biome_key_at(game.game_world, 0, x, y)
    expected = resources.wall_material(planet(game), game.game_world.master_seed, 0, x, y, biome)
    before = len(game.player.inventory.items)
    actions.BumpAction(game.player, x, y).perform()  # bumping a wall with a mining tool mines it
    assert game.game_map.is_walkable(x, y)
    got = game.player.inventory.items[-1]
    assert isinstance(got, Stuff) and got.substance == expected
    assert len(game.player.inventory.items) == before + 1


def test_deposits_are_deterministic(game):
    x, y = find_wall(game)
    args = (planet(game), game.game_world.master_seed, 0, x, y, "grassland")
    assert resources.wall_material(*args) == resources.wall_material(*args)


def test_fire_needs_a_spark_and_fuel_and_burns_out(game):
    p = game.player
    fire = crafting.Campfire(p.inventory)
    p.inventory.add(fire)
    fire.place_on_map(p.x + 1, p.y, game.game_map)
    wood = make_material("fuelwood", Family.WOOD, flammability=6, combustibility=6, burn_yield=40.0, burn_duration=8, toughness=5)
    give(p, defs.BRANCH, wood)
    with pytest.raises(exceptions.Impossible, match="spark"):
        actions.InteractAction(p).perform()
    flint = make_material("sparkflint", Family.STONE, hardness=9, toughness=2)
    give(p, defs.PIECE_STONE, flint)
    actions.InteractAction(p).perform()
    assert fire.emits_light and fire.turns_left() == 7  # 8 turns of fuel, one spent lighting it
    now = game.game_world.current_time
    game.game_world.current_time = now + 9
    assert not fire.emits_light and not fire.is_lit


def test_hard_to_ignite_or_flashing_fuel_does_not_light_a_fire(game):
    p = game.player
    fire = crafting.Campfire(p.inventory); p.inventory.add(fire)
    fire.place_on_map(p.x + 1, p.y, game.game_map)
    give(p, defs.PIECE_STONE, make_material("sparkflint2", Family.STONE, hardness=9, toughness=2))
    wet = make_material("wetwood", Family.WOOD, flammability=0.5, combustibility=5, burn_yield=30.0, burn_duration=6, toughness=5)
    give(p, defs.BRANCH, wet)
    with pytest.raises(exceptions.Impossible, match="catch"):
        actions.InteractAction(p).perform()
    grass = make_material("quickgrass", Family.WOOD, flammability=9, combustibility=2, burn_yield=3.0, burn_duration=1, toughness=2)
    p.inventory.items[:] = [i for i in p.inventory.items if i.object_type != "Branch"]
    p.inventory.contents = p.inventory.items
    give(p, defs.BRANCH, grass)
    actions.InteractAction(p).perform()  # flashes and dies
    assert not fire.is_lit


def furnace_setup(game):
    p = game.player
    from items import Placed
    furnace = Placed(defs.FURNACE, {"walls": make_material("furn", Family.STONE, hardness=6)}, 1.0, "furnace")
    furnace.is_placed = True
    furnace.place(p.x + 1, p.y, game.game_map)
    return furnace


def test_smelting_needs_a_furnace_fuel_and_enough_heat(game):
    p = game.player
    pl = planet(game)
    ore_id = next(i for i in pl.ore_ids if pl.material(pl.material(i).refines_to).melting_point > 1400)  # the structural metal
    ore = pl.material(ore_id)
    for _ in range(2):
        give(p, defs.PIECE_ORE, ore)
    smelt = recipes.BY_KEY["smelt"]
    assert any("furnace" in r for r in crafting.check(smelt, p).reasons)
    furnace_setup(game)
    wood = make_material("smeltwood", Family.WOOD, flammability=6, combustibility=6, burn_yield=40.0, burn_duration=8, toughness=5)
    for _ in range(3):
        give(p, defs.BRANCH, wood)
    plan = crafting.check(smelt, p)
    assert not plan.ok and any("Furnace heat" in r for r in plan.reasons)  # wood is too cool for this metal
    coal = pl.material(pl.coal_id)
    give(p, defs.PIECE_COAL, coal)
    plan = crafting.check(smelt, p)
    assert plan.ok, plan.reasons
    (ingot,) = crafting.craft(smelt, p)
    assert ingot.form == "Ingot" and ingot.substance.family is Family.METAL
    assert not [i for i in p.inventory.items if i.form == "Ore"]
    assert not [i for i in p.inventory.items if i.form == "Coal"]  # the fuel burned


def test_glass_and_bricks_come_from_sand_and_clay(game):
    p = game.player
    pl = planet(game)
    furnace_setup(game)
    for _ in range(2):
        give(p, defs.PIECE_SAND, pl.material(pl.sand_id))
        give(p, defs.PIECE_CLAY, pl.material(pl.clay_id))
    for _ in range(3):
        give(p, defs.PIECE_COAL, pl.material(pl.coal_id))
    glass = crafting.craft(recipes.BY_KEY["glass"], p)[0]
    assert glass.substance.family is Family.GLASS and glass.substance.transparency > pl.material(pl.sand_id).transparency
    bricks = crafting.craft(recipes.BY_KEY["brick"], p)
    assert len(bricks) == 2 and bricks[0].substance.family is Family.CERAMIC


def test_wall_hit_points_follow_the_material_and_weapons_scale_by_material(game):
    p = game.player
    hard = make_material("granite", Family.STONE, hardness=8, toughness=7, density=8)
    soft = make_material("soapstone", Family.STONE, hardness=2, toughness=2, density=3)
    w_hard = crafting.Wall({"block": hard}, 1.0, {})
    w_soft = crafting.Wall({"block": soft}, 1.0, {})
    assert w_hard.max_hp > 3 * w_soft.max_hp
    for w, x in ((w_hard, p.x + 1), (w_soft, p.x - 1)):
        game.game_map.add_entity(w, x, p.y)
        assert not game.game_map.is_walkable(x, p.y) and not game.game_map.tile_at(x, p.y)["transparent"]
    # a wooden club dents soft stone much more than granite
    from items import Gear
    wood = make_material("clubwood", Family.WOOD, toughness=6, density=4, hardness=4, tenacity=4, flammability=5, combustibility=5, burn_yield=30.0, burn_duration=5)
    club = Gear(defs.CLUB, {"head": wood}, 1.0, "club", {"density": ("role", "head"), "toughness": ("role", "head")})
    p.inventory.add(club); p.equipment.toggle_equip(club, add_message=False)
    actions.MeleeAction(p, w_soft.x, w_soft.y).perform()
    actions.MeleeAction(p, w_hard.x, w_hard.y).perform()
    assert (w_soft.max_hp - w_soft.hp) > (w_hard.max_hp - w_hard.hp)


def test_a_wall_collapses_and_restores_the_tile(game):
    p = game.player
    mat = make_material("wallmat", Family.STONE, hardness=4, toughness=3, density=4)
    w = crafting.Wall({"block": mat}, 1.0, {})
    game.game_map.add_entity(w, p.x + 1, p.y)
    w.handle_health(-1000)
    assert w.dead and game.game_map.is_walkable(p.x + 1, p.y)
    assert game.game_map.tile_at(p.x + 1, p.y)["transparent"]


def test_shrubs_give_fibre_and_trees_wood(game):
    import components.plant as plants
    pl = planet(game)
    shrub_species = next(s for s in pl.flora if s.fiber is not None)
    tree_species = next(s for s in pl.flora if s.material is not None)
    s = plants.Shrub(shrub_species); t = plants.Tree(tree_species)
    assert isinstance(s.yield_piece(), Stuff) and s.yield_piece().form == "Fibre"
    assert t.yield_piece().substance is tree_species.material


def test_animals_drop_hide_of_their_species_material(game):
    from components.unit import Unit
    pl = planet(game)
    species = next(s for s in pl.fauna if s.hide is not None)
    a = Unit(species)
    game.game_map.add_entity(a, game.player.x + 3, game.player.y)
    a.die(game.player, quiet=True)
    hides = [i for i in a.inventory.items if isinstance(i, Stuff) and i.form == "Hide"]
    assert hides and hides[0].substance is species.hide


def test_digging_sand_and_clay(game):
    p = game.player
    # find a tile where the ground yields something (shore or sandy/clayey biome) by scanning around
    world = game.game_map
    found = None
    for dx in range(-30, 31):
        for dy in range(-30, 31):
            x, y = p.x + dx, p.y + dy
            tile = world.tile_at(x, y)
            if tile is not None and tile["walkable"] and not tile["liquid"] and not tile["stairs"]:
                if resources.ground_material(planet(game), game.game_world, world, x, y):
                    found = (x, y); break
        if found:
            break
    if not found:
        pytest.skip("no diggable ground within 30 tiles of this seed's start")
    p.place(*found, world)
    actions.GatherAction(p).perform()
    assert p.inventory.items[-1].form in ("Sand", "Clay")
