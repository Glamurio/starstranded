import colornames


def test_a_colour_gets_the_name_of_the_nearest_known_colour():
    assert colornames.name_of((0, 0, 0)) == "black"
    assert colornames.name_of((250, 250, 250)) in ("white", "snow", "ivory")
    assert colornames.name_of((255, 0, 0)) == "red"
    assert colornames.name_of((0, 0, 250)) == "blue"
    assert colornames.name_of((70, 200, 170)) in ("turquoise", "verdigris", "aquamarine", "jade")


def test_nearest_lists_distinct_names_best_first():
    found = colornames.nearest((110, 140, 60), 3)
    assert len(set(found)) == 3 and found[0] == colornames.name_of((110, 140, 60))
