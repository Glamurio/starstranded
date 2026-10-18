"""Hunger-driven behaviour: hungry -> find food -> approach -> attack/eat; carnivores hunt herbivores."""
import behavior
import exceptions
from components.consumable import Fruit, Meat
from components.unit import Animal, Selenite
from species import Diet


def turn(unit, times=1, cheap=False):
    for _ in range(times):
        if not unit.is_alive:
            return
        try:
            if cheap:
                behavior.act(unit, unit.ai, cheap=True)
            else:
                unit.ai.perform()
        except exceptions.Impossible:
            pass


def far_player(e, x=35, y=35):
    """The player stands far away and sees only 3 tiles: hostile creatures do not notice them."""
    from config import GameConfig
    e.config = GameConfig(fov_radius=3)
    e.player.place(x, y)
    e.update_fov()


def stage(small_world, hunter_at=(5, 5), prey_at=(10, 5)):
    e = small_world(width=40, height=40)
    far_player(e)
    hunter = Selenite(name="Zub"); hunter.place(*hunter_at, e.game_map)
    prey = Animal(); prey.place(*prey_at, e.game_map)
    prey.ai = None  # a sitting duck unless a test wants it to run
    return e, hunter, prey


def test_diets():
    assert Selenite(name="x").diet is Diet.CARNIVORE and Animal().diet is Diet.HERBIVORE


def test_what_each_diet_can_eat():
    assert Animal().can_eat(Fruit()) and not Animal().can_eat(Meat("x"))
    s = Selenite(name="x")
    assert s.can_eat(Meat("x")) and not s.can_eat(Fruit())


def test_hungry_carnivore_hunts_the_herbivore_it_sees(small_world):
    e, hunter, prey = stage(small_world)
    prey.max_hp = prey.hp = 1
    hunter.hunger = 50
    turn(hunter, 12)
    assert not prey.is_alive


def test_a_fed_carnivore_leaves_prey_alone(small_world):
    e, hunter, prey = stage(small_world)
    hunter.hunger = hunter.thirst = 100
    turn(hunter, 15)
    assert prey.is_alive and prey.hp == prey.max_hp


def test_the_hunter_eats_what_it_killed(small_world):
    e, hunter, prey = stage(small_world, prey_at=(7, 5))
    hunter.hunger = 30
    turn(hunter, 25)
    assert not prey.is_alive
    assert hunter.hunger > 30  # it ate the meat from the corpse
    assert not any(isinstance(i, Meat) for i in prey.inventory.items)


def test_carnivores_do_not_eat_fruit_nor_herbivores_meat(small_world):
    e = small_world(width=30, height=30)
    far_player(e, 28, 28)
    s = Selenite(name="Zub"); s.place(5, 5, e.game_map)
    s.hunger = 30
    f = Fruit(); f.place(6, 5, e.game_map)
    turn(s, 3)
    assert f.parent is e.game_map
    r = Animal(); r.place(15, 15, e.game_map)
    r.hunger = 30
    m = Meat("x"); m.place(16, 15, e.game_map)
    turn(r, 3)
    assert m.parent is e.game_map


def test_hungry_herbivore_walks_to_distant_food(small_world):
    """It used to wander instead of approaching food that was not next to it."""
    e = small_world(width=40, height=40)
    far_player(e)
    rabbit = Animal(); rabbit.place(5, 5, e.game_map)
    rabbit.hunger = 30
    fruit = Fruit(); fruit.place(11, 8, e.game_map)
    turn(rabbit, 12)
    assert fruit.parent is not e.game_map  # looted (and maybe eaten already)


def test_herbivores_flee_from_hunters(small_world):
    e = small_world(width=40, height=40)
    far_player(e)
    rabbit = Animal(); rabbit.place(10, 10, e.game_map)
    hunter = Selenite(name="Zub"); hunter.place(12, 10, e.game_map)
    hunter.ai = None
    start = max(abs(rabbit.x - hunter.x), abs(rabbit.y - hunter.y))
    turn(rabbit, 4)
    assert max(abs(rabbit.x - hunter.x), abs(rabbit.y - hunter.y)) > start


def test_herbivores_do_not_fight_each_other(small_world):
    e = small_world(width=30, height=30)
    far_player(e, 28, 28)
    a, b = Animal(), Animal()
    a.place(5, 5, e.game_map); b.place(6, 5, e.game_map)
    a.hunger = 10
    turn(a, 5)
    assert b.hp == b.max_hp


def test_the_player_is_prey_to_nobody_but_hunts_rabbits(small_world):
    e = small_world()
    r = Animal()
    assert behavior.preys_on(e.player, r) and not behavior.preys_on(r, e.player)


def test_near_tier_creatures_hunt_too(small_world):
    e, hunter, prey = stage(small_world)
    prey.max_hp = prey.hp = 1
    hunter.hunger = 40
    turn(hunter, 15, cheap=True)
    assert not prey.is_alive


def test_fights_the_player_cannot_see_are_not_logged(small_world):
    e, hunter, prey = stage(small_world, hunter_at=(30, 5), prey_at=(31, 5))
    prey.max_hp = prey.hp = 1
    hunter.hunger = 10
    before = len(e.message_log.messages)
    e.game_map.explored[:] = True
    turn(hunter, 4)
    assert not prey.is_alive
    assert [m.plain_text for m in e.message_log.messages[before:]] == []
