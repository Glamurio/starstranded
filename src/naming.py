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

import colornames
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
                 "coal", "plant", "bush", "grass", "reed", "coat", "hopper", "runner", "shell", "wing", "horn", "root",
                 "flower", "bloom", "bell", "blossom", "star", "aster")

FAMILY_NOUNS: Dict[str, Tuple[str, ...]] = {
    "wood": ("wood", "tree"), "stone": ("stone", "rock"), "metal": ("metal",), "fiber": ("fibre", "plant"),
    "hide": ("hide",), "bone": ("bone",), "clay": ("clay",), "sand": ("sand",), "glass": ("glass",),
    "ceramic": ("clay",), "crystal": ("crystal", "stone"), "fuel": ("coal", "stone"), "organic": ("plant",),
    "composite": ("wood",),
    # organisms
    "tree": ("tree", "wood"), "shrub": ("bush", "plant"), "flower": ("flower", "bloom", "bell", "blossom", "star", "aster"), "grass": ("grass", "reed"), "fungus": ("plant",),
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
    "red": ("Red", "Scarlet", "Crimson", "Ruby", "Cardinal", "Madder", "Maroon", "Wine"), "orange": ("Orange", "Amber", "Copper", "Rust", "Ochre", "Tangerine"),
    "yellow": ("Yellow", "Gold", "Straw", "Saffron", "Citrine", "Mustard"), "green": ("Green", "Moss", "Lichen", "Jade", "Sage", "Olive", "Emerald", "Viridian"),
    "teal": ("Teal", "Verdigris", "Aqua", "Turquoise", "Lagoon"), "blue": ("Blue", "Azure", "Cobalt", "Sky", "Cerulean", "Sapphire", "Navy"),
    "indigo": ("Indigo", "Midnight", "Navy", "Dusk", "Ink"), "violet": ("Violet", "Lilac", "Plum", "Orchid", "Amethyst", "Mauve"), "pink": ("Pink", "Rose", "Blush", "Coral", "Peach", "Carnation"),
    "brown": ("Brown", "Umber", "Chestnut", "Russet", "Sepia", "Bronze"), "white": ("White", "Pale", "Ivory", "Snow", "Pearl", "Chalk"),
    "black": ("Black", "Soot", "Ebony", "Jet"), "grey": ("Grey", "Ash", "Slate", "Dun", "Smoke", "Pewter"),
    "wood": ("wood", "timber"), "tree": ("tree", "bole"), "stone": ("stone", "rock"), "rock": ("rock", "crag"),
    "metal": ("metal", "steel"), "fibre": ("fibre", "strand"), "hide": ("hide", "skin"), "bone": ("bone",),
    "clay": ("clay", "mud"), "sand": ("sand", "grit"), "glass": ("glass",), "crystal": ("crystal", "spar"),
    "coal": ("coal", "cinder"), "plant": ("plant", "weed"), "bush": ("bush", "shrub"), "grass": ("grass", "sedge"),
    "reed": ("reed", "cane"), "coat": ("coat", "pelt", "fur"), "hopper": ("hopper", "hare"), "runner": ("runner", "stalker"),
    "shell": ("shell", "back"), "wing": ("wing",), "horn": ("horn",), "root": ("root", "tuber"),
    "flower": ("flower", "bud"), "bloom": ("bloom",), "bell": ("bell", "cup"), "blossom": ("blossom",), "star": ("star",), "aster": ("aster",),
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
    "flower": ("sheny",), "bloom": ("pert",), "bell": ("nebet",), "blossom": ("khenem",), "star": ("seba",), "aster": ("iaret",),
}


def _selenite_lexicon(concepts: Iterable[str]) -> Dict[str, Tuple[str, ...]]:
    """One word per concept, built ONLY from the syllable pools of `data/namegen/voyage_selenite.cfg` (Start + Middle + End,
    the cfg's own `$s$m$e` rule), so every Selenite word obeys the syllable logic Pascal researched from Voyage: Journey to
    the Moon. Deterministic per concept: a concept always has the same word."""
    import namegen
    name_set = namegen.find_set("selenite", namegen.load_name_sets())
    pools = dict(name_set.syllables)
    starts, middles, ends = (tuple(p.lower() for p in pools[k]) for k in ("s", "m", "e"))
    words: Dict[str, Tuple[str, ...]] = {}
    taken: Set[str] = set()
    for concept in sorted(concepts):
        rng = random.Random(hash_key("selenite:" + concept))
        for _ in range(500):
            word = rng.choice(starts) + rng.choice(middles) + rng.choice(ends)
            if word in taken or namegen._tidy(word).lower() != word or any(bad in word for bad in name_set.illegal):
                continue
            taken.add(word)
            words[concept] = (word,)
            break
        else:  # pragma: no cover - 500 draws out of 1 100+ combinations
            raise RuntimeError(f"no Selenite word for {concept!r}")
    return words


SELENITE: Dict[str, Tuple[str, ...]] = {}

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
# Which animals have which covering (planet.py): fur -> small_herbivore, grazer, predator; feather -> bird; skin -> animal;
# chitin and scale -> crawler, serpent. Hard chitin or scale is ordinary for them; "hard" is only remarkable on a furred beast.
FAMILY_TYPICAL["scaled"] = dict(FAMILY_TYPICAL["hide"], hardness=5.5, toughness=5, tenacity=2.5, density=4, insulation=2,
                                flammability=0.8, combustibility=0.8)
FAMILY_TYPICAL["feathered"] = dict(FAMILY_TYPICAL["hide"], insulation=7.5, tenacity=2, toughness=2, hardness=0.6, density=0.8)
FAMILY_TYPICAL["skinned"] = dict(FAMILY_TYPICAL["hide"], insulation=3, tenacity=5, toughness=4, hardness=1.5, flammability=4, density=2)
for _animal in ("animal",):
    FAMILY_TYPICAL[_animal] = FAMILY_TYPICAL["skinned"]
for _animal in ("furred", "small_herbivore", "grazer", "predator"):
    FAMILY_TYPICAL[_animal] = FAMILY_TYPICAL["hide"]
FAMILY_TYPICAL["bird"] = FAMILY_TYPICAL["feathered"]
for _animal in ("armoured", "crawler", "serpent"):
    FAMILY_TYPICAL[_animal] = FAMILY_TYPICAL["scaled"]
for _plant in ("tree", "shrub", "grass", "fungus"):
    FAMILY_TYPICAL[_plant] = FAMILY_TYPICAL["wood"] if _plant == "tree" else FAMILY_TYPICAL["fiber"]
NOUNLIKE_EPITHETS = {"spring", "spark", "glow", "grit", "ray", "bind", "heat", "tinder", "fuel"}
"""Epithets that can stand alone as a noun ("Indigo Spring", "Red Grit"); adjectives always need a noun."""


@dataclass(frozen=True)
class Name:
    text: str
    gloss: str                      # what it means, in plain English ("blue spring-wood")
    reasons: Tuple[Tuple[str, str], ...] = ()   # (property, "high"/"low") justifications, for tests and the codex
    modifier: str = ""              # organisms: the distinguishing word of "scarlet fir" (its children, the fruit, share it)
    form: str = ""                  # organisms: what it looks like: "fir"


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
    for limit, name in ((15, "red"), (40, "orange"), (68, "yellow"), (165, "green"), (195, "teal"), (245, "blue"),
                        (268, "indigo"), (318, "violet"), (345, "pink"), (361, "red")):
        if deg < limit:
            return name
    return "red"


HUE_TOLERANCE = 9.0         # degrees a shade may drift from its base colour's hue
SATURATION_TOLERANCE = 0.18
VALUE_TOLERANCE = 0.2


def same_color_group(base: RGB, shifted: RGB) -> bool:
    """Is `shifted` still recognisably `base`? Strict: it must have the same colour word (`hue_name`), and for a saturated base
    the hue may drift only a few degrees and neither saturation nor brightness may jump. Used for every random shade."""
    if hue_name(base) != hue_name(shifted):
        return False
    bh, bs, bv = colorsys.rgb_to_hsv(*(c / 255 for c in base))
    sh, ss, sv = colorsys.rgb_to_hsv(*(c / 255 for c in shifted))
    if abs(bs - ss) > SATURATION_TOLERANCE or abs(bv - sv) > VALUE_TOLERANCE:
        return False
    if bs >= 0.25 and bv >= 0.25:
        drift = abs(bh - sh) * 360
        drift = min(drift, 360 - drift)
        if drift > HUE_TOLERANCE:
            return False
    return True


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



_ONSETS = ("v", "k", "th", "s", "m", "l", "r", "z", "n", "b", "d", "f", "g", "t", "h", "j", "sh")
_VOWELS = ("a", "e", "i", "o", "u")
_CODAS = ("n", "r", "l", "s", "x", "m", "k", "", "")


def coined(rng: random.Random) -> str:
    """An invented but pronounceable word ("vasmir", "thelon") for things that have no everyday name yet."""
    return "".join(rng.choice(_ONSETS) + rng.choice(_VOWELS) + rng.choice(_CODAS) for _ in range(2))


class Namer:
    """Names one planet's things for one culture, resolving collisions in call order."""

    def __init__(self, seed: int, culture: str = "human"):
        assert culture in CULTURES, f"unknown naming culture {culture!r}"
        self.seed = seed
        self.culture = culture
        self.used: Set[str] = set()
        self.glosses: Dict[str, str] = {}   # name text -> plain English meaning (for non-English cultures)

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
                self.glosses[candidate.text] = candidate.gloss
                return candidate
        # exhausted: a coined qualifier keeps names unique ("vasmir pale stone"); numerals are the very last resort
        base = next((b for b in (self._compose(rng, traits, colour, nouns, k) for k in range(12, 40)) if _well_formed(b.text)),
                    self._compose(rng, traits, colour, nouns, 0))
        text = self._unique(rng, base.text)
        self.glosses[text] = base.gloss
        return Name(text, base.gloss, base.reasons)

    def _unique(self, rng: random.Random, base: str) -> str:
        """`base` made unique among this planet's names by a coined qualifier before it (never "II")."""
        for _ in range(60 if self.culture == "human" else 0):    # (the other cultures keep a short catalogue numeral: their words are long)
            text = _plain(self.culture, f"{coined(rng)} {base}")
            if _norm(text) not in self.used:
                self.used.add(_norm(text))
                return text
        serial = 2
        while _norm(f"{base} {_roman(serial)}") in self.used:
            serial += 1
        text = f"{base} {_roman(serial)}"
        self.used.add(_norm(text))
        return text

    def organism(self, key: str, forms: Sequence[str], color: RGB, props: Optional[Mapping[str, float]] = None, family: str = "tree") -> Name:
        """A plant's name from what it looks like: a distinguishing word and its form ("scarlet fir", "vasmir toadstool").
        `forms` are the everyday words for its shape (chosen from its sprite). Other cultures keep their own word-building."""
        if self.culture != "human" or not forms:
            return self.name(key, family, color, props)
        rng = random.Random(mix_seed(self.seed, hash_key(key)))
        colour = hue_name(color)
        traits = salient_traits(props or {}, limit=1, family=family)
        palette = colornames.nearest(color, 2)           # the actual colour, by name: the nearest two of a table of web colour names
        trait_words = [w.lower() for w in HUMAN[TRAIT_CONCEPTS[(traits[0][0], traits[0][1])]]] if traits else []
        for attempt in range(48):
            form = forms[attempt % len(forms)] if attempt < 2 * len(forms) else rng.choice(forms)
            roll = rng.random() if attempt < 8 else 0.7          # the plain colour words run out first: then coin one
            if roll < 0.5:
                modifier = rng.choice(palette)
            elif roll < 0.9:
                modifier = coined(rng)
            else:
                modifier = rng.choice(trait_words or palette)
            text = f"{modifier} {form}"
            if _norm(text) not in self.used and modifier not in form:
                self.used.add(_norm(text))
                gloss = f"{colour} {form}"
                self.glosses[text] = gloss
                return Name(text, gloss, (), modifier, form)
        text = self._unique(rng, f"{rng.choice(palette)} {forms[0]}")
        return Name(text, f"{colour} {forms[0]}", (), text.split(" ")[0], forms[0])

    def fruit_of(self, key: str, parent: Name, nouns: Sequence[str]) -> str:
        """A fruit's name from its parent plant and its own kind: "scarlet" fir -> "scarlet cone"; a clash adds the parent's form."""
        rng = random.Random(mix_seed(self.seed, hash_key(key)))
        if self.culture != "human" or not parent.modifier:
            return self.fruit(key, (128, 128, 128), rng.choice(list(nouns)))
        noun = rng.choice(list(nouns))
        extra = " ".join(w for w in parent.form.split() if w not in noun.split())   # "barrel" of "barrel cactus" before "cactus fig"
        candidates = [f"{parent.modifier} {noun}"] + ([f"{parent.modifier} {extra} {noun}"] if extra else [])
        for text in candidates:
            if _norm(text) not in self.used:
                self.used.add(_norm(text))
                self.glosses[text] = text
                return text
        text = self._unique(rng, f"{parent.modifier} {noun}")
        return text

    def fruit(self, key: str, color: RGB, shape: str) -> str:
        """A fruit's name: its colour word and its shape ("Azure pear"); other cultures name the colour and "plant fruit"."""
        rng = random.Random(mix_seed(self.seed, hash_key(key)))
        colour = hue_name(color)
        for _ in range(8):
            word = ((colornames.nearest(color, 3) + [coined(rng)])[_] if _ < 4 else coined(rng)) if self.culture == "human" else self._word(rng, colour)
            text = f"{word} {shape}" if self.culture == "human" and shape else f"{word}-{self._word(rng, 'plant')}"
            text = _plain(self.culture, _tidy(text) if self.culture != "human" else f"{word} {shape}")
            if _norm(text) not in self.used:
                self.used.add(_norm(text))
                self.glosses[text] = f"{colour} {shape or 'fruit'}"
                return text
        base = f"{word} {shape}".strip() if self.culture == "human" else f"{word}-{self._word(rng, 'plant')}"
        serial = 2
        while _norm(f"{base} {_roman(serial)}") in self.used:
            serial += 1
        text = f"{_plain(self.culture, _tidy(base))} {_roman(serial)}"
        self.used.add(_norm(text))
        self.glosses[text] = f"{colour} {shape or 'fruit'}"
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
        return Name(_plain(self.culture, _tidy(text)), gloss, reasons)

    def _join(self, a: str, b: str, compound: bool) -> str:
        if not compound:
            return f"{a} {b}"
        if self.culture == "human":
            return a + b.lower()
        if self.culture == "selenite":
            return f"{a} {b}"   # each Selenite word keeps its own Start-Middle-End shape
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


PROPER_WORDS = ("Human", "Selenite", "Mau", "Selenites", "Harmonic", "Egyptian")


def _plain(culture: str, text: str) -> str:
    """Only people's names are capitalised: the name of a plant, creature or material is written in lower case, whatever
    language it was built from. (A corporate catalogue code such as "Fenlith-5B" is a code, not a word.)"""
    return text if culture == "corporate" else text.lower()


def lower_first(text: str) -> str:
    """Everyday things are written in lower case ("hide", "ration pack"); people, races and invented names keep their capital.
    A text that names someone ("Jon, the human") is left alone."""
    if not text or ", the " in text:
        return text
    first = text.split(" ", 1)[0]
    if first in PROPER_WORDS or first.rstrip("'s") in PROPER_WORDS:
        return text
    return text[0].lower() + text[1:]


SELENITE.update(_selenite_lexicon(MAU))
