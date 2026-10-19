"""Item names: generated names are lower case, and a piece is not named twice ("rock stone")."""
import re

import items
import naming


def bare(text):
    """The name without a trailing catalogue numeral (" II")."""
    return re.sub(r" [IVX]+$", "", text)


def test_generated_names_are_lower_case_except_catalogue_codes():
    namer = naming.Namer(5)
    for i in range(10):
        assert bare(namer.name(f"w{i}", "wood", (120, 80, 40)).text).islower()
        assert bare(namer.fruit(f"f{i}", (200, 40, 40), "pear")).islower()
    assert naming.Namer(5, "corporate").name("c", "stone", (100, 100, 100)).text[0].isupper()


def test_a_branch_of_a_generated_wood_reads_in_lower_case():
    assert items.noun_title("kindle wood", "Branch") == "kindle wood branch"


def test_a_rock_piece_is_not_called_rock_stone():
    assert items.noun_title("grey rock", "Stone") == "grey rock"
    assert items.noun_title("Dunstone", "Stone") == "Dunstone"
    assert items.noun_title("rustore", "Ore") == "rustore"
    assert items.noun_title("rust", "Ore") == "rust ore"
