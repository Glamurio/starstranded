"""Skills: how trained a character is in a field of knowledge (0 = untrained ... 5 = master).

There are deliberately few. Strength and dexterity are not separate scores: bodies differ through race modifiers
(`capabilities`), not rolls. Skills decide *information quality* (see `knowledge`) and gate some recipes
(`crafting`); nothing is rolled, so identical knowledge gives identical results (important for a deterministic,
save-compatible roguelike).
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Iterable, Mapping, Tuple

MAX_LEVEL = 5


class Skill(Enum):
    ENGINEERING = "engineering"    # machines, structures, electronics, construction quality
    BIOLOGY = "biology"            # animals, plants, ecosystems, biological resources
    CHEMISTRY = "chemistry"        # liquids, compounds, reactions, toxicity
    GEOLOGY = "geology"            # minerals, terrain, resources in the ground
    LINGUISTICS = "linguistics"    # languages, inscriptions, ancient writing
    SURVIVAL = "survival"          # shelter, fire, foraging, weather
    MARKSMANSHIP = "marksmanship"  # ranged weapons and tracking prey

    def __str__(self) -> str:
        return self.value


class SkillSet:
    """Immutable mapping Skill -> level (missing = 0), clamped to 0..MAX_LEVEL."""

    def __init__(self, levels: Mapping[Skill, int] = ()):
        self._levels: Dict[Skill, int] = {}
        for skill, level in dict(levels).items():
            self._levels[Skill(skill)] = max(0, min(MAX_LEVEL, int(level)))

    def level(self, skill: Skill) -> int:
        return self._levels.get(skill, 0)

    def __getitem__(self, skill: Skill) -> int:
        return self.level(skill)

    def combine(self, *others: "SkillSet") -> "SkillSet":
        """Sum of levels (race + background + training), clamped."""
        merged: Dict[Skill, int] = dict(self._levels)
        for other in others:
            for skill, level in other._levels.items():
                merged[skill] = merged.get(skill, 0) + level
        return SkillSet(merged)

    def items(self) -> Iterable[Tuple[Skill, int]]:
        return tuple(sorted(self._levels.items(), key=lambda kv: kv[0].value))

    def __eq__(self, other) -> bool:
        return isinstance(other, SkillSet) and self._levels == other._levels

    def __hash__(self) -> int:
        return hash(tuple(sorted((s.value, l) for s, l in self._levels.items())))

    def __repr__(self) -> str:
        return "SkillSet(" + ", ".join(f"{s.value}={l}" for s, l in self.items()) + ")"


def skills(**levels: int) -> SkillSet:
    """`skills(biology=3, survival=1)`."""
    return SkillSet({Skill(name): level for name, level in levels.items()})
