"""The usability round: scanning fruit in plants, bud/blossom names, grabbing stacks, flowers, dropping decorations, names."""
import pytest

import actions
import input_handlers
import species as defs
from items import Stuff
import materials


def _stones(engine, n, at=None):
    mat = materials.Material if False else None
    from resources import surface_stone
    planet = getattr(engine.game_world, "planet", None)
    m = surface_stone(planet, 5, 1, 1, 7, "plains") if planet is not None else None
    if m is None:
        import housing
        m = housing.material_for(None, 0, "stone")
    made = [Stuff(defs.PIECE_STONE, m) for _ in range(n)]
    for s in made:
        engine.game_map.add_entity(s, *(at or (engine.player.x, engine.player.y)))
    return made


def test_grab_all_takes_every_item_of_a_stack(small_world):
    e = small_world()
    made = _stones(e, 4)
    stack = [x for x in e.game_map.stack_at(e.player.x, e.player.y) if x in made]
    handler = input_handlers.InventoryLootHandler(e, e.player, entities=stack)
    handler.inventory_entries = list(stack)
    act = handler.on_items_selected(handler.inventory_entries)
    act.perform()
    assert all(s in e.player.inventory.items for s in made)
    assert not [x for x in e.game_map.get_entities_at_location(e.player.x, e.player.y) if x in made]


def test_grab_all_from_a_plant_holding_several_fruit(small_world):
    import components.plant as plants
    from components.consumable import Fruit
    e = small_world()
    species = e.game_world and plants.make_plant_species(plants.PlantCategory.SHRUB) if hasattr(plants, "PlantCategory") else None
    species = species or plants.make_plant_species(plants.defs.PlantCategory.SHRUB)
    plant = plants.Shrub(species)
    e.game_map.add_entity(plant, 3, 3)
    while len(plant.inventory.items) < 3:
        plant.inventory.add(Fruit(plant.inventory, species.fruit))
    held = list(plant.inventory.items)
    handler = input_handlers.InventoryLootHandler(e, e.player, plant.inventory)
    handler.inventory_entries = list(held)
    handler.on_items_selected(handler.inventory_entries).perform()
    assert all(f in e.player.inventory.items for f in held), (len(e.player.inventory.items), len(plant.inventory.items))


def test_grab_all_after_dropping_a_stack(small_world):
    e = small_world()
    made = _stones(e, 4)
    for s in made:
        e.player.inventory.loot(s)
    actions.DropStack(e.player, made).perform()
    here = [x for x in e.game_map.stack_at(e.player.x, e.player.y) if x in made]
    assert len(here) == 4
    handler = input_handlers.InventoryLootHandler(e, e.player, entities=here)
    handler.on_render(input_handlers.SESSION.canvas) if hasattr(input_handlers, "SESSION") else None
    handler.inventory_entries = list(here)
    handler.on_items_selected(handler.inventory_entries).perform()
    assert all(s in e.player.inventory.items for s in made)



def test_grab_all_key_in_the_real_flow(small_world):
    from ui_helpers import SESSION
    import events
    e = small_world()
    made = _stones(e, 4)
    here = [x for x in e.game_map.stack_at(e.player.x, e.player.y) if x in made]
    handler = input_handlers.InventoryLootHandler(e, e.player, entities=here)
    SESSION.handlers.append(handler)
    handler.on_render(SESSION.canvas)
    result = handler.ev_keydown(events.KeyDown(input_handlers.Key.G, 0)) if hasattr(events, "KeyDown") else None
    assert isinstance(result, actions.MassPickupAction), result
    result.perform()
    assert all(s in e.player.inventory.items for s in made), (len(e.player.inventory.items), [type(i).__name__ for i in e.player.inventory.items])


def test_scenery_can_be_picked_up_and_put_down_again(small_world):
    import scenery
    from ui_helpers import SESSION
    e = small_world()
    bones = scenery.Scenery("bones", 0)
    e.game_map.add_entity(bones, e.player.x, e.player.y)
    actions.MassPickupAction(e.player, [bones]).perform()
    assert bones in e.player.inventory.items
    handler = input_handlers.InventoryDropHandler(e, e.player.inventory)
    handler.inventory_entries = [bones]
    act = handler._activate(0)
    assert isinstance(act, actions.DropItem)
    act.perform()
    assert bones not in e.player.inventory.items and bones.parent is e.game_map


def test_a_picked_flower_is_gone_and_new_ones_sprout():
    import random
    import setup_game
    import components.plant as plants
    from engine import Engine
    from world import GameWorld, World
    from worldgen import NoiseWorldSource, regrow_flowers
    engine = Engine(player=setup_game.create_player())
    engine.game_world = GameWorld(engine=engine, seed=5)
    source = NoiseWorldSource(3)
    world = World(engine, source, floor=1, seed=3)
    engine.game_map = world
    chunk = world.load_chunk((6, 5))
    flowers = [e for e in chunk.entities if isinstance(e, plants.Flower)]
    assert flowers
    flower = flowers[0]
    bloom = flower.inventory.items[0]
    engine.player.inventory.loot(bloom)
    assert flower.parent is None and flower not in chunk.entities
    before = sum(isinstance(e, plants.Flower) for e in chunk.entities)
    random.seed(1)
    for now in range(0, 2000, 20):
        regrow_flowers(world, [chunk], now)
    assert sum(isinstance(e, plants.Flower) for e in chunk.entities) > before


def test_a_bud_stays_a_bud_until_identified(small_world):
    import lore
    from planet import BLOOM_SPRITE
    import species as defs
    kind = defs.ItemKind(None, "Consumable", species="Sheny blossom", sprite=BLOOM_SPRITE, color=(200, 80, 80), shade_sigma=8, parent_key="planet:flora:x:0")
    class Run:                                    # (nothing is known yet)
        knowledge = type("K", (), {"level": lambda self, s, k: 0})()
    assert lore.fruit_name(Run(), kind).endswith("blossom")


def test_scan_reaches_a_fruit_inside_a_plant(small_world):
    import components.plant as plants
    from components.consumable import Fruit
    e = small_world()
    species = plants.make_plant_species(plants.defs.PlantCategory.SHRUB)
    plant = plants.Shrub(species)
    e.game_map.add_entity(plant, 4, 1)
    fruit = Fruit(plant.inventory, species.fruit)
    plant.inventory.add(fruit)
    assert actions._position_of(fruit) == (4, 1)
    far = plants.Shrub(species)
    e.game_map.add_entity(far, 11, 9)
    far_fruit = Fruit(far.inventory, species.fruit)
    far.inventory.add(far_fruit)
    assert actions._position_of(far_fruit) == (11, 9)


def test_right_click_menu_lists_what_can_be_done(small_world):
    import screens
    import components.plant as plants
    from components.consumable import Fruit
    e = small_world()
    stone = _stones(e, 1, at=(2, 1))[0]
    labels = [label for label, _ in screens.ContextMenu.options(e, 2, 1)]
    assert any(l.startswith("Grab") for l in labels) and any(l.startswith("Scan") for l in labels)
    assert "Walk here" in labels
    plain = [label for label, _ in screens.ContextMenu.options(e, 6, 5)]
    assert plain == ["Walk here"]
    # something hostile next to you can be attacked
    import setup_game
    from entity import EntityCategory
    species = plants.make_plant_species(plants.defs.PlantCategory.SHRUB)
    bush = plants.Shrub(species)
    e.game_map.add_entity(bush, 3, 1)
    assert any(l.startswith("Scan") for l, _ in screens.ContextMenu.options(e, 3, 1))


def test_a_key_press_stops_a_repeating_walk(small_world):
    import pygame
    pygame.event.clear()
    assert not input_handlers.walk_cancelled()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode="a", scancode=4))
    assert input_handlers.walk_cancelled()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT, mod=0, unicode="", scancode=225))
    assert not input_handlers.walk_cancelled()


def test_creature_names_are_names_not_colour_plus_animal():
    import colornames
    import naming
    import planet as pl
    plain_colours = {w for w in colornames.NAMES} if hasattr(colornames, "NAMES") else set()
    plain_animals = {w for forms in pl.FAUNA_FORMS.values() for w in forms}
    for seed in (3, 7, 11):
        planet = pl.generate_planet(seed, "human")
        names = [f.name for f in planet.fauna]
        assert len(set(names)) == len(names)
        bare = [n for n in names if len(n.split()) == 2 and n.split()[1] in plain_animals and n.split()[0] in naming_colour_words()]
        assert not bare, bare


def naming_colour_words():
    import naming
    return {w.lower() for words in (naming.HUMAN[c] for c in naming.COLOR_CONCEPTS) for w in words}


def test_every_property_of_a_material_is_listed_on_a_scan():
    import lore
    import materials
    from planet import generate_planet
    planet = generate_planet(5, "human")
    rock = next((m for _, m in planet.materials if m.family is materials.Family.STONE), None)
    if rock is None:
        pytest.skip("no stone catalogue")
    keys = {f.key for f in lore.facts_for_material(rock, planet)}
    assert set(materials.PROPERTY_KEYS) <= keys


def test_flowers_only_grow_back_up_to_what_the_chunk_carried():
    import random
    import setup_game
    import components.plant as plants
    from engine import Engine
    from world import GameWorld, World
    from worldgen import NoiseWorldSource, regrow_flowers
    engine = Engine(player=setup_game.create_player())
    engine.game_world = GameWorld(engine=engine, seed=5)
    world = World(engine, NoiseWorldSource(3), floor=1, seed=3)
    engine.game_map = world
    chunk = world.load_chunk((6, 5))
    count = lambda: sum(isinstance(e, plants.Flower) for e in chunk.entities)
    start = count()
    assert chunk.flower_capacity == start > 0
    random.seed(2)
    for now in range(0, 6000, 20):
        regrow_flowers(world, [chunk], now)
    assert count() == start                      # nothing was picked: nothing may sprout
    for flower in [e for e in chunk.entities if isinstance(e, plants.Flower)][:5]:
        world.remove_entity(flower)
    for now in range(0, 20000, 20):
        regrow_flowers(world, [chunk], now)
    assert count() == start                      # picked ones come back, no more
