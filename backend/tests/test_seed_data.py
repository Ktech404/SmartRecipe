"""Checks on the seed CSV files. No database needed."""
from scripts.seed import (load_allergen_groups, load_ingredient_allergen_groups,
                          load_ingredient_parents, load_ingredients, load_synonyms)


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


# ---- the ingredient hierarchy (ingredient_parents.csv) --------------------------


def test_every_parent_link_points_at_real_ingredients():
    names = {n for n, _, _ in load_ingredients()}
    for child, parent in load_ingredient_parents():
        assert child in names, f"unknown ingredient {child!r}"
        assert parent in names, f"unknown parent {parent!r}"


def test_an_ingredient_has_one_parent_and_there_are_no_loops():
    links = load_ingredient_parents()
    children = [c for c, _ in links]
    assert len(children) == len(set(children)), "an ingredient is listed with two parents"
    parent_of = dict(links)
    for start in parent_of:
        seen, current = {start}, parent_of.get(start)
        while current is not None:
            assert current not in seen, f"loop through {current!r}"
            seen.add(current)
            current = parent_of.get(current)


def test_a_child_never_gains_an_allergen_group_from_its_parent():
    """Children inherit their parent's allergen groups, so a group on the parent that
    the child does not belong to would wrongly block it (corn tortilla is not gluten)."""
    groups: dict[str, set[str]] = {}
    for ingredient, group in load_ingredient_allergen_groups():
        groups.setdefault(ingredient, set()).add(group)
    for child, parent in load_ingredient_parents():
        extra = groups.get(parent, set()) - groups.get(child, set())
        assert not extra, f"{child!r} would inherit {sorted(extra)} from {parent!r}"


def test_general_cheese_is_dairy_and_the_cheeses_sit_under_it():
    assert ("cheese", "dairy") in load_ingredient_allergen_groups()
    parent_of = dict(load_ingredient_parents())
    assert parent_of["cheddar cheese"] == "cheese"
    assert parent_of["mozzarella cheese"] == "cheese"
    assert "cream cheese" not in parent_of and "cottage cheese" not in parent_of


def test_chicken_is_the_parent_of_every_chicken_cut():
    parent_of = dict(load_ingredient_parents())
    for cut in ["chicken breast", "chicken thigh", "chicken wing", "whole chicken", "ground chicken"]:
        assert parent_of[cut] == "chicken"
    assert "chicken" in {n for n, _, _ in load_ingredients()}
    assert "chicken" not in load_synonyms()  # bare "chicken" is its own ingredient now


def test_every_dairy_looking_ingredient_is_in_the_dairy_group():
    """Cheeses, creams and cream soups are dairy. Plant milks, nut butters and squash
    only look like it, so they are listed as the known exceptions."""
    dairy = {i for i, g in load_ingredient_allergen_groups() if g == "dairy"}
    not_dairy = {"coconut milk", "coconut cream", "almond milk", "oat milk", "soy milk",
                 "peanut butter", "almond butter", "butternut squash"}
    for name, _, _ in load_ingredients():
        looks_dairy = any(word in name for word in ("cheese", "cream", "milk", "yogurt", "butter"))
        if looks_dairy and name not in not_dairy:
            assert name in dairy, f"{name!r} should be in the dairy allergen group"


def test_generic_herb_bean_and_pecorino_are_in_the_hierarchy():
    names = {n for n, _, _ in load_ingredients()}
    parent_of = dict(load_ingredient_parents())
    for name in ["herb", "bean", "pecorino romano cheese"]:
        assert name in names
    assert parent_of["basil"] == "herb"
    assert parent_of["black bean"] == "bean"
    assert parent_of["pecorino romano cheese"] == "cheese"
    assert "green bean" not in parent_of and "chickpea" not in parent_of
