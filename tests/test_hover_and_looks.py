"""Hover shows names in the side panel only for scenery and rock; ground cover is named; bare ground under an object is blank;
scenery and cover vary in hue; the codex has pictures."""
import numpy as np

import lore
import render_functions as rf
import scenery
import terrain_text
import tile_types


def test_vary_turns_hue_a_little_and_keeps_it_in_range():
    base = (160, 150, 140)
    seen = {scenery.vary(base, h / 10, l / 10) for h in range(11) for l in range(11)}
    assert len(seen) > 20
    assert all(0 <= c <= 255 for color in seen for c in color)
    assert all(max(color) - min(color) < 120 for color in seen)          # still a muted stone, not a rainbow


def test_ground_cover_has_a_name():
    tile = np.zeros((), dtype=tile_types.tile_dt)
    tile["walkable"] = True
    tile["light"]["sprite"] = tile_types.sprite_id(3, 9)
    assert terrain_text.cover_label(tile) == "Dry grass"
    tile["light"]["sprite"] = tile_types.sprite_id(10, 9)
    assert terrain_text.cover_label(tile) == "Ferns"
    tile["light"]["sprite"] = tile_types.sprite_id(0, 5)
    assert terrain_text.cover_label(tile) is None


def test_scenery_and_rock_get_no_popup_but_a_side_panel_line(new_engine):
    import entity
    engine, world = new_engine, new_engine.game_map
    p = engine.player
    spot = next((p.x + dx, p.y + dy) for dx in range(-6, 7) for dy in range(-6, 7)
                if world.is_walkable(p.x + dx, p.y + dy) and not world.get_entities_at_location(p.x + dx, p.y + dy) and world.is_visible(p.x + dx, p.y + dy))
    bones = scenery.Scenery("bones")
    world.add_entity(bones, *spot)
    engine.mouse_location = spot
    drawn = []

    class Canvas:
        def __getattr__(self, name):
            return lambda *a, **k: drawn.append(name)
    rf.render_tooltip(Canvas(), engine)
    assert not drawn                                                    # no card for bones
    assert "Scattered bones" in rf.get_names_at_location(*spot, world)  # but it is named for the side panel


def test_codex_has_a_picture_for_every_kind_of_subject(new_engine):
    pictures = lore.codex_pictures(new_engine)
    planet = new_engine.game_world.planet
    assert lore.species_subject(planet.fauna[0]) in pictures and lore.plant_subject(planet.flora[0]) in pictures
    assert all(lore.material_subject(m) in pictures for _, m in planet.materials)
    assert all(isinstance(s, int) and len(t) == 3 for s, t in pictures.values())
