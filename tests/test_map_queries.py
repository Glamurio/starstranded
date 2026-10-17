"""Entity lookup contracts on GameMap."""
import inspect

from components.unit import Animal
from components.consumable import HealthPotion


def test_get_entities_at_location_is_annotated_as_a_list():
    from world import GameMap
    ann = inspect.signature(GameMap.get_entities_at_location).return_annotation
    assert "List[Entity]" in str(ann) and "Optional" not in str(ann)


def test_get_entities_at_location_always_returns_a_list(small_world):
    e = small_world()
    m = e.game_map
    assert m.get_entities_at_location(9, 9) == []
    assert m.get_entities_at_location(-5, -5) == []  # out of bounds: still a list
    pot = HealthPotion(); pot.place(3, 3, m)
    a = Animal(); a.place(3, 3, m)
    here = m.get_entities_at_location(3, 3)
    assert isinstance(here, list) and set(here) == {pot, a}
    assert m.get_entities_at_location(3, 3, True) == [a]  # only the blocking unit
