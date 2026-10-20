"""What the player knows about the world, and how scanning and expertise establish it.

Everything scannable (a material, a species, a liquid, an artifact) offers `Fact`s. A fact has a *domain* (the skill
that interprets it) and a *difficulty* (1 trivial ... 5 expert). How much of a fact is revealed is a pure function of
the observer, with no dice:

    effective = scanner_tier + skill(domain) + caps.stat("scan_depth") (+ 1 if a domain capability tag applies)
    effective >= difficulty        -> `Know.FULL`    (exact value)
    effective == difficulty - 1    -> `Know.PARTIAL` (a coarse description: "high", "toxic?")
    otherwise                      -> `Know.UNKNOWN` (not shown)

The standard retinal scanner is tier 1: it identifies the trivial (difficulty 1) and hints at difficulty 2. A Biologist
reads biological facts at tier 1 + 3 = 4 and so interprets uses and adaptations a stranger never sees; the scanner alone
never reveals them. Discoveries persist for the rest of the run (`Knowledge`), only ever improving
(UNKNOWN -> PARTIAL -> FULL); a new run starts with an empty `Knowledge`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from capabilities import CapabilitySet
from skills import Skill, SkillSet

SCANNER_TIER = 1
"""Tier of the retinal scanner every character starts with."""


class Know(IntEnum):
    UNKNOWN = 0
    PARTIAL = 1
    FULL = 2


@dataclass(frozen=True)
class Fact:
    key: str                         # "name", "hardness", "diet", "uses" ...
    domain: Skill
    difficulty: int                  # 1..5
    value: Any                       # the truth; shown only when FULL
    hint: Optional[str] = None       # what a PARTIAL reading shows; numbers get a default bucket
    capability: Optional[str] = None  # a tag that gives +1 effective skill for this fact

    def __post_init__(self):
        assert 1 <= self.difficulty <= 5, f"fact {self.key!r}: difficulty must be 1..5"


def effective_level(fact: Fact, skills: SkillSet, caps: CapabilitySet, scanner_tier: int = SCANNER_TIER) -> int:
    level = scanner_tier + skills.level(fact.domain) + int(caps.stat("scan_depth"))
    if fact.capability and caps.has(fact.capability):
        level += 1
    return level


def reveal_level(fact: Fact, skills: SkillSet, caps: CapabilitySet, scanner_tier: int = SCANNER_TIER) -> Know:
    effective = effective_level(fact, skills, caps, scanner_tier)
    if effective >= fact.difficulty:
        return Know.FULL
    if effective == fact.difficulty - 1:
        return Know.PARTIAL
    return Know.UNKNOWN


def bucket(value: float) -> str:
    """Coarse reading of a 1-10 property."""
    return "low" if value <= 3.5 else "moderate" if value <= 6.5 else "high"


def format_fact(fact: Fact, know: Know) -> Optional[str]:
    """How a fact is shown at a knowledge level (None = not shown)."""
    if know is Know.UNKNOWN:
        return None
    if know is Know.FULL:
        value = fact.value
        return f"{value:.1f}" if isinstance(value, float) else str(value)
    if fact.hint is not None:
        return fact.hint
    if isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool):
        return bucket(float(fact.value)) + "?"
    return "?"


class Knowledge:
    """Per-run store: subject key -> fact key -> Know level. Subject keys are stable strings
    (``"material:wood/oak"``, ``"species:rabbit"``, ``"liquid:2"``)."""

    def __init__(self):
        self._known: Dict[str, Dict[str, int]] = {}

    def level(self, subject: str, fact_key: str) -> Know:
        return Know(self._known.get(subject, {}).get(fact_key, 0))

    def known_facts(self, subject: str) -> Dict[str, Know]:
        return {k: Know(v) for k, v in self._known.get(subject, {}).items() if v}

    def is_known(self, subject: str) -> bool:
        return bool(self._known.get(subject))

    def learn(self, subject: str, fact_key: str, level: Know) -> bool:
        """Record `level` if it improves on what is known. True if something was learned."""
        record = self._known.setdefault(subject, {})
        if int(level) > record.get(fact_key, 0):
            record[fact_key] = int(level)
            return True
        return False

    def note(self, subject: str, fact_key: str) -> None:
        """Record that a fact exists without knowing it yet: the subject then lists it as '???'."""
        self._known.setdefault(subject, {}).setdefault(fact_key, 0)

    def scan(self, subject: str, facts: Iterable[Fact], skills: SkillSet, caps: CapabilitySet,
             scanner_tier: int = SCANNER_TIER) -> List[Tuple[Fact, Know]]:
        """Scan a subject: improve the store and return the (fact, level) pairs that are newly learned."""
        learned = []
        for fact in facts:
            level = reveal_level(fact, skills, caps, scanner_tier)
            if level and self.learn(subject, fact.key, level):
                learned.append((fact, level))
        return learned

    def view(self, subject: str, facts: Iterable[Fact]) -> List[Tuple[Fact, Know, Optional[str]]]:
        """What the UI may show now for a subject: (fact, level, text) for every fact, level UNKNOWN has text None."""
        return [(f, self.level(subject, f.key), format_fact(f, self.level(subject, f.key))) for f in facts]

    # persistence: plain data, so a save never has to pickle live objects
    def to_dict(self) -> Dict[str, Dict[str, int]]:
        return {s: dict(f) for s, f in self._known.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Dict[str, int]]) -> "Knowledge":
        k = cls()
        for subject, facts in (data or {}).items():
            for key, level in facts.items():
                k.learn(str(subject), str(key), Know(int(level)))
        return k
