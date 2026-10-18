"""Sponsors, contracts, valuation, reputation spillover, factions and the persisted run state."""
import pytest

import characters
import exceptions
import factions
import setup_game
import species as defs
import sponsors
from components.consumable import Fruit, Meat
from items import Artifact, Stuff
from material_helpers import make_material
from materials import Family
from run import CASUAL, RunState


def piece(kind, **props):
    family = {"Ore": Family.STONE, "Fibre": Family.FIBER, "Ingot": Family.METAL}.get(kind.object_type, Family.STONE)
    return Stuff(kind, make_material(f"t:{kind.key}", family=family, **props))


def test_five_sponsors_each_want_something_different():
    assert set(sponsors.SPONSORS) == set(factions.FACTIONS) and len(sponsors.SPONSORS) == 5
    assert len({s.wants for s in sponsors.SPONSORS.values()}) == 5


def test_items_are_classified_into_market_categories():
    assert sponsors.categories_of(Fruit()) == ("food",)
    assert sponsors.categories_of(Meat("x")) == ("meat",)
    assert sponsors.categories_of(Artifact()) == ("artifact",)
    assert sponsors.categories_of(piece(defs.PIECE_ORE, radioactivity=7)) == ("radioactive",)
    assert sponsors.categories_of(piece(defs.PIECE_ORE)) == ("ore",)
    assert sponsors.categories_of(piece(defs.PIECE_FIBER)) == ("fibre",)


def test_sponsors_pay_a_premium_for_what_they_want():
    run = RunState()
    fruit = Fruit()
    assert sponsors.unit_value(fruit, "agricultural_monopoly", run) > sponsors.unit_value(fruit, "retail_megacorp", run) > 0
    assert sponsors.unit_value(fruit, "heavy_industries", run) == 0
    assert sponsors.unit_value(Artifact(), "relic_collectors", run) > sponsors.unit_value(fruit, "agricultural_monopoly", run)


def test_flooding_one_sponsor_with_one_good_lowers_its_price():
    run = RunState()
    fruit = Fruit()
    first = sponsors.unit_value(fruit, "agricultural_monopoly", run)
    run.delivered = {"agricultural_monopoly": {"food": 10}}
    assert sponsors.unit_value(fruit, "agricultural_monopoly", run) < first
    run.delivered = {"agricultural_monopoly": {"food": 500}}
    assert sponsors.saturation(run, "agricultural_monopoly", "food") == sponsors.MIN_SATURATION


def test_contracts_are_deterministic_and_wanted_by_the_sponsor():
    a = sponsors.offer_contracts(123, "heavy_industries", 0)
    b = sponsors.offer_contracts(123, "heavy_industries", 0)
    assert a == b and len(a) == 3
    assert all(c.category in sponsors.SPONSORS["heavy_industries"].wants for c in a)
    assert sponsors.offer_contracts(124, "heavy_industries", 0) != a


def test_signing_with_a_sponsor_gives_its_perk_and_first_contracts():
    player = characters.create_character("T", "human", "surveyor", sponsor="agricultural_monopoly")
    run = RunState(seed=5)
    rations = sum(i.kind is defs.RATION for i in player.inventory.items)
    sponsors.choose_sponsor(run, player, "agricultural_monopoly")
    assert sum(i.kind is defs.RATION for i in player.inventory.items) == rations + 2
    assert run.contracts and run.sponsor == "agricultural_monopoly" and run.credits > 0
    gov = characters.create_character("T", "human")
    sponsors.choose_sponsor(RunState(seed=5), gov, "government_agency")
    assert gov.capabilities.stat("scan_depth") == 1.0


def test_delivering_pays_credits_and_reputation_and_finishes_the_contract():
    player = characters.create_character("T", "human")
    player.inventory.capacity = 40
    run = RunState(seed=9)
    contract = sponsors.Contract("c1", "agricultural_monopoly", "food", 2, reputation=6, credits=20)
    run.contracts = [contract]
    with pytest.raises(exceptions.Impossible):
        sponsors.deliver(player, run, contract)  # carrying nothing it wants
    for _ in range(3):
        player.inventory.add(Fruit(player.inventory))
    n, value = sponsors.deliver(player, run, contract)
    assert n == 2 and value > 0 and contract.done and run.credits == value
    assert run.reputation["agricultural_monopoly"] >= 6
    assert run.delivered["agricultural_monopoly"]["food"] == 2
    assert sum(isinstance(i, Fruit) for i in player.inventory.items) == 1
    with pytest.raises(exceptions.Impossible):
        sponsors.deliver(player, run, contract)


def test_reputation_spills_over_to_allies_and_rivals():
    run = RunState()
    changes = sponsors.add_reputation(run, "relic_collectors", 20)
    assert changes["relic_collectors"] == 20
    assert run.reputation["government_agency"] < 0          # they quarrel over ownership of finds
    assert run.reputation.get("agricultural_monopoly", 0) == 0
    run2 = RunState()
    sponsors.add_reputation(run2, "agricultural_monopoly", 20)
    assert run2.reputation["retail_megacorp"] > 0           # allied trading partners
    assert run2.reputation["heavy_industries"] < 0


def test_factions_have_stance_trade_and_dispute_not_just_friend_or_foe():
    rel = factions.relation("relic_collectors", "government_agency")
    assert rel.stance == -2 and rel.dispute and not rel.trade
    rel = factions.relation("retail_megacorp", "relic_collectors")
    assert rel.stance < 0 and rel.trade and rel.dispute  # they trade and still quarrel
    assert factions.relation("heavy_industries", "retail_megacorp") == factions.relation("retail_megacorp", "heavy_industries")
    assert factions.rivals("relic_collectors")
    assert len({d.leaning for d in factions.DIVISIONS.values()}) == 2


def test_rescue_needs_reputation_and_finished_contracts():
    run = RunState(sponsor="heavy_industries")
    assert not sponsors.rescue_ready(run)
    run.reputation["heavy_industries"] = sponsors.RESCUE_REPUTATION
    assert not sponsors.rescue_ready(run)
    run.completed = ["heavy_industries:0:0", "heavy_industries:1:0"]
    assert sponsors.rescue_ready(run)


def test_shop_sells_supplies_for_credits():
    player = characters.create_character("T", "human")
    run = RunState(credits=15)
    sponsors.buy(player, run, "ration")
    assert run.credits == 5
    with pytest.raises(exceptions.Impossible):
        sponsors.buy(player, run, "medkit")


def test_new_game_follows_race_culture_mode_and_sponsor():
    player = characters.create_character("Q", "mau", "bounty_hunter", sponsor="heavy_industries")
    e = setup_game.new_game(player, mode=CASUAL)
    assert e.game_world.culture == "mau" and e.game_world.planet.culture == "mau"
    assert e.game_world.run.mode == CASUAL and e.game_world.run.sponsor == "heavy_industries"


def test_run_state_and_character_survive_save_and_load(tmp_path):
    player = characters.create_character("Q", "selenite_people", "biologist", sponsor="government_agency")
    e = setup_game.new_game(player)
    run = e.game_world.run
    run.reputation["retail_megacorp"] = 7
    run.flags["beacon"] = True
    run.knowledge.learn("species:x", "diet", 2)
    path = str(tmp_path / "t.sav")
    e.save_as(path)
    loaded = setup_game.load_game(path)
    lr = loaded.game_world.run
    assert lr.reputation == run.reputation and lr.flags == {"beacon": True} and lr.sponsor == "government_agency"
    assert lr.contracts == run.contracts and lr.knowledge.level("species:x", "diet") == 2
    p = loaded.player
    assert p.kind.key == "selenite_people" and p.background == "biologist"
    assert p.capabilities.has("botanical_expertise") and p.capabilities.has("survey_license")
    assert loaded.game_world.culture == "selenite"
