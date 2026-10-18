"""Damage types: resolution, weapons, resistances and felling plants."""
import pytest

import actions
import exceptions
from components.equippable import Axe
from components.plant import Shrub, Tree
from components.unit import Animal
from crafting import Branch, WoodenSpear
from recipes import RECIPES
from damage import DamageType, resolve


def test_resolve_applies_defense_then_multiplier():
    assert resolve(6, 1, DamageType.SHARP) == 5
    assert resolve(6, 0, DamageType.BLUNT, ((DamageType.BLUNT, 0.5),)) == 3
    assert resolve(2, 0, DamageType.BLUNT, ((DamageType.BLUNT, 0.1),)) == 1  # anything that gets through does 1
    assert resolve(9, 0, DamageType.PIERCE, ((DamageType.PIERCE, 0.0),)) == 0  # immune
    assert resolve(1, 3, DamageType.SHARP) == 0  # defense soaks it up


def wield(unit, weapon):
    unit.inventory.add(weapon)
    unit.equipment.toggle_equip(weapon, add_message=False)


def unwield(unit):
    unit.equipment.toggle_equip(unit.equipment.weapon, add_message=False)


def test_weapons_set_the_damage_type(small_world):
    e = small_world()
    p = e.player
    assert p.damage_type is DamageType.SHARP  # the starting dagger
    unwield(p)
    assert p.damage_type is DamageType.BLUNT  # fists
    wield(p, WoodenSpear(p.inventory))
    assert p.damage_type is DamageType.PIERCE


def tree_next_to_player(e):
    t = Tree(); t.place(e.player.x + 1, e.player.y, e.game_map)
    return t


def test_bare_hands_bump_into_a_tree_instead_of_attacking(small_world):
    e = small_world()
    unwield(e.player)
    t = tree_next_to_player(e)
    with pytest.raises(exceptions.Impossible):
        actions.BumpAction(e.player, t.x, t.y).perform()
    assert t.hp == t.max_hp


def test_an_axe_fells_a_tree_by_bumping(small_world):
    e = small_world()
    p = e.player
    unwield(p)
    wield(p, Axe(p.inventory))
    t = tree_next_to_player(e)
    hits = 0
    while not t.dead:
        actions.BumpAction(p, t.x, t.y).perform()
        hits += 1
        assert hits < 12
    assert 3 <= hits <= 7
    assert e.game_map.is_walkable(t.x, t.y) and (t.x, t.y) != (p.x, p.y)
    assert any(isinstance(i, Branch) for i in e.game_map.get_entities_at_location(t.x, t.y))
    from index_helpers import assert_index_consistent
    assert_index_consistent(e.game_map)


def test_trees_shrug_off_blunt_and_pierce_much_better_than_sharp(small_world):
    e = small_world()
    t = Tree()
    sharp = resolve(6, 0, DamageType.SHARP, t.resistances())
    blunt = resolve(6, 0, DamageType.BLUNT, t.resistances())
    pierce = resolve(6, 0, DamageType.PIERCE, t.resistances())
    assert sharp > pierce > blunt >= 1


def test_melee_on_a_shrub_hurts_it(small_world):
    e = small_world()
    s = Shrub(); s.place(e.player.x + 1, e.player.y, e.game_map)
    actions.MeleeAction(e.player, s.x, s.y).perform()
    assert s.hp < s.max_hp


def test_animals_hit_with_their_natural_type(small_world):
    e = small_world()
    a = Animal()
    assert a.damage_type is DamageType.BLUNT


def test_hatchet_is_craftable_from_head_handle_and_binding():
    hatchet = next(r for r in RECIPES if r.key == "hatchet")
    assert set(hatchet.ingredients) == {"head", "handle", "binding"}
