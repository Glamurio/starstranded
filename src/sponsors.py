"""Sponsors: who you work for, what they pay for, and how work turns into a way off the planet.

Each sponsor wants certain *categories* of goods (`categories_of` classifies an item). Contracts ask for a number of items
of one category; a delivery pays reputation and credits. The price of one item is

    base(category) x sponsor premium x item quality x saturation

where saturation falls as you flood a sponsor with the same category (`SATURATION`^delivered, never below
`MIN_SATURATION`): it is cheaper to serve several sponsors than to flog one thing. Reputation earned with one sponsor
spills over to the others through `factions.spillover`. Enough reputation (and finished contracts) opens the
sponsor's rescue (`rescue_ready`, see `endings`).

Everything here is deterministic: contracts derive from the planet seed, the sponsor and how many were completed.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import factions
import species as defs
from skills import Skill

SATURATION = 0.9
MIN_SATURATION = 0.3
RESCUE_REPUTATION = 40
RESCUE_CONTRACTS = 2
DELIVERY_RADIUS = 3

BASE_VALUE: Dict[str, int] = {
    "food": 6, "meat": 4, "fibre": 3, "hide": 5, "ore": 8, "radioactive": 20, "ingot": 15, "fuel": 5, "glass": 10,
    "wire": 8, "crystal": 25, "electronics": 40, "medicine": 30, "hull": 50, "artifact": 120,
}


@dataclass(frozen=True)
class Sponsor:
    key: str
    name: str
    blurb: str
    premium: Tuple[Tuple[str, float], ...]       # category -> multiplier on its base value
    perk: str                                    # what signing with them gives, in words
    start_credits: int = 40

    def multiplier(self, category: str) -> float:
        return dict(self.premium).get(category, 0.0)

    @property
    def wants(self) -> Tuple[str, ...]:
        return tuple(c for c, _ in self.premium)


SPONSORS: Dict[str, Sponsor] = {s.key: s for s in (
    Sponsor("agricultural_monopoly", "Agricultural Monopoly",
            "Feeds half the sector and wants more land, seed stock and fibre. Pays for anything that grows.",
            (("food", 2.0), ("fibre", 1.5), ("hide", 1.3), ("meat", 1.2)), "Starts with extra rations.", 40),
    Sponsor("heavy_industries", "Heavy Industries",
            "Mines, mills and shipyards. Pays well for ore, metal, fuel and hull parts, and asks no questions.",
            (("ore", 1.6), ("ingot", 1.8), ("fuel", 1.4), ("wire", 1.5), ("hull", 1.6), ("radioactive", 1.5)),
            "Starts with spare ammunition.", 40),
    Sponsor("relic_collectors", "Relic Collectors",
            "Private collectors of precursor artifacts. Pay absurd sums for relics and a fair price for crystals.",
            (("artifact", 2.5), ("crystal", 1.5), ("glass", 1.1)), "Starts able to recognise precursor sites.", 40),
    Sponsor("retail_megacorp", "Retail Megacorp",
            "Sells everything to everyone. Wants consumer goods: hides, glass, medicine, electronics, crystals.",
            (("hide", 1.4), ("glass", 1.5), ("medicine", 1.5), ("electronics", 1.3), ("crystal", 1.3), ("food", 1.2)),
            "Starts with more credits.", 80),
    Sponsor("government_agency", "Government Agency",
            "Colonial survey office. Pays for knowledge (species and materials catalogued) and for electronics and medicine.",
            (("electronics", 1.4), ("medicine", 1.5), ("radioactive", 1.8), ("hull", 1.3)),
            "Starts with a better scanner reading (scan depth +1).", 40),
)}

KNOWLEDGE_CONTRACT = "knowledge"   # a contract the government pays for in catalogue entries, not goods
HUNT = "hunt:"                     # "hunt:<species key>": kill that many (counted from when the contract was offered)
HUNTERS = ("heavy_industries", "government_agency", "agricultural_monopoly")


# ── classifying and valuing items ───────────────────────────────────────────────────────────────────────────
def categories_of(item) -> Tuple[str, ...]:
    """The market categories an item belongs to (empty: nobody wants it)."""
    from components.consumable import Fruit, Meat
    from items import Artifact, Composite, Stuff
    found: List[str] = []
    if isinstance(item, Fruit):
        found.append("food")
    elif isinstance(item, Meat):
        found.append("meat")
    elif isinstance(item, Artifact):
        found.append("artifact")
    elif isinstance(item, Stuff):
        form, mat = item.form, item.substance
        if form == "Fibre":
            found.append("fibre")
        elif form in ("Hide", "Leather"):
            found.append("hide")
        elif form == "Ore":
            found.append("radioactive" if mat.radioactivity >= 5 else "ore")
        elif form == "Ingot":
            found.append("ingot")
        elif form == "Coal":
            found.append("fuel")
        elif form == "Glass":
            found.append("glass")
        elif form == "Wire":
            found.append("wire")
        elif form == "Stone" and mat.family.value == "crystal":
            found.append("crystal")
    elif isinstance(item, Composite):
        kind = item.kind
        if kind in (defs.CIRCUIT, defs.POWER_CELL, defs.NAV_UNIT, defs.LENS):
            found.append("electronics")
        elif kind is defs.MEDKIT:
            found.append("medicine")
        elif kind is defs.HULL_PLATE:
            found.append("hull")
    return tuple(found)


def item_quality(item) -> float:
    """0.7 .. 1.3: how good this particular item is (a crafted thing's quality, a material's best properties)."""
    from items import Composite, Stuff
    if isinstance(item, Composite):
        return max(0.7, min(1.3, item.quality))
    if isinstance(item, Stuff):
        values = sorted(item.substance.props().values(), reverse=True)[:3]
        return 0.7 + 0.06 * (sum(values) / 3)
    return 1.0


def saturation(run, sponsor: str, category: str) -> float:
    count = run.delivered.get(sponsor, {}).get(category, 0)
    return max(MIN_SATURATION, SATURATION ** count)


def unit_value(item, sponsor: str, run, category: Optional[str] = None) -> int:
    """What `sponsor` pays now for one `item` (0 if it does not want it)."""
    best = 0.0
    for cat in categories_of(item):
        if category and cat != category:
            continue
        premium = SPONSORS[sponsor].multiplier(cat)
        best = max(best, BASE_VALUE[cat] * premium * item_quality(item) * saturation(run, sponsor, cat))
    return int(round(best))


# ── contracts ───────────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Contract:
    id: str
    sponsor: str
    category: str
    count: int
    reputation: int
    credits: int
    filled: int = 0
    done: bool = False
    start_kills: int = 0
    label: str = ""

    @property
    def is_hunt(self) -> bool:
        return self.category.startswith(HUNT)

    @property
    def species_key(self) -> str:
        return self.category[len(HUNT):]

    @property
    def remaining(self) -> int:
        return self.count - self.filled

    @property
    def title(self) -> str:
        if self.is_hunt:
            return f"{SPONSORS[self.sponsor].name}: hunt {self.count} {self.label or self.species_key}"
        what = "catalogue entries" if self.category == KNOWLEDGE_CONTRACT else f"{self.category} (x{self.count})"
        return f"{SPONSORS[self.sponsor].name}: deliver {what}"


def hunt_targets(planet) -> List[Tuple[str, str, int]]:
    """Creatures of the planet a sponsor may put a bounty on: (species key, name, danger)."""
    if planet is None:
        return []
    return [(s.key, s.name, s.max_hp + 2 * s.power) for s in planet.fauna]


def offer_contracts(seed: int, sponsor: str, completed: int, how_many: int = 3, targets=(), kills=None) -> List[Contract]:
    """A deterministic set of contracts: same planet, sponsor and progress give the same offers. With `targets` (see
    `hunt_targets`) the sponsors in `HUNTERS` may ask for hunts; `kills` is the player's kill count so far (hunts count from there)."""
    rng = random.Random(f"{seed}:{sponsor}:{completed}")
    spec = SPONSORS[sponsor]
    options = list(spec.wants) + ([KNOWLEDGE_CONTRACT] if sponsor == "government_agency" else [])
    if targets and sponsor in HUNTERS:
        options.append(HUNT)
    offers = []
    for index in range(how_many):
        category = options[(index + rng.randrange(len(options))) % len(options)]
        count = rng.randint(2, 4 + min(4, completed))
        if category == HUNT:
            key, name, danger = targets[rng.randrange(len(targets))]
            count = max(1, count // 2)
            offers.append(Contract(f"{sponsor}:{completed}:{index}", sponsor, HUNT + key, count, reputation=count * 3,
                                   credits=count * (8 + 3 * danger), start_kills=(kills or {}).get(key, 0), label=name))
            continue
        base = BASE_VALUE.get(category, 12)
        offers.append(Contract(f"{sponsor}:{completed}:{index}", sponsor, category, count,
                               reputation=count * 2 + (2 if base >= 25 else 0), credits=count * base))
    return offers


def knowledge_count(run) -> int:
    """How many catalogue entries (species and materials the player has learned something about)."""
    return sum(1 for subject in run.knowledge.to_dict() if subject.startswith(("species:", "material:")))


# ── the run's economy: reputation, credits, deliveries ───────────────────────────────────────────────────────
def choose_sponsor(run, player, sponsor: str, planet=None) -> None:
    """Sign with a sponsor at the start of a run: starting credits, perk and the first reputation."""
    spec = SPONSORS[sponsor]
    run.sponsor = sponsor
    run.credits += spec.start_credits
    run.reputation[sponsor] = run.reputation.get(sponsor, 0) + 5
    if sponsor == "agricultural_monopoly":
        from components.consumable import Ration
        for _ in range(2):
            if not player.inventory.is_full():
                player.inventory.add(Ration(player.inventory))
    elif sponsor == "heavy_industries":
        from items import Ammo
        if not player.inventory.is_full():
            player.inventory.add(Ammo(player.inventory, 12))
    elif sponsor == "relic_collectors":
        player.extra_grants += (defs_grant("archaeology"),)
    elif sponsor == "government_agency":
        player.extra_grants += (defs_grant("survey_license"),)
    run.hunt_targets = hunt_targets(planet)
    run.contracts = offer_contracts(run.seed, sponsor, 0, targets=run.hunt_targets, kills=run.kills)


def defs_grant(tag: str):
    from capabilities import Grant
    return Grant(tag)


def add_reputation(run, sponsor: str, amount: int) -> Dict[str, int]:
    """Change reputation with `sponsor` and let the news reach the others; returns every change made."""
    changes = {sponsor: amount}
    for other, delta in factions.spillover(sponsor, amount).items():
        changes[other] = delta
    for key, delta in changes.items():
        run.reputation[key] = run.reputation.get(key, 0) + delta
    return changes


def matching_items(player, contract: Contract):
    return [i for i in player.inventory.items if contract.category in categories_of(i)]


def deliver(player, run, contract: Contract) -> Tuple[int, int]:
    """Hand over what the player carries for `contract`. Returns (items delivered, credits earned). Raises Impossible if
    nothing fits or the player is not at the pod."""
    import exceptions
    if contract.done:
        raise exceptions.Impossible("That contract is finished.")
    if contract.is_hunt:
        kills = run.kills.get(contract.species_key, 0) - contract.start_kills
        take = min(contract.remaining, max(0, kills - contract.filled))
        if not take:
            raise exceptions.Impossible(f"You have not killed any {contract.label or contract.species_key} for this bounty yet.")
        value = take * contract.credits // contract.count
        delivered = take
    elif contract.category == KNOWLEDGE_CONTRACT:
        have = knowledge_count(run) - run.knowledge_spent
        take = min(contract.remaining, max(0, have))
        if not take:
            raise exceptions.Impossible("You have no new catalogue entries to hand in.")
        run.knowledge_spent += take
        value = take * BASE_VALUE.get("electronics", 12) // 2
        delivered = take
    else:
        items = matching_items(player, contract)[:contract.remaining]
        if not items:
            raise exceptions.Impossible(f"You carry nothing the {SPONSORS[contract.sponsor].name} wants for this contract.")
        value = 0
        for item in items:
            value += unit_value(item, contract.sponsor, run, contract.category)
            player.inventory.remove(item)
            counts = run.delivered.setdefault(contract.sponsor, {})
            counts[contract.category] = counts.get(contract.category, 0) + 1
        delivered = len(items)
    contract.filled += delivered
    run.credits += value
    if contract.filled >= contract.count:
        contract.done = True
        run.completed.append(contract.id)
        add_reputation(run, contract.sponsor, contract.reputation)
        run.contracts = [c for c in run.contracts if not c.done] + (
            offer_contracts(run.seed, contract.sponsor, len(run.completed), 1, run.hunt_targets, run.kills)
            if len(run.contracts) < 3 else [])
    else:
        add_reputation(run, contract.sponsor, max(1, delivered))
    return delivered, value


SHOP: Dict[str, Tuple[int, str]] = {
    "ration": (10, "Ration pack"), "medkit": (60, "Medkit"), "ammo": (30, "Pistol rounds (12)"),
}


def buy(player, run, key: str):
    """Buy a supply item at the pod with credits."""
    import exceptions
    import characters
    price, _ = SHOP[key]
    if run.credits < price:
        raise exceptions.Impossible(f"That costs {price} credits; you have {run.credits}.")
    if player.inventory.is_full():
        raise exceptions.Impossible("Your inventory is full.")
    run.credits -= price
    return characters.issue_item(key, player)


def rescue_ready(run, sponsor: Optional[str] = None) -> bool:
    """Is a corporate rescue on offer: enough reputation with the sponsor and enough finished contracts."""
    sponsor = sponsor or run.sponsor
    if not sponsor:
        return False
    done = sum(1 for c in run.completed if c.startswith(sponsor + ":"))
    return run.reputation.get(sponsor, 0) >= RESCUE_REPUTATION and done >= RESCUE_CONTRACTS
