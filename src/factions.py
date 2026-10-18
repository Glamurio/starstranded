"""Who likes whom: a small relationship model between the sponsors, richer than friend or foe.

Every pair of factions has a `Relation` with three independent parts: a *stance* (-2 hostile .. +2 allied), whether they
*trade* with each other, and a named *dispute* (what they actually quarrel about). Each faction also has an internal
*division* (a hawk and a dove wing) that decides how it takes the news of what you do to the natives. The model's one
mechanical job is to turn "you did X for A" into reputation changes for everyone else (`spillover`), so working for one
sponsor makes allies of its friends a little warmer and its rivals colder, while a quarrel only costs you where it exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Relation:
    stance: int                 # -2 hostile, -1 wary, 0 neutral, 1 friendly, 2 allied
    trade: bool = False         # they buy and sell from each other
    dispute: str = ""           # what the quarrel is about ("" = none)


@dataclass(frozen=True)
class Division:
    hawks: str                  # one wing's view of the natives
    doves: str                  # the other's
    leaning: int                # +1 hawks hold the board, -1 doves hold it: sign of the reaction to harming natives


FACTIONS = ("agricultural_monopoly", "heavy_industries", "relic_collectors", "retail_megacorp", "government_agency")

_R = Relation
RELATIONS: Dict[Tuple[str, str], Relation] = {}


def _link(a: str, b: str, relation: Relation) -> None:
    RELATIONS[(a, b)] = relation
    RELATIONS[(b, a)] = relation


_link("agricultural_monopoly", "retail_megacorp", _R(2, True))
_link("agricultural_monopoly", "heavy_industries", _R(-1, False, "land use: farms or mines on the same ground"))
_link("agricultural_monopoly", "government_agency", _R(0, True, "subsidies and crop quotas"))
_link("agricultural_monopoly", "relic_collectors", _R(0))
_link("heavy_industries", "retail_megacorp", _R(1, True))
_link("heavy_industries", "government_agency", _R(-1, False, "safety regulation and mining permits"))
_link("heavy_industries", "relic_collectors", _R(-1, False, "digging up sites for ore"))
_link("relic_collectors", "government_agency", _R(-2, False, "who owns what is dug up"))
_link("relic_collectors", "retail_megacorp", _R(-1, True, "authenticity of 'genuine' relics"))
_link("retail_megacorp", "government_agency", _R(0, False, "consumer rules"))

DIVISIONS: Dict[str, Division] = {
    "agricultural_monopoly": Division("Clear the natives' land for farms", "Keep the native ecosystem as a seed bank", 1),
    "heavy_industries": Division("Natives are an obstacle; clear them", "Natives are a labour and market opportunity", 1),
    "relic_collectors": Division("Take whatever the natives guard", "Natives are keepers of the sites: leave them be", -1),
    "retail_megacorp": Division("Natives are a risk to the supply chain", "Natives are customers", -1),
    "government_agency": Division("Secure the colony first", "First contact rules apply: no harm", -1),
}


def relation(a: str, b: str) -> Relation:
    return RELATIONS.get((a, b), Relation(0))


def rivals(faction: str):
    return [f for f in FACTIONS if f != faction and relation(faction, f).stance < 0]


def spillover(faction: str, amount: int) -> Dict[str, int]:
    """Reputation changes for the *other* factions when you earn `amount` with `faction`: allies warm a little, rivals
    cool by their stance, a trade link softens a quarrel. Pure and symmetric."""
    result: Dict[str, int] = {}
    for other in FACTIONS:
        if other == faction:
            continue
        rel = relation(faction, other)
        delta = amount * rel.stance // 4
        if rel.trade and delta < 0:
            delta = delta // 2  # trading partners do not hold a quarrel against each other for long
        if delta:
            result[other] = delta
    return result


def reaction_to_harming_natives(faction: str) -> int:
    """+1: this faction's board approves of clearing natives, -1: it is upset."""
    return DIVISIONS[faction].leaning


NATIVE_KILLS_PER_REACTION = 5
