"""Characterization: inventory add / drop / loot / equip."""
import pytest

import actions
import exceptions
from components.consumable import Meat
import components.equippable as equip


def test_player_starts_with_dagger_and_armor_equipped(small_world):
    p = small_world().player
    names = sorted(i.object_type for i in p.inventory.items)
    assert names == ["Armor", "Dagger"]
    assert p.equipment.weapon is not None and p.equipment.armor is not None
    assert p.power == 2 + 2 and p.defense == 1 + 1


def test_add_until_full_raises_for_player(small_world):
    e = small_world()
    inv = e.player.inventory
    while not inv.is_full():
        inv.add(Meat("x", inv))
    assert len(inv.items) == inv.capacity == 20
    with pytest.raises(exceptions.Impossible):
        inv.add(Meat("x", inv))


def test_full_npc_inventory_silently_refuses(small_world):
    from animals import Animal
    e = small_world()
    a = Animal(); a.place(4, 4, e.game_map)
    for _ in range(12):
        a.inventory.add(Meat("x", a.inventory))
    assert len(a.inventory.items) == 10


def test_loot_moves_item_from_map_to_inventory(small_world):
    e = small_world()
    potion = Meat("x")
    potion.place(1, 1, e.game_map)
    assert potion in e.game_map.get_entities_at_location(1, 1)
    e.player.inventory.loot(potion)
    assert potion not in e.game_map.entities
    assert potion in e.player.inventory.items and potion.parent is e.player.inventory


def test_pickup_action_adds_message(small_world):
    e = small_world()
    potion = Meat("x"); potion.place(1, 1, e.game_map)
    actions.PickupAction(e.player, potion).perform()
    assert potion in e.player.inventory.items
    assert any("picked up" in m.plain_text for m in e.message_log.messages)


def test_drop_places_item_at_target_and_removes_from_inventory(small_world):
    e = small_world()
    meat = Meat("rabbit", e.player.inventory)
    e.player.inventory.add(meat)
    actions.DropItem(e.player, meat, (3, 3)).perform()
    assert meat not in e.player.inventory.items
    assert (meat.x, meat.y) == (3, 3) and meat.parent is e.game_map
    assert meat in e.game_map.get_entities_at_location(3, 3)


def test_drop_equipped_item_unequips_it(small_world):
    e = small_world()
    dagger = e.player.equipment.weapon
    actions.DropItem(e.player, dagger, (2, 2)).perform()
    assert e.player.equipment.weapon is None
    assert dagger.equipped is False


def test_equip_toggle_changes_power(small_world):
    e = small_world()
    p = e.player
    before = p.power
    spear_dagger = e.player.equipment.weapon
    actions.EquipAction(p, spear_dagger).perform()  # toggles off
    assert p.power == before - 2
    actions.EquipAction(p, spear_dagger).perform()  # toggles on
    assert p.power == before


def test_equipping_second_weapon_swaps_slot(small_world):
    e = small_world()
    p = e.player
    from animals import Spear as WoodenSpear
    spear = WoodenSpear(p.inventory)
    p.inventory.add(spear)
    p.equipment.toggle_equip(spear)
    assert p.equipment.weapon is spear
    assert p.power == 2 + 3


def test_food_consumption_restores_and_depletes(small_world):
    e = small_world()
    p = e.player
    p.hunger = 50
    meat = Meat("x", p.inventory); p.inventory.add(meat)
    meat.activate(p)
    assert p.hunger == 60 and meat not in p.inventory.items


def test_only_the_players_drops_are_announced(small_world):
    from components.consumable import Meat
    from animals import Animal
    e = small_world()
    rabbit = Animal(); rabbit.place(5, 5, e.game_map)
    meat = Meat("x", rabbit.inventory); rabbit.inventory.add(meat)
    before = len(e.message_log.messages)
    rabbit.inventory.drop(meat, (5, 6))
    assert len(e.message_log.messages) == before and meat.parent is e.game_map
    mine = Meat("y", e.player.inventory); e.player.inventory.add(mine)
    e.player.inventory.drop(mine, None)
    assert e.message_log.messages[-1].plain_text.startswith("You dropped")
