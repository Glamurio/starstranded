"""Inventory menu rendering must cope with items whose `char` is a plain string (HealthPotion '!')."""
import g
import input_handlers
from components.consumable import HealthPotion, Meat


def render_inventory(e):
    handler = input_handlers.InventoryActivateHandler(e, e.player.inventory)
    g.handlers = [input_handlers.MainGameEventHandler(e), handler]
    g.root_console.clear()
    handler.on_render(g.root_console)
    return g.root_console


def test_inventory_renders_with_a_health_potion(small_world):
    e = small_world()
    e.player.inventory.add(HealthPotion())
    console = render_inventory(e)
    # entries start at (12, 3) and are 2 rows apart: dagger, armor, potion
    assert console.rgb["ch"][12, 7] == ord("!")


def test_inventory_still_renders_codepoint_sprites(small_world):
    e = small_world()
    meat = Meat("rabbit", e.player.inventory)
    e.player.inventory.add(meat)
    console = render_inventory(e)
    assert console.rgb["ch"][12, 7] == meat.char


def test_entity_glyph_handles_both_kinds():
    class Dummy:
        pass
    d = Dummy()
    d.char = 0xE123
    assert input_handlers.entity_glyph(d) == chr(0xE123)
    d.char = "!"
    assert input_handlers.entity_glyph(d) == "!"
