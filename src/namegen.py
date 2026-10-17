"""Pure-Python name generator for the libtcod-style ``.cfg`` files in ``data/namegen``.

Replaces ``tcod.namegen_*`` (only reachable through the deprecated implicit ``libtcodpy`` alias, global
state, and it re-parsed every file on every call). The cfg format is documented in
``data/namegen/README.txt``; supported: syllable sets (Pre/Start/Middle/End/Post), phoneme sets
(Vocals/Consonants), ``illegal`` substrings and ``rules`` with ``$`` wildcards (optionally with a
percent chance, e.g. ``$35m``), ``_`` for a space, ``/x`` escapes and ``%NN`` rule weights.

Randomness comes from the global ``random`` module unless a ``random.Random`` is passed, so seeding
``random`` makes names reproducible.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

DATA_DIR = Path(__file__).resolve().parent / "data" / "namegen"

_SYLLABLE_KEYS = {
    "syllablesPre": "P",
    "syllablesStart": "s",
    "syllablesMiddle": "m",
    "syllablesEnd": "e",
    "syllablesPost": "p",
}
_MAX_ATTEMPTS = 100

# A rule is (weight_percent, tokens). A token is ("lit", text) or ("wild", chance_percent, kind).
Token = Tuple
Rule = Tuple[int, Tuple[Token, ...]]


@dataclass(frozen=True)
class NameSet:
    """One ``name "..." { ... }`` block. Immutable and shared."""

    name: str
    syllables: Dict[str, Tuple[str, ...]]  # keys: P s m e p
    vocals: Tuple[str, ...]
    consonants: Tuple[str, ...]
    illegal: Tuple[str, ...]
    rules: Tuple[Rule, ...]


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def _split_syllables(value: str, lowercase: bool = False) -> Tuple[str, ...]:
    """Split a syllable/phoneme list. Letters, ' and - belong to syllables; '_' or '\\ ' is a space;
    '/x' is a literal x; anything else separates syllables. A trailing '/' drops the last syllable."""
    out: List[str] = []
    current: List[str] = []
    i = 0
    while i < len(value):
        c = value[i]
        if c == "/":
            if i + 1 >= len(value):
                current = []  # documented quirk: a slash at the very end loses the final syllable
                break
            current.append(value[i + 1])
            i += 1
        elif c == "\\" and i + 1 < len(value) and value[i + 1] == " ":
            current.append(" ")
            i += 1
        elif c == "_":
            current.append(" ")
        elif c.isalpha() or c in "'-":
            current.append(c)
        else:
            if current:
                out.append("".join(current))
            current = []
        i += 1
    if current:
        out.append("".join(current))
    if lowercase:
        out = [s.lower() for s in out]
    return tuple(dict.fromkeys(out))  # drop repeated entries, keep order


def _parse_rules(value: str) -> Tuple[Rule, ...]:
    rules: List[Rule] = []
    tokens: List[Token] = []
    weight = 100
    literal: List[str] = []

    def flush_literal() -> None:
        if literal:
            tokens.append(("lit", "".join(literal)))
            literal.clear()

    def flush_rule() -> None:
        nonlocal tokens, weight
        flush_literal()
        if tokens:
            rules.append((weight, tuple(tokens)))
        tokens, weight = [], 100

    i = 0
    n = len(value)
    while i < n:
        c = value[i]
        if c == "%":
            j = i + 1
            while j < n and value[j].isdigit():
                j += 1
            if j > i + 1:
                weight = int(value[i + 1 : j])
            i = j
            continue
        if c == "$":
            j = i + 1
            while j < n and value[j].isdigit():
                j += 1
            chance = int(value[i + 1 : j]) if j > i + 1 else 100
            if j < n and value[j] in "Psmepvc?":
                flush_literal()
                tokens.append(("wild", chance, value[j]))
                i = j + 1
                continue
            i = j
            continue
        if c == "/" and i + 1 < n:
            literal.append(value[i + 1])
            i += 2
            continue
        if c == "_":
            literal.append(" ")
        elif c.isalpha() or c in "'-":
            literal.append(c)
        else:  # any other character separates rules (a comma is conventional)
            flush_rule()
        i += 1
    flush_rule()
    return tuple(rules)


def parse_name_sets(text: str) -> Tuple[NameSet, ...]:
    """Parse the text of one cfg file into its name sets."""
    sets: List[NameSet] = []
    for match in re.finditer(r'name\s+"([^"]+)"\s*\{(.*?)\}', _strip_comments(text), flags=re.DOTALL):
        fields = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', match.group(2)))
        sets.append(
            NameSet(
                name=match.group(1),
                syllables={key: _split_syllables(fields.get(field, "")) for field, key in _SYLLABLE_KEYS.items()},
                vocals=_split_syllables(fields.get("phonemesVocals", ""), lowercase=True),
                consonants=_split_syllables(fields.get("phonemesConsonants", ""), lowercase=True),
                illegal=tuple(s.lower() for s in _split_syllables(fields.get("illegal", ""))),
                rules=_parse_rules(fields.get("rules", "")),
            )
        )
    return tuple(sets)


@lru_cache(maxsize=None)
def load_name_sets(directory: Optional[Path] = None) -> Tuple[NameSet, ...]:
    """Parse every ``*.cfg`` in `directory` (default: ``data/namegen``) once; later calls hit the cache.

    Order is deterministic: files sorted by name, sets in file order.
    """
    directory = Path(directory) if directory else DATA_DIR
    sets: List[NameSet] = []
    for path in sorted(directory.glob("*.cfg")):
        sets.extend(parse_name_sets(path.read_text(encoding="utf-8")))
    return tuple(sets)


def _tidy(word: str) -> str:
    """Collapse runs of 3+ identical letters to 2, repeated ' or -, and surrounding spaces."""
    word = re.sub(r"(.)\1{2,}", r"\1\1", word)
    word = re.sub(r"([\'-])\1+", r"\1", word)
    word = re.sub(r" {2,}", " ", word).strip()
    return word[:1].upper() + word[1:]


def _build(name_set: NameSet, rng: random.Random) -> str:
    rules = name_set.rules
    while True:  # pick a rule with probability proportional to its %weight
        weight, tokens = rules[rng.randrange(len(rules))]
        if rng.random() * 100 < weight:
            break
    pools = dict(name_set.syllables)
    pools["v"] = name_set.vocals
    pools["c"] = name_set.consonants
    pools["?"] = name_set.vocals + name_set.consonants
    parts: List[str] = []
    for token in tokens:
        if token[0] == "lit":
            parts.append(token[1])
            continue
        _, chance, kind = token
        pool = pools.get(kind, ())
        if pool and rng.random() * 100 < chance:
            parts.append(rng.choice(pool))
    return _tidy("".join(parts))


def generate_from_set(name_set: NameSet, rng: random.Random = random) -> str:
    """Generate one name from `name_set`, retrying while it contains an ``illegal`` substring."""
    if not name_set.rules:
        return ""
    word = ""
    for _ in range(_MAX_ATTEMPTS):
        word = _build(name_set, rng)
        lowered = word.lower()
        if word and not any(bad in lowered for bad in name_set.illegal):
            return word
    return word


def find_set(origin: str, sets: Sequence[NameSet]) -> NameSet:
    """First set whose name contains `origin` (case-insensitive), else the first set."""
    needle = origin.casefold()
    for name_set in sets:
        if needle in name_set.name.casefold():
            return name_set
    return sets[0]


def generate_name(origin: str, rng: random.Random = random) -> str:
    """Generate a name from the first name set matching `origin` (fallback: the first set)."""
    return generate_from_set(find_set(origin, load_name_sets()), rng)
