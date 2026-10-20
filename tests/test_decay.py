"""Decay: corpse -> skeleton (loot and blood gone, bones to take) -> gone."""
import decay
from animals import Animal
from entity import EntityCategory


def _corpse(engine):
    world, p = engine.game_map, engine.player
    spot = next((p.x + dx, p.y + dy) for dx in range(-5, 6) for dy in range(-5, 6)
                if world.is_walkable(p.x + dx, p.y + dy) and not world.get_entities_at_location(p.x + dx, p.y + dy))
    animal = Animal()
    world.add_entity(animal, *spot)
    animal.die(quiet=True)
    return animal, world


def _later(engine, animal, days):
    now = animal.died_at + int(days * engine.config.day_length)
    chunk = engine.game_map.chunk_at(animal.x, animal.y) if hasattr(engine.game_map, "chunk_at") else next(
        c for c in engine.game_map.chunks.values() if animal in c.entities)
    decay.settle(engine.game_map, chunk, now)
    return chunk


def test_a_fresh_corpse_keeps_its_meat_and_blood(new_engine):
    animal, world = _corpse(new_engine)
    assert animal.died_at is not None and animal.skeleton is None
    _later(new_engine, animal, 1)
    assert animal.skeleton is None and any(i.nutrition == "meat" for i in animal.inventory.items if hasattr(i, "nutrition"))


def test_after_a_few_days_it_is_a_skeleton_with_only_bones_and_no_blood(new_engine):
    animal, world = _corpse(new_engine)
    _later(new_engine, animal, decay.SKELETON_AFTER + 0.1)
    assert animal.skeleton == "animal"
    assert animal.inventory.items and all(i.form == "Bone" for i in animal.inventory.items)
    assert not [e for e in world.get_entities_at_location(animal.x, animal.y) if getattr(e, "decal", False)]
    assert "skeleton" in animal.get_title()
    bones = [i.substance for i in animal.inventory.items]
    assert len({b.id for b in bones}) == len(bones) and all(b.family.value == "bone" for b in bones)


def test_a_person_leaves_a_human_skeleton(new_engine):
    import components.unit as units
    world, p = new_engine.game_map, new_engine.player
    spot = next((p.x + dx, p.y + dy) for dx in range(-5, 6) for dy in range(-5, 6)
                if world.is_walkable(p.x + dx, p.y + dy) and not world.get_entities_at_location(p.x + dx, p.y + dy))
    settler = units.Settler()
    world.add_entity(settler, *spot)
    settler.die(quiet=True)
    assert decay.skeleton_kind(settler) == "human"


def test_after_longer_nothing_is_left(new_engine):
    animal, world = _corpse(new_engine)
    _later(new_engine, animal, decay.GONE_AFTER + 1)
    assert animal.parent is None and animal not in world.entities


def test_bones_roll_their_own_properties():
    a, b = decay.roll_bone(), decay.roll_bone()
    assert a.id != b.id and (a.hardness, a.toughness, a.density) != (b.hardness, b.toughness, b.density)


def test_the_simulation_ages_corpses_as_turns_pass(new_engine):
    animal, world = _corpse(new_engine)
    gw = new_engine.game_world
    gw.current_time = animal.died_at + int((decay.SKELETON_AFTER + 0.5) * new_engine.config.day_length)
    import simulation
    simulation.run_turn(new_engine)
    assert animal.skeleton == "animal"
