"""Farms and towns: seed-only rolls, dry ground, doors on the street, and the routes that join them."""
import numpy as np

import routes
import settlements
import shafts
import tile_types as tt
from chunks import CHUNK_H, CHUNK_W

SEED = 123
KEYS = [(x, y) for x in range(-12, 13) for y in range(-10, 11)]


def found(kind):
    return [(k, settlements.layout(SEED, k)) for k in KEYS if settlements.kind_of(SEED, k) == kind and settlements.layout(SEED, k)]


def test_both_kinds_exist_and_never_share_a_chunk_with_a_structure_or_the_landing():
    kinds = {settlements.kind_of(SEED, k) for k in KEYS}
    assert {"farm", "town"} <= kinds
    assert settlements.kind_of(SEED, (0, 0)) is None
    for key in KEYS:
        if settlements.kind_of(SEED, key):
            structure = shafts.structure(SEED, key)
            assert structure.building is None and not structure.links


def test_the_roll_is_a_pure_function_of_the_seed():
    assert [settlements.kind_of(SEED, k) for k in KEYS] == [settlements.kind_of(SEED, k) for k in KEYS]
    assert [settlements.kind_of(SEED + 1, k) for k in KEYS] != [settlements.kind_of(SEED, k) for k in KEYS]


def test_a_farm_has_a_fenced_field_with_crops_a_gate_and_a_house():
    farms = found("farm")
    assert farms
    for key, lay in farms[:4]:
        tiles, trees = shafts.surface_layer(SEED, key)
        x, y, w, h = lay.fence
        assert tiles[x, y]["walkable"] is np.False_ and tiles[x + w - 1, y + h - 1]["light"]["sprite"] == tt.fence.sprite
        gx, gy = lay.gate
        assert tiles[gx, gy]["walkable"]                                   # the gate is open
        assert (tiles["light"]["sprite"] == tt.crops.sprite).sum() > 20
        assert not trees[x:x + w, y:y + h].any()
        house = lay.houses[0]
        assert tiles[house.door]["walkable"] and not tiles[house.x, house.y]["walkable"]
        assert lay.houses[0].x + lay.houses[0].w <= CHUNK_W and y + h <= CHUNK_H


def test_a_town_has_a_street_and_houses_with_their_doors_on_it():
    towns = found("town")
    assert towns
    for key, lay in towns[:4]:
        assert len(lay.houses) >= 3
        tiles, _ = shafts.surface_layer(SEED, key)
        sx, sy, sw, sh = lay.streets[0]
        assert (tiles[sx:sx + sw, sy:sy + sh]["light"]["sprite"] == tt.street.sprite).all()
        for house in lay.houses:
            dx, dy = house.door
            assert tiles[dx, dy]["walkable"]
            outside = tiles[dx, dy + (1 if dy >= house.y + house.h - 1 else -1)]
            assert outside["walkable"]


def test_settlements_keep_off_water_and_chasms():
    for key, lay in found("farm") + found("town"):
        raw = shafts.raw_surface(SEED, key)[0]
        for house in lay.houses:
            area = raw[house.x:house.x + house.w, house.y:house.y + house.h]
            assert not (area["liquid"] != 0).any() and not area["open"].any()


def test_settlements_are_route_sites():
    key = found("farm")[0][0]
    assert routes.is_site(SEED, key)



# ── life in a settlement ─────────────────────────────────────────────────────────────────────────────
def _load(kind):
    import setup_game
    from engine import Engine
    from worldgen import NoiseWorldSource
    from world import GameWorld, World
    key = found(kind)[0][0]
    engine = Engine(player=setup_game.create_player())
    engine.game_world = GameWorld(engine=engine, seed=5)
    world = World(engine, NoiseWorldSource(SEED), floor=1, seed=SEED)
    engine.game_map = world
    return key, world, world.load_chunk(key)


def test_nothing_wild_grows_or_lies_on_built_ground():
    from components.plant import Plant
    from components.unit import Unit
    from items import Stuff
    for kind in ("farm", "town"):
        key, world, chunk = _load(kind)
        built = settlements.built(SEED, key)
        assert built
        for entity in chunk.entities:
            local = (entity.x - chunk.x0, entity.y - chunk.y0)
            if local in built:
                assert not isinstance(entity, (Plant, Stuff)), (kind, type(entity).__name__, local)
                assert not (isinstance(entity, Unit) and entity.kind.faction == "wildlife"), (kind, local)


def test_houses_hold_supplies_and_settlers_live_there():
    from components.consumable import Ration
    from components.unit import Settler
    for kind, low in (("farm", 1), ("town", 2)):
        key, world, chunk = _load(kind)
        layout = settlements.layout(SEED, key)
        people = [e for e in chunk.entities if isinstance(e, Settler)]
        assert low <= len(people) <= 4 and all(p.faction == "federation" and not p.ai.is_hostile for p in people)
        rations = [e for e in chunk.entities if isinstance(e, Ration)]
        assert len(rations) >= len(layout.houses)
        for ration in rations:
            assert any(h.x < ration.x - chunk.x0 < h.x + h.w - 1 and h.y < ration.y - chunk.y0 < h.y + h.h - 1 for h in layout.houses)
