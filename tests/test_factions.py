"""Factions: every creature has one, humanoids are the Federation, and hostiles only fight enemies they can see."""
import allegiance
import species as defs
from animals import Animal
from components.unit import Robot, Selenite, Unit
from planet import generate_planet


def test_every_species_has_a_known_faction_and_humanoids_are_the_federation():
    assert {defs.HUMAN.faction, defs.SELENITE_PEOPLE.faction, defs.MAU.faction, defs.SELENITE.faction} == {"federation"}
    assert defs.ROBOT.faction == "robot"
    for kind in generate_planet(5, "human").fauna:
        assert kind.faction == "wildlife"
    for species in (defs.HUMAN, defs.SELENITE_PEOPLE, defs.MAU, defs.SELENITE, defs.ROBOT):
        assert species.faction in allegiance.FACTIONS
        assert ("humanoid" in Unit(species).capabilities.tags) == (species.faction == "federation")


def test_who_attacks_whom(new_engine):
    player = new_engine.player                               # a human: Federation
    wolf = Unit(generate_planet(5, "human").fauna[5])        # wildlife
    robot, exile = Robot(), Selenite()
    assert allegiance.faction_of(player) == "federation" and allegiance.name_of(wolf) == "Wildlife"
    assert allegiance.will_attack(wolf, player) and not allegiance.will_attack(wolf, robot)
    assert allegiance.will_attack(robot, player) and allegiance.will_attack(robot, wolf)
    assert allegiance.will_attack(player, robot) and not allegiance.will_attack(player, wolf)
    assert allegiance.will_attack(exile, player) and allegiance.will_attack(exile, robot)       # the exile is a renegade
    assert not allegiance.will_attack(player, exile)            # the player does not attack on his own
    assert not allegiance.will_attack(wolf, wolf)


def test_passive_creatures_never_threaten(new_engine):
    grazer = Unit(next(k for k in generate_planet(5, "human").fauna if k.key.endswith(":grazer")))
    assert not allegiance.threatens(grazer, new_engine.player)
    assert allegiance.threatens(Robot(), new_engine.player)


def test_a_robot_hunts_a_wolf_it_can_see_but_a_wolf_ignores_the_robot(small_world):
    import behavior
    e = small_world(width=40, height=20)
    e.player.place(2, 17)
    robot = Robot()
    robot.place(10, 5, e.game_map)
    prey = Animal()
    prey.place(15, 5, e.game_map)
    assert behavior.find_enemy(robot) is prey
    hostile_animal = Unit(next(k for k in generate_planet(5, "human").fauna if k.key.endswith(":hunter")))
    hostile_animal.place(20, 5, e.game_map)
    assert behavior.find_enemy(hostile_animal) is not robot
