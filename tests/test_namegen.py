"""Pure-Python name generator (replaces tcod.namegen_*)."""
import random
import re
import time
import warnings

import pytest

import namegen
import utilities


@pytest.fixture(autouse=True)
def fresh_cache():
    namegen.load_name_sets.cache_clear()
    yield
    namegen.load_name_sets.cache_clear()


def test_all_shipped_cfg_files_parse_into_usable_sets():
    sets = namegen.load_name_sets()
    names = {s.name for s in sets}
    assert len(sets) >= 20 and {"selenite", "tree", "dwarf male", "region"} <= names
    for s in sets:
        assert s.rules, s.name
        assert s.syllables["s"], s.name
        assert namegen.generate_from_set(s), s.name


def test_cfg_files_are_parsed_once_not_per_call(monkeypatch):
    calls = []
    real = namegen.parse_name_sets
    monkeypatch.setattr(namegen, "parse_name_sets", lambda text: calls.append(1) or real(text))
    for _ in range(200):
        utilities.generate_name("selenite")
    n_files = len(list(namegen.DATA_DIR.glob("*.cfg")))
    assert len(calls) == n_files  # once per file, total, regardless of call count
    assert namegen.load_name_sets.cache_info().misses == 1


def test_does_not_touch_deprecated_tcod_namegen(monkeypatch):
    from tcod import libtcodpy

    def boom(*a, **k):
        raise AssertionError("tcod namegen must not be used")

    for fn in ("namegen_parse", "namegen_get_sets", "namegen_generate", "namegen_destroy"):
        monkeypatch.setattr(libtcodpy, fn, boom)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no FutureWarning about implicit libtcodpy either
        assert utilities.generate_name("selenite")


def test_selenite_names_look_right_and_vary():
    names = {utilities.generate_name("selenite") for _ in range(80)}
    assert len(names) > 25
    for n in names:
        assert re.fullmatch(r"[A-Z][a-z'-]+", n), n
        assert "brbr" not in n.lower()  # `illegal` list honoured


def test_names_are_reproducible_with_seeded_random():
    random.seed(99)
    a = [utilities.generate_name("dwarf male") for _ in range(10)]
    random.seed(99)
    b = [utilities.generate_name("dwarf male") for _ in range(10)]
    assert a == b


def test_origin_matching_is_case_insensitive_substring_with_fallback():
    assert " " in utilities.generate_name("TREE")  # "$s$m$e" with "_Oak"-style end syllables
    assert utilities.generate_name("no such origin")  # falls back to the first set


def test_generation_is_fast():
    t0 = time.perf_counter()
    for _ in range(2000):
        utilities.generate_name("selenite")
    assert time.perf_counter() - t0 < 1.0


def test_readme_example_and_wildcards():
    sets = namegen.parse_name_sets(
        'name "t" { syllablesStart = "Ivan" syllablesEnd = "Terrible" rules = "$s_the_$e" }'
    )
    assert namegen.generate_from_set(sets[0]) == "Ivan the Terrible"


def test_wildcard_chance_and_rule_weights():
    s = namegen.parse_name_sets(
        'name "t" { syllablesStart = "Aa" syllablesMiddle = "xx" syllablesEnd = "Bb" rules = "$s$0m$e" }'
    )[0]
    assert {namegen.generate_from_set(s) for _ in range(30)} == {"AaBb"}  # $0m never appears
    s = namegen.parse_name_sets(
        'name "t" { syllablesStart = "Aa" syllablesEnd = "Bb" rules = "$s, %0$e$e" }'
    )[0]
    assert {namegen.generate_from_set(s) for _ in range(40)} == {"Aa"}  # %0 rule never chosen


def test_illegal_substrings_are_rejected_and_retried():
    s = namegen.parse_name_sets(
        'name "t" { syllablesStart = "Bad, Good" syllablesEnd = "x" illegal = "bad" rules = "$s$e" }'
    )[0]
    assert {namegen.generate_from_set(s) for _ in range(50)} == {"Goodx"}


def test_phoneme_wildcards_and_escapes():
    s = namegen.parse_name_sets(
        'name "t" { phonemesVocals = "a" phonemesConsonants = "k" rules = "$c$v$c_/;" }'
    )[0]
    assert re.fullmatch(r"Kak ;", namegen.generate_from_set(s))


def test_triple_letters_and_double_separators_are_tidied():
    assert namegen._tidy("aaab--c  d") == "Aab-c d"
