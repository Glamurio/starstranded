import random

import naming
from naming import CULTURES, Namer, hue_name, provisional, salient_traits
from materials import PROPERTY_KEYS


def random_props(rng):
    return {k: round(rng.uniform(0, 10), 1) for k in PROPERTY_KEYS}


def test_hue_names():
    assert hue_name((200, 30, 30)) == "red"
    assert hue_name((40, 60, 200)) == "blue"
    assert hue_name((250, 250, 250)) == "white"
    assert hue_name((10, 10, 10)) == "black"
    assert hue_name((120, 80, 40)) == "brown"
    assert hue_name((60, 190, 70)) == "green"


def test_salient_traits_follow_the_properties():
    props = {"elasticity": 9, "density": 1, "hardness": 5, "radioactivity": 0}
    traits = salient_traits(props)
    assert [t[:2] for t in traits] == [("elasticity", "high"), ("density", "low")]
    assert salient_traits({"hardness": 5, "toughness": 5}) == []
    assert salient_traits({"radioactivity": 6})[0][:2] == ("radioactivity", "high")


def test_elastic_blue_tree_is_called_something_springy_or_blue():
    props = {"elasticity": 9.5, "toughness": 5}
    names = {Namer(s, "human").name("w1", "wood", (30, 60, 200), props).text.lower() for s in range(40)}
    assert any("spring" in n or "whip" in n or "flex" in n or "azure" in n or "blue" in n or "cobalt" in n or "sky" in n for n in names)
    assert all("heavy" not in n and "lead" not in n for n in names)


def test_names_are_deterministic_and_order_independent_for_the_same_key():
    props = {"elasticity": 9, "hardness": 8}
    a = Namer(7).name("m1", "wood", (10, 90, 200), props)
    b = Namer(7).name("m1", "wood", (10, 90, 200), props)
    assert a == b
    assert Namer(7).name("m1", "wood", (10, 90, 200), props) != Namer(8, "mau").name("m1", "wood", (10, 90, 200), props)


def test_reasons_are_true_of_the_properties():
    rng = random.Random(3)
    for i in range(300):
        props = random_props(rng)
        name = Namer(i).name(f"k{i}", "stone", (rng.randrange(256), rng.randrange(256), rng.randrange(256)), props)
        for prop, direction in name.reasons:
            if direction == "high":
                assert props[prop] >= 4
            else:
                assert props[prop] <= 2.5


def test_a_planet_of_names_is_unique_and_well_formed():
    rng = random.Random(11)
    for culture in CULTURES:
        namer = Namer(99, culture)
        texts = []
        for i in range(120):
            family = rng.choice(["wood", "stone", "metal", "fiber", "animal", "furred", "tree", "shrub"])
            n = namer.name(f"{culture}{i}", family, (rng.randrange(256), rng.randrange(256), rng.randrange(256)), random_props(rng))
            texts.append(n.text)
            assert 4 <= len(n.text) <= 28 and n.text[0].isupper(), n.text
            assert "  " not in n.text and "--" not in n.text and not n.text.endswith("-"), n.text
        assert len({naming._norm(t) for t in texts}) == len(texts), f"duplicate names in {culture}"


def test_cultures_produce_different_names_for_the_same_thing():
    props = {"elasticity": 9, "density": 1}
    results = {c: Namer(5, c).name("x", "wood", (200, 50, 50), props).text for c in CULTURES}
    assert len(set(results.values())) == len(CULTURES)


def test_gloss_explains_the_name():
    n = Namer(1, "mau").name("x", "wood", (200, 50, 50), {"elasticity": 9})
    assert "wood" in n.gloss or "tree" in n.gloss


def test_provisional_description_hides_the_name():
    assert provisional("tree", (30, 60, 200)) == "blue tree"
    assert provisional("animal", (230, 120, 20), furred=True) == "orange furred animal"
