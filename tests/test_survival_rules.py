"""Cold, heat, bad air, sleep, and Casual vs Roguelike death."""
import pytest

import actions
import characters
import crafting
import exceptions
import input_handlers
import resources
import setup_game
import species as defs
import survival
from items import Placed
from run import CASUAL


def new_game(race="human", background="survivalist", mode="roguelike", seed=11):
    import random
    random.seed(seed)
    return setup_game.new_game(characters.create_character("T", race, background), mode=mode)


def calm(engine):
    """Remove every creature but the player: the world is random and a wanderer must not turn up in a rule test."""
    for unit in [u for u in engine.game_map.units if u is not engine.player]:
        engine.game_map.remove_entity(unit)


def freeze(monkeypatch, degrees):
    monkeypatch.setattr(resources, "ambient_temperature", lambda *a, **k: degrees)


def place_bed(engine, dx=1, dy=0):
    bed = Placed(defs.BED, {"frame": characters.ISSUE_STEEL}, 1.0, "bed", {}, {}, "frame")
    bed.place_on_map(engine.player.x + dx, engine.player.y + dy, engine.game_map)
    bed.blocks_movement = False
    return bed


def test_warmth_adds_up_from_clothes_fire_shelter_and_bed(monkeypatch):
    e = new_game()
    p = e.player
    freeze(monkeypatch, -10.0)
    bare = survival.effective_temperature(e, p)
    p.equipment.armor = None
    naked = survival.effective_temperature(e, p)
    assert bare > naked  # the issued armour insulates
    fire = crafting.Campfire()
    fire.place_on_map(p.x + 1, p.y, e.game_map)
    fire.add_fuel(100)
    assert survival.effective_temperature(e, p) == pytest.approx(naked + survival.FIRE_WARMTH)
    assert survival.effective_temperature(e, p, sleeping=True) > survival.effective_temperature(e, p)


def test_cold_hurts_and_a_fire_stops_it(monkeypatch):
    e = new_game()
    p = e.player
    p.equipment.armor = None
    freeze(monkeypatch, -15.0)
    hp = p.hp
    for _ in range(30):
        survival.tick(e, p)
    assert p.cold == 30 and p.hp < hp
    fire = crafting.Campfire()
    fire.place_on_map(p.x + 1, p.y, e.game_map)
    fire.add_fuel(200)
    freeze(monkeypatch, -4.0)  # with the fire that is comfortable
    survival.tick(e, p, 10)
    assert p.cold < 30  # warming up
    hp = p.hp
    survival.tick(e, p, 40)
    assert p.hp == hp and p.cold == 0


def test_comfortable_weather_costs_nothing(monkeypatch):
    e = new_game()
    freeze(monkeypatch, 20.0)
    hp = e.player.hp
    survival.tick(e, e.player, 50)
    assert e.player.hp == hp and e.player.cold == 0


def test_heat_dries_you_out(monkeypatch):
    e = new_game()
    freeze(monkeypatch, 45.0)
    thirst = e.player.thirst
    e.game_world.current_time = 0
    for t in range(0, 60):
        e.game_world.current_time = t
        survival.tick(e, e.player)
    assert e.player.thirst < thirst


def test_gas_pockets_are_deterministic_and_only_deep():
    master = 12345
    assert not any(survival.gas_at(master, 0, x, y) for x in range(40) for y in range(40))
    assert not any(survival.gas_at(master, -1, x, y) for x in range(40) for y in range(40))
    deep = [(x, y) for x in range(0, 120, 3) for y in range(0, 120, 3) if survival.gas_at(master, -3, x, y)]
    assert deep and deep == [(x, y) for x in range(0, 120, 3) for y in range(0, 120, 3) if survival.gas_at(master, -3, x, y)]
    assert len(deep) < 0.4 * 40 * 40


@pytest.mark.parametrize("race,expected", [("human", 20), ("selenite_people", 60)])
def test_breath_lasts_by_race_and_then_you_suffocate(monkeypatch, race, expected):
    e = new_game(race)
    p = e.player
    monkeypatch.setattr(survival, "gas_at", lambda *a: True)
    hp = p.hp
    for _ in range(expected - 1):
        survival.tick(e, p)
    assert p.hp == hp  # still holding
    survival.tick(e, p, 2)
    assert p.hp < hp
    monkeypatch.setattr(survival, "gas_at", lambda *a: False)
    survival.tick(e, p, expected)
    assert p.breath is None


def test_sleep_needs_a_bed_and_heals(monkeypatch):
    e = new_game()
    p = e.player
    freeze(monkeypatch, 15.0)
    monkeypatch.setattr(actions.SleepAction, "_enemy_in_view", lambda self: False)  # the world is random: no wanderers
    calm(e)
    with pytest.raises(exceptions.Impossible):
        actions.SleepAction(p).perform()
    place_bed(e)
    p.hp = p.max_hp - 8
    action = actions.SleepAction(p)
    turns = 0
    while action.perform():
        turns += 1
        assert turns < 200
    assert p.hp > p.max_hp - 8 and action.slept >= 30
    assert not p.sleeping


def test_sleep_is_interrupted_by_damage(monkeypatch):
    e = new_game()
    calm(e)
    p = e.player
    freeze(monkeypatch, 15.0)
    place_bed(e)
    action = actions.SleepAction(p)
    assert action.perform()
    p.hp -= 2
    assert action.perform() is False


def test_casual_sleep_saves_and_death_wakes_you_at_the_bed(monkeypatch, tmp_path):
    save = str(tmp_path / "bed")
    monkeypatch.setattr(actions, "BED_SAVE", save)
    e = new_game(mode=CASUAL)
    calm(e)
    p = e.player
    freeze(monkeypatch, 15.0)
    place_bed(e)
    actions.SleepAction(p).perform()
    assert (tmp_path / "bed").is_dir() and e.game_world.run.bed is not None
    p.hp = 0
    p.die()
    over = input_handlers.GameOverEventHandler(e)
    assert over.casual_respawn()
    e.session.push(over)
    from events import Key, KeyDown
    over.handle_events(KeyDown(Key.R))
    handler = e.session.handlers[-1]
    assert isinstance(handler, input_handlers.MainGameEventHandler)
    assert handler.engine.player.is_alive and handler.engine.game_world.run.deaths == 1


def test_roguelike_death_offers_no_respawn(monkeypatch, tmp_path):
    monkeypatch.setattr(actions, "BED_SAVE", str(tmp_path / "bed"))
    e = new_game(mode="roguelike")
    (tmp_path / "bed").mkdir()
    assert not input_handlers.GameOverEventHandler(e).casual_respawn()


def test_status_lines_show_temperature_and_credits():
    import survival
    engine = new_game()
    engine.game_world.run.sponsor = "heavy_industries"
    lines = survival.status_lines(engine)
    assert lines[0][0] in ("Fine", "Cold", "Freezing", "Hot")
    assert any(text.endswith("cr") for text, _ in lines)
    engine.player.breath = 7        # held breath is a meter on the HUD now (see test_swimming), not a text line
    assert not any("Breath" in t for t, _ in survival.status_lines(engine))


def test_engine_render_with_status_panel(small_world):
    from ui_helpers import SESSION
    engine = new_game()
    engine.render(SESSION.canvas)
