"""Regression tests for the defects found by the independent review (each one pressed through the real code path)."""
import os
import random

import pytest

import actions
import characters
import exceptions
import input_handlers as ih
import savegame
import setup_game
import sponsors
import structures
from components.consumable import Meat, Fruit
from events import Key, KeyDown
from items import Artifact


def new_game(race="human", background="survivalist", mode="roguelike", sponsor="heavy_industries", seed=41):
    random.seed(seed)
    return setup_game.new_game(characters.create_character("T", race, background, sponsor=sponsor), mode=mode)


def press(handler, key):
    return handler.handle_events(KeyDown(key, 0))


def test_help_and_navigation_keys_open_their_screens():
    engine = new_game()
    main = ih.MainGameEventHandler(engine)
    import screens
    assert isinstance(press(main, Key.H), screens.HelpHandler)
    assert isinstance(press(main, Key.M), screens.NavigationHandler)
    assert isinstance(press(main, Key.O), ih.CodexHandler)


def test_player_cannot_eat_against_their_diet():
    selenite = new_game("selenite_people")
    meat = Meat("x", selenite.player.inventory)
    selenite.player.inventory.add(meat)
    with pytest.raises(exceptions.Impossible):
        meat.activate(selenite.player)
    assert meat in selenite.player.inventory.items
    mau = new_game("mau")
    fruit = Fruit(mau.player.inventory) if True else None
    mau.player.inventory.add(fruit)
    with pytest.raises(exceptions.Impossible):
        fruit.activate(mau.player)


def test_a_new_run_clears_a_stale_bed_save(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / actions.BED_SAVE).mkdir()
    new_game(mode="casual")
    assert not os.path.exists(actions.BED_SAVE)


def test_death_of_a_new_run_leaves_another_runs_save(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "savegame").mkdir()
    engine = new_game()
    over = ih.GameOverEventHandler(engine)
    with pytest.raises(exceptions.QuitWithoutSaving):
        over.on_quit()
    assert os.path.isdir("savegame")


def test_death_of_a_continued_run_deletes_its_save(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "savegame").mkdir()
    engine = new_game()
    engine.continued = True
    with pytest.raises(exceptions.QuitWithoutSaving):
        ih.GameOverEventHandler(engine).on_quit()
    assert not os.path.exists("savegame")


def test_a_finished_run_is_never_written_by_the_exit_save(tmp_path, monkeypatch):
    import main
    import screens
    monkeypatch.chdir(tmp_path)
    engine = new_game()
    main.save_game(ih.GameOverEventHandler(engine), "savegame")
    main.save_game(screens.EndingHandler(engine), "savegame")
    assert not os.path.exists("savegame")
    main.save_game(ih.MainGameEventHandler(engine), "savegame")
    assert os.path.isdir("savegame")


def place_bed(engine):
    import species as defs
    from items import Placed
    bed = Placed(defs.BED, {"frame": characters.ISSUE_STEEL}, 1.0, "bed", {}, {}, "frame")
    bed.place_on_map(engine.player.x + 1, engine.player.y, engine.game_map)
    bed.blocks_movement = False


def test_sleep_stops_when_the_sleeper_dies(monkeypatch):
    import resources
    engine = new_game()
    p = engine.player
    monkeypatch.setattr(resources, "ambient_temperature", lambda *a, **k: 15.0)
    place_bed(engine)
    action = actions.SleepAction(p)
    assert action.perform()
    action.slept = 2                        # the next turn is a healing turn
    original = engine.game_world.pass_time

    def deadly(unit, time):
        original(unit=unit, time=time)
        p.hp = 0
        p.die()
    monkeypatch.setattr(engine.game_world, "pass_time", deadly)
    assert action.perform() is False
    assert not p.is_alive and p.hp <= 0     # no healing the dead, no further sleeping
    assert action.slept == 2


def test_gate_keys_cannot_be_sold_but_curios_can():
    engine = new_game(sponsor="relic_collectors")
    p = engine.player
    key = Artifact(p.inventory, "Precursor key 1", 0, is_key=True)
    curio = Artifact(p.inventory, "Precursor curio", 0)
    assert sponsors.categories_of(key) == ()
    assert "artifact" in sponsors.categories_of(curio)


def test_digging_a_ruin_gives_a_key_and_a_curio():
    engine = new_game()
    p = engine.player
    ruin = structures.Ruin(1)
    engine.game_map.add_entity(ruin, p.x, p.y + 1)
    ruin.interact(p, engine)
    finds = [i for i in p.inventory.items if isinstance(i, Artifact)]
    assert sorted(i.is_key for i in finds) == [False, True]


def test_one_kill_pays_one_bounty():
    engine = new_game()
    run = engine.game_world.run
    key, name, _ = run.hunt_targets[0]
    mk = lambda i: sponsors.Contract(f"h{i}", "heavy_industries", sponsors.HUNT + key, 2, reputation=6, credits=100,
                                     label=name, start_kills=0)
    a, b = mk(1), mk(2)
    run.contracts = [a, b]
    run.kills[key] = 2
    assert sponsors.deliver(engine.player, run, a)[0] == 2
    with pytest.raises(exceptions.Impossible):
        sponsors.deliver(engine.player, run, b)
    run.kills[key] = 4
    assert sponsors.deliver(engine.player, run, b)[0] == 2


def test_pod_shows_what_a_delivery_would_really_pay():
    engine = new_game()
    run, p = engine.game_world.run, engine.player
    from items import Stuff
    import species as defs
    contract = sponsors.Contract("c", "heavy_industries", "ingot", 4, reputation=8, credits=60)
    run.contracts = [contract]
    for _ in range(4):
        p.inventory.add(Stuff(defs.PIECE_INGOT, characters.ISSUE_STEEL, p.inventory))
    units, worth = sponsors.offer_value(p, run, contract)
    paid = sponsors.deliver(p, run, contract)
    assert (units, worth) == paid


def test_reputation_is_clamped():
    engine = new_game()
    run = engine.game_world.run
    sponsors.add_reputation(run, "heavy_industries", 10_000)
    assert all(-sponsors.MAX_REPUTATION <= v <= sponsors.MAX_REPUTATION for v in run.reputation.values())


def test_scanning_takes_a_turn():
    engine = new_game()
    p = engine.player
    engine.update_fov()
    import lore
    spot = next((x, y) for x in range(p.x - 6, p.x + 7) for y in range(p.y - 6, p.y + 7)
                if engine.game_map.is_visible(x, y) and (x, y) != (p.x, p.y) and lore.subject_at(engine, x, y))
    before = engine.game_world.current_time
    actions.ScanAction(p, *spot).perform()
    assert engine.game_world.current_time > before


def test_continue_falls_back_to_the_bed_save_after_a_casual_death(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = new_game(mode="casual")
    engine.save_as(actions.BED_SAVE)
    menu = setup_game.MainMenu()
    menu.button_highlight = "Continue"
    result = menu.resolve_menu(None)
    assert isinstance(result, ih.MainGameEventHandler)


def test_empty_inventory_enter_does_not_crash():
    engine = new_game()
    engine.player.inventory.contents.clear()
    handler = ih.InventoryActivateHandler(engine, engine.player.inventory)
    assert press(handler, Key.RETURN) in (None, handler)
