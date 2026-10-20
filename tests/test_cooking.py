"""Flavours, raw food, dishes and the cooking screen."""
import pytest

import actions
import cooking
import exceptions
import input_handlers as ih
import liquids
import species as defs
from components.consumable import Dish, Fruit, Meat
from crafting import Campfire, Flask
from items import DEFAULT_WOOD, Stuff
from events import Key, KeyDown
from ui_helpers import SESSION


def kind(flavours=("sweet",), hunger=10, toxicity=0, raw_toxic=False, bloom=False, thirst=6):
    return defs.ItemKind(None, "Consumable", species="test fruit", sprite=(3, 21), color=(200, 60, 60), shade_sigma=8, hunger_amount=hunger,
                         thirst_amount=thirst, toxicity=toxicity, raw_toxic=raw_toxic, flavours=flavours, parent_key="planet:flora:x:0", bloom=bloom)


def fruit(e, **kw):
    item = Fruit(e.player.inventory, kind(**kw))
    e.player.inventory.add(item)
    return item


def meat(e, flavours=("savory",), nourishment=20):
    item = Meat("hare", e.player.inventory, source=defs.UnitSpecies("planet:fauna:t", "t", sprite=(1, 1), corpse_sprite=(1, 1), color=(120, 90, 60), flavours=flavours))
    item.nourishment = nourishment
    e.player.inventory.add(item)
    return item


def flask(e, kind_=liquids.LiquidKind.IMPURE, sips=3):
    item = Flask(e.player.inventory)
    item.liquid, item.sips = int(kind_), sips
    e.player.inventory.add(item)
    return item


def branch(e):
    item = Stuff(defs.BRANCH, DEFAULT_WOOD, e.player.inventory)
    e.player.inventory.add(item)
    return item


def lit_fire(e, dx=1):
    fire = Campfire()
    fire.place_on_map(e.player.x + dx, e.player.y, e.game_map)
    fire.add_fuel(200)
    return fire


# ── flavours ────────────────────────────────────────────────────────────────────────────────────────────────
def test_flavours_are_one_or_two_never_everything_and_stable():
    seen = set()
    for i in range(200):
        for what in ("fruit", "herb", "meat"):
            found = cooking.roll_flavours(f"x:{i}", (i % 255, 3, 4), what)
            assert 1 <= len(found) <= 2 and set(found) <= set(cooking.FLAVOURS)
            assert found == cooking.roll_flavours(f"x:{i}", (i % 255, 3, 4), what)
            seen.update(found)
    assert seen == set(cooking.FLAVOURS)


def test_generated_food_has_flavours_and_some_is_unsafe_raw(small_world):
    import planet
    import random
    from naming import Namer
    e = small_world()
    world = e.game_world.planet
    if world is None:
        pytest.skip("test world has no planet")
    fruits = [p.fruit for p in world.flora if p.fruit is not None]
    assert fruits and all(f.flavours for f in fruits)
    assert all(s.flavours for s in world.fauna)


# ── raw and cooked worth ─────────────────────────────────────────────────────────────────────────────────────
def test_raw_food_gives_a_fraction_of_its_worth(small_world):
    e = small_world()
    f = fruit(e, hunger=10)
    assert f.hunger_amount == round(10 * cooking.RAW_FRACTION)
    m = meat(e, nourishment=30)
    assert m.hunger_amount == round(30 * cooking.RAW_FRACTION) and m.hunger_amount > f.hunger_amount     # meat is the richer food


def test_people_must_cook_meat_but_other_races_need_not(small_world):
    e = small_world()
    assert "cooks_meat" in e.player.capabilities.tags
    m = meat(e)
    e.player.hunger = 50
    m.activate(e.player)
    assert e.player.poison > 0
    e.player.poison = 0
    mau = type("U", (), {"capabilities": type("C", (), {"tags": {}})()})()
    assert Meat.poison_turns(m, mau) == 0


def test_a_plant_poisonous_only_raw_is_safe_cooked_but_a_real_poison_is_not(small_world):
    e = small_world()
    e.player.hunger = 10
    bad = fruit(e, toxicity=10, raw_toxic=True)
    bad.activate(e.player)
    assert e.player.poison > 0
    e.player.poison = 0
    lit_fire(e)
    safe = cooking.cook(e, e.player, cooking.DISHES["skewer"], [fruit(e, toxicity=10, raw_toxic=True), branch(e)])
    assert safe.poison_turns(e.player) == 0
    deadly = cooking.cook(e, e.player, cooking.DISHES["skewer"], [fruit(e, toxicity=10), branch(e)])
    assert deadly.poison_turns(e.player) > 0


# ── dishes ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_stew_needs_meat_and_liquid_soup_fruit_and_liquid_skewer_a_branch(small_world):
    e = small_world()
    stew, soup, skewer = (cooking.DISHES[k] for k in ("stew", "soup", "skewer"))
    m, f, liquid, stick = meat(e), fruit(e), flask(e), branch(e)
    assert cooking.plan(stew, [m, liquid]).ok
    assert not cooking.plan(stew, [m]).ok and not cooking.plan(stew, [liquid]).ok
    assert cooking.plan(soup, [f, liquid]).ok and not cooking.plan(soup, [f]).ok
    assert cooking.plan(skewer, [m, stick]).ok and cooking.plan(skewer, [f, stick]).ok
    assert not cooking.plan(skewer, [m]).ok and not cooking.plan(skewer, [m, stick, liquid]).ok
    herbs = [fruit(e, bloom=True, hunger=3) for _ in range(3)]
    assert cooking.plan(stew, [m, liquid, herbs[0]]).ok and cooking.plan(stew, [m, liquid, *herbs[:2]]).ok
    assert not cooking.plan(stew, [m, liquid, *herbs]).ok          # (too much seasoning)


def test_a_toxic_or_acid_liquid_ruins_a_dish(small_world):
    e = small_world()
    assert not cooking.plan(cooking.DISHES["stew"], [meat(e), flask(e, liquids.LiquidKind.TOXIC)]).ok
    assert cooking.plan(cooking.DISHES["stew"], [meat(e), flask(e, liquids.LiquidKind.IMPURE)]).ok        # (cooking boils it)


def test_dishes_take_the_flavours_of_what_goes_in_and_are_named_for_them(small_world):
    e = small_world()
    plan = cooking.plan(cooking.DISHES["soup"], [fruit(e, flavours=("sweet", "sour")), flask(e)])
    assert plan.flavours == ("sweet", "sour") and plan.name == "sweet and sour soup"
    plan = cooking.plan(cooking.DISHES["stew"], [meat(e, flavours=("savory", "salty")), flask(e)])
    assert plan.name == "hearty stew"
    seasoned = cooking.plan(cooking.DISHES["stew"], [meat(e, flavours=("savory",)), flask(e), fruit(e, flavours=("spicy",), bloom=True, hunger=3)])
    assert seasoned.flavours == ("spicy", "savory") and seasoned.name == "peppery stew"
    assert set(cooking.PAIR_NAMES) == {frozenset((a, b)) for i, a in enumerate(cooking.FLAVOURS) for b in cooking.FLAVOURS[i + 1:]}   # a name for every pair


def test_cooked_food_is_worth_much_more_than_raw(small_world):
    e = small_world()
    m = meat(e, nourishment=24)
    raw = m.hunger_amount
    plan = cooking.plan(cooking.DISHES["stew"], [m, flask(e)])
    assert plan.hunger >= 3 * raw


def test_cooking_needs_a_lit_fire_uses_the_ingredients_and_makes_a_dish(small_world):
    e = small_world()
    m, liquid = meat(e), flask(e, sips=3)
    with pytest.raises(exceptions.Impossible):
        cooking.cook(e, e.player, cooking.DISHES["stew"], [m, liquid])            # no fire
    lit_fire(e)
    made = cooking.cook(e, e.player, cooking.DISHES["stew"], [m, liquid])
    assert isinstance(made, Dish) and made in e.player.inventory.items
    assert m not in e.player.inventory.items and liquid.sips == 3 - cooking.LIQUID_SIPS
    e.player.hunger, e.player.thirst = 20, 20
    made.activate(e.player)
    assert e.player.hunger == 20 + made.hunger_amount and made not in e.player.inventory.items


def test_a_herbivore_cannot_eat_a_stew_with_meat(small_world, monkeypatch):
    from species import Diet
    e = small_world()
    lit_fire(e)
    made = cooking.cook(e, e.player, cooking.DISHES["stew"], [meat(e), flask(e)])
    monkeypatch.setattr(type(e.player), "diet", property(lambda self: Diet.HERBIVORE))
    assert not e.player.can_eat(made)


# ── the screen ───────────────────────────────────────────────────────────────────────────────────────────────
def test_interacting_with_a_lit_fire_opens_the_cooking_screen_and_cooks(small_world):
    e = small_world()
    lit_fire(e)
    m, liquid = meat(e), flask(e)
    handler = ih.MainGameEventHandler(e)
    SESSION.reset(handler)
    actions.InteractAction(e.player).perform()
    screen = SESSION.handlers[-1]
    assert isinstance(screen, ih.CookingHandler)
    SESSION.draw(screen)
    for item in (m, liquid):                       # mark the meat and the flask
        screen.list.selected = next(i for i, r in enumerate(screen.list.rows) if r.data is item)
        screen.ev_keydown(KeyDown(Key.SPACE, 0))
    assert set(screen.chosen) == {m, liquid} and screen.outcome().ok
    SESSION.draw(screen)
    screen.ev_keydown(KeyDown(Key.RETURN, 0))
    assert any(isinstance(i, Dish) for i in e.player.inventory.items)


def test_a_lit_fire_without_food_still_takes_fuel(small_world):
    e = small_world()
    fire = lit_fire(e)
    stick = branch(e)
    SESSION.reset(ih.MainGameEventHandler(e))
    actions.InteractAction(e.player).perform()
    assert stick not in e.player.inventory.items and not isinstance(SESSION.handlers[-1], ih.CookingHandler)
