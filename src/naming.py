"""Believable, deterministic names for materials, organisms and places, grounded in what the thing *is*.

Names are built from *concepts* chosen by the entity's measurable traits (a very elastic material -> SPRING, a conductive
fur -> SPARK + COAT, a blue colour -> BLUE) and then *rendered* in the language of the culture that names it. The same
concepts therefore give "Springwood" (Human), "Lumvaar" style compounds (Selenite, Harmonic) or "khet-nehem" (Mau,
Egyptian) and the gloss of a name always says what it means, so a Translator can recover it.

Rules enforced by construction and checked by tests:
- Words only come from a concept whose condition the traits satisfy (no "Heavy" for a light material).
- Deterministic: a name depends only on `(seed, key, traits, culture)`; a `Namer` resolves collisions among the names of
  one planet in call order, so a planet's catalogue is named once, in a fixed order, by `planet.py`.
- No malformed output: capitalised, no doubled or leading separators, no repeated stems, 4-24 characters.

Provisional (unidentified) descriptions are produced by `provisional`; the real name is shown once the "name" fact is
known (see `knowledge`).
"""
from __future__ import annotations

import colorsys
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from seeds import mix_seed

RGB = Tuple[int, int, int]

# ── concepts ───────────────────────────────────────────────────────────────────────────────────────────
# trait concepts: (property, direction) -> concept. Salience of a trait = how far from "ordinary" the value is.
TRAIT_CONCEPTS: Dict[Tuple[str, str], str] = {
    ("elasticity", "high"): "spring", ("hardness", "high"): "hard", ("hardness", "low"): "soft",
    ("toughness", "high"): "stout", ("toughness", "low"): "brittle", ("tenacity", "high"): "bind",
    ("density", "high"): "heavy", ("density", "low"): "feather", ("insulation", "high"): "warm",
    ("electrical_conductivity", "high"): "spark", ("thermal_conductivity", "high"): "heat",
    ("flammability", "high"): "tinder", ("combustibility", "high"): "fuel", ("transparency", "high"): "clear",
    ("incandescence", "high"): "glow", ("radioactivity", "high"): "ray", ("abrasivity", "high"): "grit",
}
ABSENT_TYPICAL = {"radioactivity", "transparency", "incandescence", "electrical_conductivity", "thermal_conductivity",
                  "abrasivity", "flammability", "combustibility", "elasticity", "insulation", "tenacity"}

COLOR_CONCEPTS = ("red", "orange", "yellow", "green", "teal", "blue", "indigo", "violet", "pink", "brown", "white", "black", "grey")

NOUN_CONCEPTS = ("wood", "tree", "stone", "rock", "metal", "fibre", "hide", "bone", "clay", "sand", "glass", "crystal",
                 "coal", "plant", "bush", "grass", "reed", "coat", "hopper", "runner", "shell", "wing", "horn", "root")

FAMILY_NOUNS: Dict[str, Tuple[str, ...]] = {
    "wood": ("wood", "tree"), "stone": ("stone", "rock"), "metal": ("metal",), "fiber": ("fibre", "plant"),
    "hide": ("hide",), "bone": ("bone",), "clay": ("clay",), "sand": ("sand",), "glass": ("glass",),
    "ceramic": ("clay",), "crystal": ("crystal", "stone"), "fuel": ("coal", "stone"), "organic": ("plant",),
    "composite": ("wood",),
    # organisms
    "tree": ("tree", "wood"), "shrub": ("bush", "plant"), "grass": ("grass", "reed"), "fungus": ("plant",),
    "animal": ("hopper", "runner"), "furred": ("coat", "runner"), "armoured": ("shell", "runner"),
    "small_herbivore": ("hopper", "coat"), "grazer": ("runner", "horn"), "predator": ("runner", "coat"),
    "crawler": ("shell", "runner"), "bird": ("wing", "runner"), "serpent": ("runner", "hide"), "fruit": ("plant",),
}

CONCEPT_GLOSS = {c: c for c in list(COLOR_CONCEPTS) + list(NOUN_CONCEPTS) + list(TRAIT_CONCEPTS.values())}
CONCEPT_GLOSS.update({"fibre": "fibre", "bind": "binding", "tinder": "tinder", "ray": "radiance", "feather": "light",
                      "spark": "spark", "heat": "heat", "clear": "clear", "stout": "sturdy", "hard": "hard"})

# ── cultures: concept -> word ────────────────────────────────────────────────────────────────────────────
HUMAN: Dict[str, Tuple[str, ...]] = {
    "spring": ("Spring", "Whip", "Flex"), "hard": ("Iron", "Adamant", "Hard"), "soft": ("Soft", "Velvet", "Down"),
    "stout": ("Stout", "Sturdy", "Stub"), "brittle": ("Brittle", "Crisp", "Shard"), "bind": ("Strand", "Tie", "Cord"),
    "heavy": ("Heavy", "Lead", "Weight"), "feather": ("Feather", "Air", "Wisp"), "warm": ("Warm", "Hearth", "Cosy"),
    "spark": ("Spark", "Volt", "Static"), "heat": ("Sun", "Hot", "Kiln"), "tinder": ("Tinder", "Kindle", "Flare"),
    "fuel": ("Burn", "Cinder", "Blaze"), "clear": ("Clear", "Lucid", "Glassy"), "glow": ("Glow", "Ember", "Lume"),
    "ray": ("Ray", "Halo", "Radiant"), "grit": ("Grit", "Scour", "Whet"),
    "red": ("Red", "Scarlet", "Crimson", "Ruby"), "orange": ("Orange", "Amber", "Copper", "Rust"),
    "yellow": ("Yellow", "Gold", "Straw", "Saffron"), "green": ("Green", "Moss", "Fern", "Jade"),
    "teal": ("Teal", "Verdigris", "Aqua"), "blue": ("Blue", "Azure", "Cobalt", "Sky"),
    "indigo": ("Indigo", "Midnight", "Navy"), "violet": ("Violet", "Lilac", "Plum"), "pink": ("Pink", "Rose", "Blush"),
    "brown": ("Brown", "Umber", "Chestnut"), "white": ("White", "Pale", "Ivory", "Snow"),
    "black": ("Black", "Soot", "Ebony", "Coal"), "grey": ("Grey", "Ash", "Slate", "Dun"),
    "wood": ("wood", "timber"), "tree": ("tree", "bole"), "stone": ("stone", "rock"), "rock": ("rock", "crag"),
    "metal": ("metal", "steel"), "fibre": ("fibre", "strand"), "hide": ("hide", "skin"), "bone": ("bone",),
    "clay": ("clay", "mud"), "sand": ("sand", "grit"), "glass": ("glass",), "crystal": ("crystal", "spar"),
    "coal": ("coal", "cinder"), "plant": ("plant", "weed"), "bush": ("bush", "shrub"), "grass": ("grass", "sedge"),
    "reed": ("reed", "cane"), "coat": ("coat", "pelt", "fur"), "hopper": ("hopper", "hare"), "runner": ("runner", "stalker"),
    "shell": ("shell", "back"), "wing": ("wing",), "horn": ("horn",), "root": ("root", "tuber"),
}
SELENITE: Dict[str, Tuple[str, ...]] = {
    "spring": ("vaelu",), "hard": ("dorun",), "soft": ("miel",), "stout": ("ruvan",), "brittle": ("shiral",), "bind": ("tennu",),
    "heavy": ("grovan",), "feather": ("selae",), "warm": ("calum",), "spark": ("zephi",), "heat": ("solun",),
    "tinder": ("ignel",), "fuel": ("pyral",), "clear": ("lucen",), "glow": ("lumar",), "ray": ("radel",), "grit": ("abrun",),
    "red": ("rubel",), "orange": ("aurel",), "yellow": ("solar",), "green": ("verun",), "teal": ("celun",), "blue": ("azur",),
    "indigo": ("nocel",), "violet": ("violan",), "pink": ("rosel",), "brown": ("terran",), "white": ("albel",),
    "black": ("noctar",), "grey": ("cinar",), "wood": ("ligna",), "tree": ("arbo",), "stone": ("petra",), "rock": ("saxum",),
    "metal": ("ferra",), "fibre": ("filum",), "hide": ("pelle",), "bone": ("osan",), "clay": ("argil",), "sand": ("arena",),
    "glass": ("vitra",), "crystal": ("crysta",), "coal": ("carbo",), "plant": ("flora",), "bush": ("frutex",),
    "grass": ("herba",), "reed": ("calam",), "coat": ("vellus",), "hopper": ("salta",), "runner": ("curra",),
    "shell": ("testa",), "wing": ("ala",), "horn": ("cornu",), "root": ("radix",),
}
MAU: Dict[str, Tuple[str, ...]] = {
    "spring": ("nehem",), "hard": ("khepesh",), "soft": ("neden",), "stout": ("aa",), "brittle": ("tjeser",), "bind": ("shenu",),
    "heavy": ("djeba",), "feather": ("shut",), "warm": ("khet-u",), "spark": ("sekhem",), "heat": ("hemet",),
    "tinder": ("seshep",), "fuel": ("neshem",), "clear": ("wab",), "glow": ("akhet",), "ray": ("aten",), "grit": ("sehen",),
    "red": ("desher",), "orange": ("sepa",), "yellow": ("nebu",), "green": ("wadj",), "teal": ("shes",), "blue": ("khesbed",),
    "indigo": ("irtyu",), "violet": ("hemut",), "pink": ("hedj-sha",), "brown": ("tjam",), "white": ("hedj",),
    "black": ("kem",), "grey": ("iner-hu",), "wood": ("khet",), "tree": ("ished",), "stone": ("iner",), "rock": ("djew",),
    "metal": ("biau",), "fibre": ("shenet",), "hide": ("inem",), "bone": ("qes",), "clay": ("hebes",), "sand": ("shay",),
    "glass": ("hebeny",), "crystal": ("mefkat",), "coal": ("tjesu",), "plant": ("sekhet",), "bush": ("bener",),
    "grass": ("sekhu",), "reed": ("ges",), "coat": ("seshem",), "hopper": ("sepen",), "runner": ("maw",),
    "shell": ("nekhen",), "wing": ("djuw",), "horn": ("abu",), "root": ("khenu",),
}
CORPORATE_CODE: Dict[str, str] = {  # corporate catalogue style: stem + series code
    "spring": "Elast", "hard": "Dura", "soft": "Plia", "stout": "Robu", "brittle": "Frag", "bind": "Ligo", "heavy": "Mass",
    "feather": "Lite", "warm": "Therm", "spark": "Cond", "heat": "Calor", "tinder": "Ign", "fuel": "Pyro", "clear": "Lumi",
    "glow": "Incan", "ray": "Rad", "grit": "Abra",
}

CULTURES = ("human", "selenite", "mau", "corporate")
_TABLE = {"human": HUMAN, "selenite": SELENITE, "mau": MAU}

COMPOUNDABLE = {"wood", "tree", "stone", "rock", "bush", "grass", "root", "shell", "coat", "reed", "clay", "sand", "bone"}
"""Nouns that fuse with a preceding word in Human names ("Springwood"); others stay separate ("Whip Steel")."""

BASELINE = 5.0
SALIENT_DEVIATION = 2.5
PRESENT_MIN = 4.0

# What is *ordinary* for a family: a trait is remarkable only relative to it (every wood burns; a wood that burns
# poorly is remarkable). Properties not listed default to BASELINE, or to 0 for the "absent unless present" ones.
FAMILY_TYPICAL: Dict[str, Dict[str, float]] = {
    "wood": {"hardness": 4.5, "toughness": 6, "tenacity": 4.5, "density": 5, "elasticity": 4.5, "insulation": 4.5, "flammability": 6.2, "combustibility": 6.2, "thermal_conductivity": 2},
    "fiber": {"hardness": 2, "toughness": 3, "tenacity": 6.5, "density": 2, "elasticity": 4, "insulation": 3, "flammability": 7, "combustibility": 3.2},
    "hide": {"hardness": 1.2, "toughness": 3, "tenacity": 4, "density": 1.5, "insulation": 6.5, "flammability": 6.5, "combustibility": 4, "thermal_conductivity": 1.2},
    "stone": {"hardness": 6, "toughness": 4.5, "tenacity": 1.5, "density": 6.5, "abrasivity": 4, "insulation": 3, "thermal_conductivity": 4},
    "metal": {"hardness": 4.5, "toughness": 6, "tenacity": 6, "density": 8, "electrical_conductivity": 5, "thermal_conductivity": 6},
    "crystal": {"hardness": 8, "toughness": 3, "density": 5, "transparency": 6, "thermal_conductivity": 4},
    "fuel": {"hardness": 2.5, "toughness": 2.5, "density": 3.5, "flammability": 4, "combustibility": 9},
    "sand": {"hardness": 5.5, "toughness": 1.5, "density": 4, "abrasivity": 6, "transparency": 3},
    "clay": {"hardness": 2, "toughness": 2.5, "tenacity": 2.5, "density": 4.5, "insulation": 3.5},
}
for _animal in ("animal", "furred", "armoured", "small_herbivore", "grazer", "predator", "crawler", "bird", "serpent"):
    FAMILY_TYPICAL[_animal] = FAMILY_TYPICAL["hide"]
for _plant in ("tree", "shrub", "grass", "fungus"):
    FAMILY_TYPICAL[_plant] = FAMILY_TYPICAL["wood"] if _plant == "tree" else FAMILY_TYPICAL["fiber"]
NOUNLIKE_EPITHETS = {"spring", "spark", "glow", "grit", "ray", "bind", "heat", "tinder", "fuel"}
"""Epithets that can stand alone as a noun ("Indigo Spring", "Red Grit"); adjectives always need a noun."""


@dataclass(frozen=True)
class Name:
    text: str
    gloss: str                      # what it means, in plain English ("blue spring-wood")
    reasons: Tuple[Tuple[str, str], ...] = ()   # (property, "high"/"low") justifications, for tests and the codex


def hue_name(color: RGB) -> str:
    """Nearest colour concept (one of COLOR_CONCEPTS) for an RGB colour."""
    r, g, b = (c / 255 for c in color)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if v < 0.18:
        return "black"
    if s < 0.12:
        return "white" if v > 0.8 else "grey" if v > 0.3 else "black"
    deg = h * 360
    if v < 0.55 and 15 <= deg < 50:
        return "brown"
    if s < 0.35 and v < 0.7 and 15 <= deg < 50:
        return "brown"
    for limit, name in ((15, "red"), (40, "orange"), (68, "yellow"), (165, "green"), (195, "teal"), (255, "blue"),
                        (285, "indigo"), (320, "violet"), (345, "pink"), (361, "red")):
        if deg < limit:
            return name
    return "red"


def salient_traits(props: Mapping[str, float], limit: int = 2, family: Optional[str] = None) -> List[Tuple[str, str, float]]:
    """The most remarkable properties as (property, "high"/"low", salience), strongest first, measured against what is
    ordinary for the family. Only traits that have a word."""
    typical = FAMILY_TYPICAL.get(family or "", {})
    found = []
    for prop, value in props.items():
        ordinary = typical.get(prop, 0.0 if prop in ABSENT_TYPICAL else BASELINE)
        deviation = value - ordinary
        if ordinary == 0.0 and prop in ABSENT_TYPICAL:
            if value >= PRESENT_MIN and (prop, "high") in TRAIT_CONCEPTS:
                found.append((prop, "high", value - PRESENT_MIN + 1))
            continue
        if deviation >= SALIENT_DEVIATION and (prop, "high") in TRAIT_CONCEPTS:
            found.append((prop, "high", deviation))
        elif deviation <= -SALIENT_DEVIATION and (prop, "low") in TRAIT_CONCEPTS:
            found.append((prop, "low", -deviation))
    found.sort(key=lambda t: (-t[2], t[0]))
    return found[:limit]


def provisional(family: str, color: RGB, culture: str = "human", furred: bool = False) -> str:
    """What an unidentified thing looks like before it has been scanned: its colour and what it appears to be."""
    colour = hue_name(color)
    nouns = {"wood": "tree", "tree": "tree", "stone": "rock", "metal": "metallic lump", "fiber": "plant fibre", "hide": "hide",
             "shrub": "shrub", "grass": "grass", "animal": "furred animal" if furred else "animal", "crystal": "crystal",
             "fungus": "fungus", "sand": "sand", "clay": "clay"}
    return f"{colour} {nouns.get(family, family)}"


class Namer:
    """Names one planet's things for one culture, resolving collisions in call order."""

    def __init__(self, seed: int, culture: str = "human"):
        assert culture in CULTURES, f"unknown naming culture {culture!r}"
        self.seed = seed
        self.culture = culture
        self.used: Set[str] = set()

    # ── public ──────────────────────────────────────────────────────────────────────────────────────
    def name(self, key: str, family: str, color: RGB, props: Optional[Mapping[str, float]] = None,
             habitat: Optional[str] = None) -> Name:
        rng = random.Random(mix_seed(self.seed, hash_key(key)))
        traits = salient_traits(props or {}, family=family)
        colour = hue_name(color)
        nouns = FAMILY_NOUNS.get(family, ("plant",))
        for attempt in range(12):
            candidate = self._compose(rng, traits, colour, nouns, attempt)
            if _norm(candidate.text) not in self.used and _well_formed(candidate.text):
                self.used.add(_norm(candidate.text))
                return candidate
        # exhausted: add a catalogue qualifier (rare; keeps names unique)
        base = self._compose(rng, traits, colour, nouns, 0)
        serial = 2
        while _norm(f"{base.text} {_roman(serial)}") in self.used:
            serial += 1
        text = f"{base.text} {_roman(serial)}"
        self.used.add(_norm(text))
        return Name(text, base.gloss, base.reasons)

    def fruit(self, key: str, color: RGB, shape: str) -> str:
        """A fruit's name: its colour word and its shape ("Azure pear"); other cultures name the colour and "plant fruit"."""
        rng = random.Random(mix_seed(self.seed, hash_key(key)))
        colour = hue_name(color)
        for _ in range(8):
            word = self._word(rng, colour)
            text = f"{word} {shape}" if self.culture == "human" and shape else f"{word}-{self._word(rng, 'plant')}"
            text = _tidy(text) if self.culture != "human" else f"{word} {shape}"
            if _norm(text) not in self.used:
                self.used.add(_norm(text))
                return text
        base = f"{word} {shape}".strip() if self.culture == "human" else f"{word}-{self._word(rng, 'plant')}"
        serial = 2
        while _norm(f"{base} {_roman(serial)}") in self.used:
            serial += 1
        text = _tidy(f"{base} {_roman(serial)}")
        self.used.add(_norm(text))
        return text

    # ── internals ──────────────────────────────────────────────────────────────────────────────────
    def _word(self, rng: random.Random, concept: str) -> str:
        return rng.choice(_TABLE[self.culture][concept]) if self.culture in _TABLE else concept

    def _compose(self, rng: random.Random, traits, colour: str, nouns: Sequence[str], attempt: int) -> Name:
        noun = nouns[attempt % len(nouns)] if attempt < 4 else rng.choice(nouns)
        trait = traits[0] if traits else None
        second = traits[1] if len(traits) > 1 else None
        epithet = TRAIT_CONCEPTS[(trait[0], trait[1])] if trait else None
        reasons = tuple((t[0], t[1]) for t in traits[:1])
        patterns = ["compound", "spaced"] if epithet else ["colour_noun"]
        if epithet:
            patterns += ["epithet_noun"]
            if epithet in NOUNLIKE_EPITHETS:
                patterns += ["colour_epithet"]
        if second is not None and attempt >= 2:
            patterns.append("two_traits")
        pattern = rng.choice(patterns) if attempt < 6 else rng.choice(["colour_noun", "epithet_noun", "two_traits"] if second else ["colour_noun"])
        if pattern in ("epithet_noun", "compound", "colour_epithet") and epithet is None:
            pattern = "colour_noun"
        if pattern == "colour_epithet" and epithet not in NOUNLIKE_EPITHETS:
            pattern = "epithet_noun"
        if pattern == "two_traits" and second is None:
            pattern = "compound"
        gloss: str
        if self.culture == "corporate":
            return self._corporate(rng, epithet, colour, noun, reasons)
        if pattern == "compound" and self.culture == "human" and noun not in COMPOUNDABLE:
            pattern = "spaced"
        if pattern == "compound":
            text = self._join(self._word(rng, epithet), self._word(rng, noun), compound=True)
            gloss = f"{CONCEPT_GLOSS[epithet]} {noun}"
        elif pattern == "spaced" or pattern == "epithet_noun":
            text = f"{self._word(rng, epithet)} {self._word(rng, noun)}"
            gloss = f"{CONCEPT_GLOSS[epithet]} {noun}"
        elif pattern == "colour_epithet":
            text = f"{self._word(rng, colour)} {self._word(rng, epithet)}"
            gloss = f"{colour} {CONCEPT_GLOSS[epithet]}"
        elif pattern == "two_traits":
            e2 = TRAIT_CONCEPTS[(second[0], second[1])]
            text = f"{self._word(rng, epithet)}-{self._word(rng, e2)} {self._word(rng, noun)}" if self.culture != "human" else \
                f"{self._word(rng, e2)} {self._word(rng, epithet)}{self._word(rng, noun).lower()}"
            gloss = f"{CONCEPT_GLOSS[e2]}, {CONCEPT_GLOSS[epithet]} {noun}"
            reasons = tuple((t[0], t[1]) for t in traits[:2])
        else:  # colour_noun
            text = self._join(self._word(rng, colour), self._word(rng, noun), compound=self.culture != "human" or rng.random() < 0.5)
            gloss = f"{colour} {noun}"
            reasons = ()
        return Name(_tidy(text), gloss, reasons)

    def _join(self, a: str, b: str, compound: bool) -> str:
        if not compound:
            return f"{a} {b}"
        if self.culture == "human":
            return a + b.lower()
        if self.culture == "selenite":
            return a + b
        return f"{a}-{b}"

    def _corporate(self, rng: random.Random, epithet: Optional[str], colour: str, noun: str, reasons) -> Name:
        stem = CORPORATE_CODE.get(epithet, HUMAN[colour][0][:4]) if epithet else HUMAN[colour][0][:4]
        suffix = {"wood": "Ligna", "tree": "Ligna", "stone": "Lith", "rock": "Lith", "metal": "Met", "fibre": "Fil", "coat": "Pel",
                  "hide": "Cor", "bone": "Oss", "clay": "Arg", "sand": "Sil", "glass": "Vit", "crystal": "Cry", "coal": "Carb"}.get(noun, noun[:3].capitalize())
        text = f"{stem}{suffix}-{rng.randint(2, 9)}{rng.choice('ABCDEFGHKLMNPRSTVXZ')}"
        return Name(text, f"{CONCEPT_GLOSS.get(epithet, colour)} {noun} (catalogue)", reasons)


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────
def hash_key(key: str) -> int:
    value = 1469598103934665603
    for ch in key.encode("utf-8"):
        value = ((value ^ ch) * 1099511628211) & 0x7FFFFFFFFFFFFFFF
    return value


def _norm(text: str) -> str:
    """Collision key: "Neshem-iner" and "Neshem Iner" are the same name."""
    return text.lower().replace("-", "").replace(" ", "")


def _tidy(text: str) -> str:
    parts = text.replace("--", "-").strip(" -").split(" ")
    return " ".join(p[:1].upper() + p[1:] if p else p for p in parts if p)


def _roman(n: int) -> str:
    numerals = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    out = ""
    for value, numeral in numerals:
        while n >= value:
            out += numeral
            n -= value
    return out


def _well_formed(text: str) -> bool:
    if not 4 <= len(text) <= 24 or text != text.strip() or "  " in text or "--" in text:
        return False
    if text.startswith("-") or text.endswith("-") or not text[0].isupper():
        return False
    lowered = text.lower().replace("-", " ").split()
    return len(set(lowered)) == len(lowered)  # no repeated words ("Wood Wood")
