"""Characterization: hunger / thirst / health.

Several tests pin CURRENT (buggy) behavior and are named ``test_current_*``; Phase 1 flips them.
"""
import actions


def test_hunger_clamps_between_zero_and_max(small_world):
    p = small_world().player
    p.handle_hunger(+50)
    assert p.hunger == p.max_hunger
    p.handle_hunger(-1000)
    assert p.hunger == 0


def test_thirst_clamps_between_zero_and_max(small_world):
    p = small_world().player
    p.handle_thirst(+50)
    assert p.thirst == p.max_thirst
    p.handle_thirst(-1000)
    assert p.thirst == 0


def test_time_drives_hunger_and_thirst_by_their_periods(small_world):
    import simulation
    e = small_world()
    e.player.max_hp = e.player.hp = 10 ** 6
    for _ in range(simulation.HUNGER_PERIOD):
        actions.WaitAction(e.player).perform()
    assert e.game_world.current_time == simulation.HUNGER_PERIOD
    assert e.player.hunger == 100 - 1
    assert e.player.thirst == 100 - simulation.HUNGER_PERIOD // simulation.THIRST_PERIOD


def test_full_thirst_lasts_three_days_and_full_hunger_seven():
    import simulation
    assert 3 * 480 <= 100 * simulation.THIRST_PERIOD < 3.2 * 480
    assert 7 * 480 <= 100 * simulation.HUNGER_PERIOD < 7.2 * 480


def test_starving_kills_the_player_outright_and_says_so(small_world):
    e = small_world()
    p = e.player
    p.hunger = 1
    p.handle_hunger(-1)
    assert p.hunger == 0 and not p.is_alive and p.hp == p.max_hp          # (no slow loss of health: it simply kills)
    assert e.game_world.run.flags["death_cause"] == "starvation"
    assert any("You died: starvation" in m.plain_text for m in e.message_log.messages)


def test_dehydration_kills_the_player_outright_and_says_so(small_world):
    e = small_world()
    p = e.player
    p.thirst = 1
    p.handle_thirst(-1)
    assert not p.is_alive and e.game_world.run.flags["death_cause"] == "thirst"


def test_the_player_is_warned_before_the_end(small_world):
    e = small_world()
    p = e.player
    p.hunger = 21
    p.handle_hunger(-1)
    assert any("You are hungry" in m.plain_text for m in e.message_log.messages)


def test_death_names_the_attacker_and_the_kind_of_damage(small_world):
    from animals import Animal
    import damage
    e = small_world()
    a = Animal(); a.place(3, 3, e.game_map)
    p = e.player
    p.hp = 1
    p.handle_health(-5, a, damage_type=damage.DamageType.SHARP)
    assert not p.is_alive
    cause = e.game_world.run.flags["death_cause"]
    assert cause.startswith("killed by ") and "(sharp damage)" in cause


def test_npc_starves_to_death_without_player_messages(small_world):
    from animals import Animal
    e = small_world()
    a = Animal(); a.place(4, 4, e.game_map)
    a.hunger = 0
    a.handle_hunger(-1)
    assert not a.is_alive
    assert not any("starving" in m.plain_text for m in e.message_log.messages)
    assert not any("experience" in m.plain_text for m in e.message_log.messages)  # no self-kill XP


def test_starvation_death_of_player_does_not_award_xp(small_world):
    e = small_world()
    p = e.player
    p.hp = 1; p.hunger = 0
    xp = p.level.current_xp
    p.handle_hunger(-1)
    assert not p.is_alive and p.level.current_xp == xp


def test_hunger_above_zero_never_damages(small_world):
    e = small_world()
    e.player.handle_hunger(-50)
    e.player.handle_thirst(-50)
    assert e.player.hp == e.player.max_hp


def test_handle_health_damage_and_death_of_ai_unit(small_world):
    from animals import Animal
    e = small_world()
    a = Animal(); a.place(3, 3, e.game_map)
    a.handle_health(-5, e.player)
    assert a.hp == 0 and not a.is_alive


def test_handle_health_clamps_to_max_hp(small_world):
    p = small_world().player
    p.handle_health(+500, p)
    assert p.hp == p.max_hp == 30


def test_handle_health_clamp_uses_max_hp_even_when_hunger_cap_differs(small_world):
    p = small_world().player
    p.max_hunger = 1000
    p.hp = 5
    p.handle_health(+500, p)
    assert p.hp == p.max_hp


def test_heal_clamps_to_max_hp_and_reports_amount(small_world):
    p = small_world().player
    p.hp = 20
    assert p.heal(4) == 4 and p.hp == 24
    assert p.heal(50) == 6 and p.hp == p.max_hp
    assert p.heal(5) == 0


def test_player_death_sets_flags(small_world):
    e = small_world()
    p = e.player
    p.die()
    assert not p.is_alive and not p.blocks_movement
    assert any("You died" in m.plain_text for m in e.message_log.messages)


def test_npc_hunger_ticks_in_ai_perform(small_world):
    from animals import Animal
    from components.ai import BaseAI
    e = small_world()
    a = Animal(); a.place(5, 5, e.game_map)
    import simulation
    e.game_world.current_time = simulation.HUNGER_PERIOD * simulation.THIRST_PERIOD
    BaseAI.perform(a.ai)
    assert a.hunger == 99 and a.thirst == 99


def test_the_player_slowly_heals_one_point_per_fifteen_turns(small_world, monkeypatch):
    import simulation
    import survival
    monkeypatch.setattr(survival, "tick", lambda *a, **k: None)
    e = small_world()
    player = e.player
    player.max_hp, player.hp = 40, 10
    player.hunger = player.thirst = 100
    start = e.game_world.current_time
    e.game_world.current_time = start - start % simulation.HEAL_PERIOD       # (on a period boundary)
    e.game_world.pass_time(player, simulation.HEAL_PERIOD * 4)
    assert player.hp == 14
