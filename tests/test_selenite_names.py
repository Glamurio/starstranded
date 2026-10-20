"""Selenite words must obey the syllable logic of data/namegen/voyage_selenite.cfg (Start + Middle + End)."""
import namegen
import naming
from planet import generate_planet


def _pools():
    ns = namegen.find_set("selenite", namegen.load_name_sets())
    pools = dict(ns.syllables)
    return ns, [tuple(p.lower() for p in pools[k]) for k in ("s", "m", "e")]


def _fits(word, starts, middles, ends):
    return any(word.startswith(s) and any(word[len(s):].startswith(m) and word[len(s) + len(m):] == e for m in middles for e in ends)
               for s in starts)


def test_every_lexicon_word_is_start_middle_end():
    ns, (starts, middles, ends) = _pools()
    for concept, (word,) in naming.SELENITE.items():
        assert _fits(word, starts, middles, ends), (concept, word)
        assert not any(bad in word for bad in ns.illegal)
    assert len({w for (w,) in naming.SELENITE.values()}) == len(naming.SELENITE)


def test_every_planet_name_is_made_of_lexicon_words():
    planet = generate_planet(5, "selenite")
    ns, (starts, middles, ends) = _pools()
    for kind in list(planet.fauna) + list(planet.flora):
        for word in kind.name.replace("-", " ").lower().split():
            if word.isalpha() and word not in {"ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv"}:
                assert _fits(word, starts, middles, ends), (kind.name, word)


def test_glosses_are_english_and_shown_for_foreign_names_only():
    import lore
    selenite = generate_planet(5, "selenite")
    assert selenite.glosses
    name, gloss = selenite.glosses[0]
    assert lore.english_name(selenite, f"{name} hide") == f"{gloss} hide"
    assert lore.english_name(selenite, "red furred animal") is None
    assert generate_planet(5, "human").glosses == ()


def test_default_selenite_name_fits_the_cfg():
    import species
    _, (starts, middles, ends) = _pools()
    assert _fits(species.SELENITE_PEOPLE.default_name.lower(), starts, middles, ends)
