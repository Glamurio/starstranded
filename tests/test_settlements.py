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


def test_a_farm_has_a_field_a_gate_and_a_house_in_the_terrain():
    farms = found("farm")
    assert farms
    for key, lay in farms[:4]:
        tiles, trees = shafts.surface_layer(SEED, key)
        x, y, w, h = lay.fence
        assert tiles[x + 1, y + 1]["light"]["sprite"] == tt.farmland.sprite     # (fence, crops and house walls are entities)
        gx, gy = lay.gate
        assert tiles[gx, gy]["walkable"]                                   # the gate is open
        assert not trees[x:x + w, y:y + h].any()
        house = lay.houses[0]
        assert tiles[house.door]["walkable"]
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
            if local in built and getattr(entity, "kind", None) is not world.source.planet.crop:      # (the field's own crop belongs)
                assert not isinstance(entity, (Plant, Stuff)), (kind, type(entity).__name__, local)
                assert not (isinstance(entity, Unit) and entity.kind.faction == "wildlife"), (kind, local)


def test_houses_hold_supplies_and_nobody_lives_there():
    from components.consumable import Ration
    from components.unit import Unit
    for kind in ("farm", "town"):
        key, world, chunk = _load(kind)
        layout = settlements.layout(SEED, key)
        assert not [e for e in chunk.entities if isinstance(e, Unit) and e.kind.faction == "federation"], "an abandoned place has no inhabitants"
        rations = [e for e in chunk.entities if isinstance(e, Ration)]
        assert len(rations) >= len(layout.houses)
        for ration in rations:
            assert any(h.x < ration.x - chunk.x0 < h.x + h.w - 1 and h.y < ration.y - chunk.y0 < h.y + h.h - 1 for h in layout.houses)


def test_there_are_no_settlers_or_settlement_npcs_in_the_game():
    import components.unit as units
    import species
    assert not hasattr(units, "Settler") and not hasattr(species, "SETTLER")
    assert "settler" not in species.UNIT_SPECIES if hasattr(species, "UNIT_SPECIES") else True


def test_a_farm_is_built_of_fence_timber_and_crop_entities():
    import components.plant
    from crafting import Fence, Wall
    key, world, chunk = _load("farm")
    lay = settlements.layout(SEED, key)
    at = lambda lx, ly: world.get_entities_at_location(chunk.x0 + lx, chunk.y0 + ly)
    fences = [e for e in chunk.entities if isinstance(e, Fence)]
    assert len(fences) == len(settlements._fence_tiles(lay))
    assert all(not world.is_walkable(f.x, f.y) and world.tile_at(f.x, f.y)["transparent"] for f in fences)   # solid, see-through
    gx, gy = lay.gate
    assert world.is_walkable(chunk.x0 + gx, chunk.y0 + gy)
    walls = [e for e in chunk.entities if isinstance(e, Wall) and not isinstance(e, Fence)]
    assert len(walls) == sum(len(settlements._wall_tiles(h)) for h in lay.houses)
    assert all(w.material.name != "" and not world.is_walkable(w.x, w.y) for w in walls)
    dx, dy = lay.houses[0].door
    assert world.is_walkable(chunk.x0 + dx, chunk.y0 + dy)
    crops = [e for e in chunk.entities if isinstance(e, components.plant.Plant) and e.kind is world.source.planet.crop]
    assert len(crops) == len(settlements._crop_tiles(lay))
    assert all(world.is_walkable(c.x, c.y) and c.fruit is not None for c in crops)


def test_a_broken_fence_gives_wood_and_opens_the_way():
    from crafting import Branch, Fence
    key, world, chunk = _load("farm")
    fence = next(e for e in chunk.entities if isinstance(e, Fence))
    x, y = fence.x, fence.y
    fence.handle_health(-fence.max_hp)
    assert world.is_walkable(x, y) and not any(isinstance(e, Fence) for e in world.get_entities_at_location(x, y))
    assert any(isinstance(e, Branch) for e in world.get_entities_at_location(x, y))


def test_the_crop_never_grows_wild():
    import planet as pl
    p = pl.generate_planet(8, "human")
    assert p.crop.habitat is None and p.crop.fruit is not None and p.crop.fruit.toxicity == 0
    pool, _ = p.species_weights({k: np.zeros((2, 2)) for k in ("temperature", "moisture", "fertility", "water", "elevation", "light")})
    assert p.crop not in pool
