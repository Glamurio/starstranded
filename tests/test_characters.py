"""Races, backgrounds, starting kits and the rules the race tags enforce."""
import numpy as np
import pytest

import actions
import characters
import exceptions
import lighting
import species as defs
import tile_types
from components.consumable import Fruit, Meat, Ration
from skills import Skill


def world_with(race="human", background="survivalist", width=14, height=10, liquid_at=None):
    from engine import Engine
    from world import GameMap, GameWorld
    player = characters.create_character("T", race, background)
    engine = Engine(player=player)
    engine.game_world = GameWorld(engine=engine, map_width=width, map_height=height,
                                  max_rooms=1, room_min_size=1, room_max_size=2)
    landscape = np.full((width, height), fill_value=tile_types.floor.get_array(), order="F", dtype=tile_types.tile_dt)
    engine.game_map = GameMap(engine, landscape, entities=[player])
    player.place(1, 1, engine.game_map)
    engine.game_map.explored[:] = True
    if liquid_at:
        x, y = liquid_at
        tile = engine.game_map.tile_at(x, y)
        tile["liquid"] = 1
        tile["depth"] = 1
        engine.game_map.set_tile(x, y, tile)
    engine.update_fov()
    return engine


def walk(engine, dx, dy, steps=1):
    p = engine.player
    for _ in range(steps):
        actions.MovementAction(p, p.x + dx, p.y + dy, [(p.x + dx, p.y + dy)]).perform()


# ── content ──────────────────────────────────────────────────────────────────────
def test_three_playable_races_with_lore_and_trade_offs():
    assert set(characters.RACES) == {"human", "selenite_people", "mau"}
    for info in characters.RACES.values():
        assert len(info.lore) > 80 and info.strengths and info.weaknesses


def test_backgrounds_requested_by_the_design_exist():
    for key in ("bounty_hunter", "biologist", "chemist", "surveyor", "salvager", "translator"):
        assert key in characters.BACKGROUNDS
    assert len(characters.BACKGROUNDS) >= 8


@pytest.mark.parametrize("race", sorted(characters.RACES))
@pytest.mark.parametrize("background", sorted(characters.BACKGROUNDS))
def test_every_combination_creates_a_valid_character(race, background):
    p = characters.create_character("T", race, background)
    bg = characters.BACKGROUNDS[background]
    for skill, level in bg.skills:
        assert p.skills.level(skill) == level
    for grant in bg.grants:
        assert p.capabilities.has(grant.tag)
    assert p.equipment.weapon is not None and p.equipment.armor is not None
    assert sum(isinstance(i, Ration) for i in p.inventory.items) == 3
    assert not p.inventory.is_full()


def test_background_kits_match_their_trade():
    bh = characters.create_character("T", "human", "bounty_hunter")
    assert any(i.kind is defs.PISTOL for i in bh.inventory.items)
    assert bh.capabilities.has("target_tracker")
    sv = characters.create_character("T", "human", "surveyor")
    assert any("surveying" in getattr(i, "tool_tags", ()) for i in sv.inventory.items)
    sal = characters.create_character("T", "human", "salvager")
    assert any("salvaging" in getattr(i, "tool_tags", ()) for i in sal.inventory.items)
    assert characters.create_character("T", "human", "translator").capabilities.has("universal_translator")
    assert characters.create_character("T", "human", "pilot").capabilities.has("pilot_training")


def test_nobody_starts_with_a_spark_flint_has_to_be_found():
    import items
    p = characters.create_character("T", "mau", "chemist")
    assert "firestarting" not in items.carried_tags(p)   # no issued ferro rod: a hard stone (flint) lies about and does it


# ── enforcement ──────────────────────────────────────────────────────────────────
def test_diet_is_enforced_per_race():
    meat, fruit = Meat("x"), Fruit()
    human = characters.create_character("T", "human").can_eat
    assert human(meat) and human(fruit)
    mau = characters.create_character("T", "mau").can_eat
    assert mau(meat) and not mau(fruit)
    sel = characters.create_character("T", "selenite_people").can_eat
    assert sel(fruit) and not sel(meat)
    for race in characters.RACES:
        assert characters.create_character("T", race).can_eat(Ration())


def test_mau_move_twice_as_fast_and_humans_at_normal_speed():
    e = world_with("mau")
    t0 = e.game_world.current_time
    walk(e, 1, 0, 8)
    assert e.game_world.current_time - t0 == 4  # eight steps in four turns
    h = world_with("human")
    h.game_world.current_time = 0
    h.game_map.has_sky = False
    t0 = h.game_world.current_time
    walk(h, 1, 0, 8)
    assert h.game_world.current_time - t0 >= 8


def test_humans_are_slowed_in_the_dark_and_not_in_daylight():
    e = world_with("human")
    e.game_map.has_sky = False  # no sky: always dark (ambient radius = night radius)
    assert lighting.is_dark_at(e)
    t0 = e.game_world.current_time
    walk(e, 1, 0, 4)
    assert e.game_world.current_time - t0 == 8
    e.game_map.has_sky = True
    e.game_world.current_time = int((0.5 - e.config.start_phase) % 1.0 * e.config.day_length)  # midday
    assert not lighting.is_dark_at(e)
    t0 = e.game_world.current_time
    walk(e, 1, 0, 4)
    assert e.game_world.current_time - t0 == 4


def test_a_lit_torch_removes_the_darkness_penalty():
    import crafting
    e = world_with("human")
    e.game_map.has_sky = False
    torch = crafting.Torch()
    torch.place_on_map(e.player.x + 1, e.player.y, e.game_map)
    torch.add_fuel(100)
    assert torch.emits_light
    assert not lighting.is_dark_at(e)


def test_mau_see_further_at_night_than_humans():
    seen = {}
    for race in ("human", "mau"):
        e = world_with(race, width=40, height=20)
        e.game_map.has_sky = False
        e.update_fov()
        seen[race] = int(e.game_map.window.ensure().visible.sum())
    assert seen["mau"] > seen["human"]


def test_liquid_averse_race_will_not_wade_but_can_be_pushed():
    e = world_with("mau", liquid_at=(2, 1))
    with pytest.raises(exceptions.Impossible):
        walk(e, 1, 0)
    assert (e.player.x, e.player.y) == (1, 1)
    e.player.move(2, 1)  # forced movement is not voluntary
    assert (e.player.x, e.player.y) == (2, 1)
    h = world_with("human", liquid_at=(2, 1))
    walk(h, 1, 0)
    assert (h.player.x, h.player.y) == (2, 1)


def test_liquid_averse_units_path_around_water():
    e = world_with("mau", liquid_at=(2, 1))
    path = e.get_path_to(e.player, 3, 1)
    assert path and (2, 1) not in path


def test_selenite_take_extra_blunt_damage_and_mau_have_claws():
    sel = characters.create_character("T", "selenite_people")
    from damage import DamageType
    assert sel.damage_multiplier(DamageType.BLUNT) == pytest.approx(1.5)
    assert sel.damage_multiplier(DamageType.SHARP) == 1.0
    mau = characters.create_character("T", "mau")
    human = characters.create_character("T", "human")
    human.equipment.weapon = None
    mau.equipment.weapon = None
    assert mau.power == human.power + 2


def test_selenite_harvest_more_and_tend_plants_faster():
    from components.consumable import Fruit
    e = world_with("selenite_people")
    p = e.player
    for item in list(p.inventory.items):
        p.inventory.remove(item)
    p.inventory.capacity = 40

    class FakePlant:
        category = actions.EntityCategory.PLANT
        growth_bonus = 0.0

        def __init__(self):
            self.inventory = type("Inv", (), {})()
        yield_piece = staticmethod(lambda: Fruit())

    plant = FakePlant()
    holder = type("Holder", (), {"parent": plant})()
    got = 0
    for _ in range(4):
        fruit = Fruit(holder)
        fruit.parent = holder
        holder.remove_entity = lambda item: None
        p.inventory.loot(fruit)
    got = len(p.inventory.items)
    assert got == 4 + 2  # +50% yield: two bonus fruit in four harvests
    assert plant.growth_bonus == pytest.approx(0.5)


def test_selenite_hold_breath_three_times_as_long():
    assert characters.create_character("T", "selenite_people").capabilities.stat("breath_turns") == pytest.approx(60)
    assert characters.create_character("T", "human").capabilities.stat("breath_turns") == pytest.approx(20)


def test_human_crafting_wastes_less():
    assert characters.create_character("T", "human").capabilities.stat("craft_cost") == pytest.approx(0.75)
    assert characters.create_character("T", "mau").capabilities.stat("craft_cost") == 1.0
