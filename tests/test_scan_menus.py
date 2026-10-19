"""Scanning from the menus: bodies and meat can be read, S scans and D drops in an inventory, and identical things stack."""
import actions
import events
import input_handlers as ih
import lore
import widgets
from components.consumable import Meat
from components.unit import Unit
from test_lore import new_game


def place_creature(engine, dx=2):
    """A creature of one of the planet's own species (the test hopper of `test_lore` is not one)."""
    kind = engine.game_world.planet.fauna[0]
    animal = Unit(kind)
    animal.place(engine.player.x + dx, engine.player.y, engine.game_map)
    return animal, kind


def kill(engine, animal):
    animal.die(engine.player, quiet=True)


def test_a_dead_creature_can_still_be_scanned():
    engine = new_game()
    animal, kind = place_creature(engine, 2)
    kill(engine, animal)
    assert not animal.is_alive
    found = lore.subject_of(engine, animal)
    assert found is not None and found[1] == kind.name
    result = lore.scan(engine, animal.x, animal.y)
    assert result is not None and result[1]


def test_meat_teaches_about_the_animal_it_came_from():
    engine = new_game()
    animal, kind = place_creature(engine, 2)
    kill(engine, animal)
    meat = next(i for i in animal.inventory.items if isinstance(i, Meat))
    found = lore.subject_of(engine, meat)
    assert found is not None and found[0] == lore.species_subject(kind)


def test_scan_thing_reads_an_item_in_the_pack_and_takes_a_turn():
    engine = new_game()
    animal, _ = place_creature(engine, 2)
    kill(engine, animal)
    meat = next(i for i in animal.inventory.items if isinstance(i, Meat))
    engine.player.inventory.add(meat, force=True)
    before = len(engine.message_log.messages)
    actions.ScanThingAction(engine.player, meat).perform()
    assert any("Scanner:" in m.plain_text for m in engine.message_log.messages[before:])


def test_identical_items_stack_into_one_row():
    engine = new_game()
    items = []
    for _ in range(3):
        a, _ = place_creature(engine, 2)
        kill(engine, a)
        items += [i for i in a.inventory.items if isinstance(i, Meat)][:1]
    assert len({i.get_title() for i in items}) == 1                # three pieces of the same animal's meat
    rows = [r for r in widgets.item_rows(items) if not r.header]
    assert len(rows) == 1 and rows[0].label.endswith(" x3") and rows[0].data is items[0]


def test_s_scans_and_d_drops_from_the_players_inventory():
    engine = new_game()
    animal, _ = place_creature(engine, 2)
    kill(engine, animal)
    meat = next(i for i in animal.inventory.items if isinstance(i, Meat))
    player = engine.player
    player.inventory.add(meat, force=True)
    handler = ih.InventoryActivateHandler(engine, player.inventory)
    engine.session.reset(handler)
    from ui_helpers import SESSION
    SESSION.draw(handler)
    handler.menu_i = handler.inventory_entries.index(meat)
    assert isinstance(handler.ev_keydown(events.KeyDown(events.Key.S, 0)), actions.ScanThingAction)
    drop = handler.ev_keydown(events.KeyDown(events.Key.D, 0))
    assert isinstance(drop, actions.DropItem)
    drop.perform()
    assert meat not in player.inventory.items


def test_d_does_nothing_in_someone_elses_inventory_but_s_scans():
    engine = new_game()
    animal, _ = place_creature(engine, 2)
    kill(engine, animal)
    handler = ih.InventoryLootHandler(engine, engine.player, animal.inventory)
    engine.session.reset(handler)
    from ui_helpers import SESSION
    SESSION.draw(handler)
    handler.menu_i = 0
    assert handler.ev_keydown(events.KeyDown(events.Key.D, 0)) is None
    assert isinstance(handler.ev_keydown(events.KeyDown(events.Key.S, 0)), actions.ScanThingAction)


def test_d_drops_the_whole_stack_in_one_turn():
    engine = new_game()
    player = engine.player
    kind = engine.game_world.planet.fauna[0]
    meats = []
    for dx in (2, 3, 4):
        a = Unit(kind)
        a.place(player.x + dx, player.y, engine.game_map)
        kill(engine, a)
        meats += [i for i in a.inventory.items if isinstance(i, Meat)][:1]
    for meat in meats:
        player.inventory.add(meat, force=True)
    handler = ih.InventoryActivateHandler(engine, player.inventory)
    engine.session.reset(handler)
    from ui_helpers import SESSION
    SESSION.draw(handler)
    handler.menu_i = handler.inventory_entries.index(meats[0])
    drop = handler.ev_keydown(events.KeyDown(events.Key.D, 0))
    assert isinstance(drop, actions.DropStack) and len(drop.items) == 3
    before = len(engine.message_log.messages)
    drop.perform()
    assert not any(m in player.inventory.items for m in meats)
    assert all((m.x, m.y) == (player.x, player.y) for m in meats)
    assert len(engine.message_log.messages) == before + 1          # one line for the whole stack
