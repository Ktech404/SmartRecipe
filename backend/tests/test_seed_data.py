"""Checks on the seed CSV files. No database needed."""
from scripts.seed import load_ingredients, load_synonyms


def test_no_duplicate_ingredient_names():
    names = [n for n, _, _ in load_ingredients()]
    assert len(names) == len(set(names))


def test_every_synonym_points_at_a_real_ingredient():
    names = {n for n, _, _ in load_ingredients()}
    for alias, canonical in load_synonyms().items():
        assert canonical in names, f"{alias!r} -> unknown {canonical!r}"


def test_no_alias_is_also_an_ingredient_name():
    names = {n for n, _, _ in load_ingredients()}
    clashes = [a for a in load_synonyms() if a in names]
    assert clashes == []


def test_old_seed_ingredients_still_present():
    names = {n for n, _, _ in load_ingredients()}
    for n in ["chicken breast", "beef", "garlic", "onion", "tomato", "rice", "pasta",
              "egg", "milk", "cheddar cheese", "salt", "black pepper", "water", "olive oil"]:
        assert n in names


def test_egg_is_dairy_and_staples_kept():
    by_name = {n: (c, s) for n, c, s in load_ingredients()}
    assert by_name["egg"][0] == "dairy"
    assert by_name["salt"][1] is True
