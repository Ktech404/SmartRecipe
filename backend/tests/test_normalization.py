import pytest

from app.services.normalization import (
    build_lookup,
    normalize_ingredient,
    resolve_ingredient,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Garlic", "garlic"),
        ("  RICE  ", "rice"),
        ("2 cloves garlic, minced", "garlic"),
        ("1/2 cup chopped fresh parsley", "parsley"),
        ("1 1/2 cups of flour", "flour"),
        ("500g chicken breast", "chicken breast"),
        ("1 lb boneless skinless chicken breasts", "chicken breast"),
        ("2-3 large eggs", "egg"),
        ("1 can black beans, drained", "black bean"),
        ("olive oil (extra virgin)", "olive oil"),
        ("extra virgin olive oil", "extra virgin olive oil"),
        ("Chicken breasts", "chicken breast"),
        ("Black beans", "black bean"),
        ("Tomatoes", "tomato"),
        ("Cherries", "cherry"),
        ("Peaches", "peach"),
        ("Bay leaves", "bay leaf"),
        ("ground beef", "ground beef"),
        ("Hummus", "hummus"),
        ("Molasses", "molasses"),
        ("Asparagus", "asparagus"),
        ("Jalape\u00f1o peppers", "jalapeno pepper"),
        ("all-purpose flour", "all purpose flour"),
        ("confectioners' sugar", "confectioners sugar"),
        ("clove", "clove"),
        ("4 cloves", ""),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_ingredient(raw, expected):
    assert normalize_ingredient(raw) == expected


def test_normalize_is_idempotent():
    for raw in ["2 cloves garlic, minced", "Black beans", "Tomatoes", "Bay leaves"]:
        once = normalize_ingredient(raw)
        assert normalize_ingredient(once) == once


def test_synonym_resolves_to_canonical():
    lookup = build_lookup(["beef", "garlic"], {"sirloin steak": "beef"})
    assert resolve_ingredient("Sirloin steak", lookup) == "beef"
    assert resolve_ingredient("2 lb sirloin steaks", lookup) == "beef"


def test_plural_and_case_match_canonical_name():
    lookup = build_lookup(["Black beans", "Tomato"], {})
    assert resolve_ingredient("black bean", lookup) == "Black beans"
    assert resolve_ingredient("TOMATOES", lookup) == "Tomato"


def test_unknown_ingredient_returns_none():
    lookup = build_lookup(["garlic"], {})
    assert resolve_ingredient("plutonium", lookup) is None
    assert resolve_ingredient("", lookup) is None


def test_alias_that_matches_its_own_canonical_is_allowed():
    lookup = build_lookup(["all purpose flour"], {"all-purpose flour": "all purpose flour"})
    assert lookup["all purpose flour"] == "all purpose flour"


def test_two_canonicals_with_same_key_are_rejected():
    with pytest.raises(ValueError):
        build_lookup(["tomato", "tomatoes"], {})


def test_alias_to_unknown_canonical_is_rejected():
    with pytest.raises(ValueError):
        build_lookup(["garlic"], {"scallion": "green onion"})


def test_alias_claimed_by_two_canonicals_is_rejected():
    with pytest.raises(ValueError):
        build_lookup(["beef", "pork"], {"steak": "beef", "steaks": "pork"})


def test_alias_colliding_with_other_canonical_is_rejected():
    with pytest.raises(ValueError):
        build_lookup(["beef", "steak"], {"steaks": "beef"})
