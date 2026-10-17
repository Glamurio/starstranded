"""GameMap draws entities bucketed by RenderOrder (no per-frame sort); later layers overwrite earlier ones."""
import g
from components.consumable import Meat
from components.unit import Animal
from render_order import RenderOrder


def test_render_order_iteration_is_layered(small_world):
    e = small_world()
    m = e.game_map
    meat = Meat("x"); meat.place(4, 4, m)
    corpse = Animal(); corpse.place(4, 4, m); corpse.hp = 0; corpse.die(None)
    order = [x.render_order.value for x in m.entities_in_render_order()]
    assert order == sorted(order)
    assert list(m.entities_in_render_order()).index(corpse) < list(m.entities_in_render_order()).index(meat)


def test_living_unit_is_drawn_over_corpse_and_item(small_world):
    e = small_world()
    m = e.game_map
    alive = Animal(); alive.place(4, 4, m)  # added first, still drawn last (UNIT layer)
    Meat("x").place(4, 4, m)
    dead = Animal(); dead.place(4, 4, m); dead.hp = 0; dead.die(None)
    e.update_fov()
    g.root_console.clear()
    m.render(g.root_console)
    assert g.root_console.rgb["ch"][4, 4] == alive.glyph
