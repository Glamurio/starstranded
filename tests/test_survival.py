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


def test_time_drives_hunger_every_4_and_thirst_every_2_minutes(small_world):
    e = small_world()
    for _ in range(8):
        actions.WaitAction(e.player).perform()
    assert e.game_world.current_time == 8
    assert e.player.hunger == 100 - 2
    assert e.player.thirst == 100 - 4


def test_starvation_damages_the_unit_and_messages_the_player_once(small_world):
    e = small_world()
    p = e.player
    p.hunger = 1
    p.handle_hunger(-1)  # reaches 0: message + 1 damage
    assert p.hunger == 0 and p.hp == p.max_hp - 1
    p.handle_hunger(-1)  # stays at 0: damage, no repeated message
    assert p.hp == p.max_hp - 2
    msgs = [m.plain_text for m in e.message_log.messages if "starving" in m.plain_text]
    assert len(msgs) == 1


def test_dehydration_damages_the_unit_and_messages_the_player_once(small_world):
    e = small_world()
    p = e.player
    p.thirst = 1
    p.handle_thirst(-1)
    p.handle_thirst(-1)
    assert p.hp == p.max_hp - 2
    msgs = [m.plain_text for m in e.message_log.messages if "dehydrated" in m.plain_text]
    assert len(msgs) == 1


def test_npc_starves_to_death_without_player_messages(small_world):
    from animals import Animal
    e = small_world()
    a = Animal(); a.place(4, 4, e.game_map)
    a.hunger = 0
    a.handle_hunger(-1)  # max_hp is 1 -> dies
    assert a.hp == 0 and not a.is_alive
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
    e.game_world.current_time = 4
    BaseAI.perform(a.ai)
    assert a.hunger == 99 and a.thirst == 99
