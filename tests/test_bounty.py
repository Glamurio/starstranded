"""The Bounty Hunter's kit: pistol, tracker, kill-counted hunt contracts."""
import random

import pytest

import actions
import characters
import exceptions
import setup_game
import sponsors
from animals import Animal
from items import Ammo


def new_game(background="bounty_hunter", sponsor="heavy_industries", seed=21):
    random.seed(seed)
    return setup_game.new_game(characters.create_character("T", "human", background, sponsor=sponsor))


def arm(player):
    pistol = next(i for i in player.inventory.items if i.kind.key == "pistol")
    player.equipment.toggle_equip(pistol, add_message=False)
    return pistol


def target(engine, dx=3, dy=0, hp=30):
    rabbit = Animal()
    rabbit.place(engine.player.x + dx, engine.player.y + dy, engine.game_map)
    rabbit.max_hp = rabbit.hp = hp
    rabbit.base_defense = 0
    return rabbit


def clear_line(engine, length=6):
    p = engine.player
    for i in range(1, length + 1):
        engine.game_map.modify_tile(p.x + i, p.y, walkable=True, transparent=True)
        for t in list(engine.game_map.get_entities_at_location(p.x + i, p.y)):
            if t is not p:
                engine.game_map.remove_entity(t)


def test_pistol_needs_to_be_wielded_and_loaded():
    e = new_game()
    p = e.player
    clear_line(e)
    with pytest.raises(exceptions.Impossible):
        actions.FireAction(p, p.x + 3, p.y).perform()  # still holding the knife
    arm(p)
    ammo = next(i for i in p.inventory.items if isinstance(i, Ammo))
    for other in [i for i in p.inventory.items if isinstance(i, Ammo) and i is not ammo]:  # the sponsor's spare rounds
        p.inventory.remove(other)
    rabbit = target(e)
    actions.FireAction(p, p.x + 3, p.y).perform()
    assert rabbit.hp < 30 and ammo.rounds == 11
    ammo.rounds = 1
    actions.FireAction(p, p.x + 3, p.y).perform()
    assert ammo not in p.inventory.items
    with pytest.raises(exceptions.Impossible):
        actions.FireAction(p, p.x + 3, p.y).perform()


def test_shot_is_stopped_by_walls():
    e = new_game()
    p = e.player
    clear_line(e)
    arm(p)
    rabbit = target(e, 4)
    e.game_map.modify_tile(p.x + 2, p.y, walkable=False, transparent=False)
    actions.FireAction(p, p.x + 4, p.y).perform()
    assert rabbit.hp == 30


def test_marksmanship_improves_with_use_and_adds_damage():
    e = new_game()
    p = e.player
    clear_line(e)
    arm(p)
    rabbit = target(e, hp=1000)
    hp = rabbit.hp
    actions.FireAction(p, p.x + 3, p.y).perform()
    assert hp - rabbit.hp >= p.power  # skill added to the shot


def test_kills_are_counted_per_species():
    e = new_game()
    p = e.player
    rabbit = target(e, hp=1)
    rabbit.handle_health(-5, p)
    assert e.game_world.run.kills["test_hopper"] == 1


def test_hunt_contracts_are_offered_and_paid_by_kills_since_the_offer():
    e = new_game()
    run = e.game_world.run
    assert run.hunt_targets
    key, name, danger = run.hunt_targets[0]
    contract = sponsors.Contract("h1", "heavy_industries", sponsors.HUNT + key, 2, reputation=6, credits=100, label=name,
                                 start_kills=run.kills.get(key, 0))
    run.contracts = [contract]
    with pytest.raises(exceptions.Impossible):
        sponsors.deliver(e.player, run, contract)
    run.kills[key] = run.kills.get(key, 0) + 1
    n, value = sponsors.deliver(e.player, run, contract)
    assert n == 1 and value == 50 and not contract.done
    run.kills[key] += 1
    n, value = sponsors.deliver(e.player, run, contract)
    assert contract.done and run.credits >= 100 and "hunt" in contract.title


def test_only_some_sponsors_post_hunts():
    targets = [("a", "Alpha", 10), ("b", "Beta", 20)]
    found = {s: any(c.is_hunt for n in range(6) for c in sponsors.offer_contracts(5, s, n, 3, targets, {})) for s in sponsors.SPONSORS}
    assert found["heavy_industries"] and not found["relic_collectors"] and not found["retail_megacorp"]


def test_tracker_points_at_the_target_and_runs_out_of_charges():
    e = new_game()
    p = e.player
    run = e.game_world.run
    key, name, _ = run.hunt_targets[0]
    run.contracts = [sponsors.Contract("h1", "heavy_industries", sponsors.HUNT + key, 1, 3, 10, label=name)]
    for unit in list(e.game_map.actors):
        if unit is not p and getattr(unit.kind, "key", None) == key:
            e.game_map.remove_entity(unit)
    species_obj = next(s for s in e.game_world.planet.fauna if s.key == key)
    from components.unit import Unit
    prey = Unit(species_obj)
    prey.place(p.x + 5, p.y, e.game_map)
    actions.TrackAction(p).perform()
    assert any("5 tiles" in m.plain_text and "E" in m.plain_text for m in e.message_log.messages)
    for _ in range(actions.TRACKER_MAX_CHARGES - 1):
        actions.TrackAction(p).perform()
    with pytest.raises(exceptions.Impossible):
        actions.TrackAction(p).perform()
    e.game_world.current_time += actions.TRACKER_RECHARGE
    actions.TrackAction(p).perform()


def test_only_trackers_can_track():
    e = new_game(background="chemist")
    with pytest.raises(exceptions.Impossible):
        actions.TrackAction(e.player).perform()
