"""Checks on the seed CSV files. No database needed."""
from scripts.seed import (load_allergen_groups, load_ingredient_allergen_groups,
                          load_ingredients, load_synonyms)


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


EXPECTED_GROUPS = {"dairy", "tree nuts", "eggs", "gluten", "shellfish", "peanuts", "soy", "fish"}


def test_the_expected_allergen_groups_exist_without_duplicates():
    groups = load_allergen_groups()
    assert len(groups) == len(set(groups))
    assert set(groups) == EXPECTED_GROUPS


def test_every_allergen_mapping_points_at_a_real_ingredient_and_group():
    names = {n for n, _, _ in load_ingredients()}
    groups = set(load_allergen_groups())
    for ingredient, group in load_ingredient_allergen_groups():
        assert ingredient in names, f"unknown ingredient {ingredient!r}"
        assert group in groups, f"unknown group {group!r}"


def test_no_duplicate_allergen_mappings_and_every_group_has_members():
    mappings = load_ingredient_allergen_groups()
    assert len(mappings) == len(set(mappings))
    used = {group for _, group in mappings}
    assert used == set(load_allergen_groups())


def test_key_allergen_examples():
    mappings = set(load_ingredient_allergen_groups())
    for pair in [
        ("milk", "dairy"), ("cheddar cheese", "dairy"), ("egg", "eggs"),
        ("mayonnaise", "eggs"), ("all purpose flour", "gluten"),
        ("spaghetti", "gluten"), ("soy sauce", "gluten"), ("soy sauce", "soy"),
        ("tofu", "soy"), ("almond", "tree nuts"), ("peanut butter", "peanuts"),
        ("shrimp", "shellfish"), ("salmon", "fish"), ("fish sauce", "fish"),
        ("worcestershire sauce", "fish"),
    ]:
        assert pair in mappings, pair


def test_plant_milks_and_plain_rice_are_not_flagged_as_dairy_or_gluten():
    mappings = set(load_ingredient_allergen_groups())
    for pair in [("coconut milk", "dairy"), ("almond milk", "dairy"),
                 ("soy milk", "dairy"), ("rice", "gluten"), ("coconut", "tree nuts")]:
        assert pair not in mappings, pair
