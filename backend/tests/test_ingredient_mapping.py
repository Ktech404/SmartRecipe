from pathlib import Path

import pytest

from app.providers.base import RawRecipe
from app.services.ingredient_mapping import (
    map_ingredient_line,
    map_recipe,
    parse_quantity_and_unit,
)
from app.services.normalization import build_lookup, load_seed_lookup

NAMES = ["garlic", "pasta", "salt", "black pepper", "olive oil", "chicken breast",
         "egg", "rice", "onion", "butter", "chicken thigh", "ginger", "lime"]
SYNONYMS = {"eggs": "egg", "pepper": "black pepper"}
LOOKUP = build_lookup(NAMES, SYNONYMS)


def _recipe(*lines):
    return RawRecipe(source_url="https://example.com/r", title="T", ingredient_lines=tuple(lines))


# ---- quantity and unit --------------------------------------------------------


@pytest.mark.parametrize(
    "line, expected",
    [
        ("2 cloves garlic, minced", (2.0, "clove")),
        ("1 1/2 cups rice", (1.5, "cup")),
        ("1/2 tsp salt", (0.5, "tsp")),
        ("500g chicken breast", (500.0, "g")),
        ("2 tablespoons olive oil", (2.0, "tbsp")),
        ("1 lb chicken breast", (1.0, "lb")),
        ("2 pounds chicken breast", (2.0, "lb")),
        ("2-3 large eggs", (2.0, None)),
        ("3 eggs", (3.0, None)),
        ("½ cup rice", (0.5, "cup")),
        ("Salt to taste", (None, None)),
        ("garlic", (None, None)),
    ],
)
def test_quantity_and_unit(line, expected):
    assert parse_quantity_and_unit(line) == expected


# ---- one line -----------------------------------------------------------------


def test_simple_line_is_mapped_with_quantity_and_unit():
    [item] = map_ingredient_line("2 cloves garlic, minced", LOOKUP)
    assert (item.name, item.quantity, item.unit) == ("garlic", 2.0, "clove")
    assert item.line == "2 cloves garlic, minced" and item.is_optional is False


def test_synonym_maps_to_the_canonical_name():
    [item] = map_ingredient_line("3 eggs", LOOKUP)
    assert item.name == "egg"


def test_optional_is_detected():
    [item] = map_ingredient_line("1 tbsp butter (optional)", LOOKUP)
    assert item.name == "butter" and item.is_optional is True


def test_salt_and_pepper_becomes_two_ingredients():
    items = map_ingredient_line("Salt and pepper to taste", LOOKUP)
    assert [i.name for i in items] == ["salt", "black pepper"]
    assert all(i.quantity is None for i in items)


@pytest.mark.parametrize(
    "line", ["Salt to taste", "salt, to taste", "Salt as needed", "olive oil for frying"]
)
def test_serving_notes_do_not_block_recognition(line):
    [item] = map_ingredient_line(line, LOOKUP)
    assert item.name in ("salt", "olive oil")


@pytest.mark.parametrize(
    "line, expected",
    [
        ("1 1/2 lbs boneless, skinless chicken thighs", "chicken thigh"),
        ("1 cup uncooked rice", "rice"),
        ("1 inch piece fresh ginger, grated", "ginger"),
        ("2-inch knob of ginger", "ginger"),
        ("juice of 1 lime", "lime"),
        ("zest of a lime", "lime"),
    ],
)
def test_common_recipe_wording_is_understood(line, expected):
    [item] = map_ingredient_line(line, LOOKUP)
    assert item.name == expected


def test_compound_line_needs_both_halves_known():
    assert map_ingredient_line("salt and unicorn dust", LOOKUP) is None


def test_unknown_line_returns_none():
    assert map_ingredient_line("1 cup dragon fruit", LOOKUP) is None


# ---- whole recipe -------------------------------------------------------------


def test_clean_recipe_is_ok():
    result = map_recipe(_recipe("200 g pasta", "2 cloves garlic", "salt"), LOOKUP)
    assert result.ok and result.reason is None
    assert [i.name for i in result.ingredients] == ["pasta", "garlic", "salt"]
    assert result.unrecognized == ()


def test_one_unrecognized_line_rejects_the_recipe_by_default():
    result = map_recipe(_recipe("200 g pasta", "2 cloves garlic", "1 cup dragon fruit"), LOOKUP)
    assert not result.ok
    assert result.unrecognized == ("1 cup dragon fruit",)
    assert "unrecognized" in result.reason
    assert len(result.ingredients) == 2  # the good ones are still reported


def test_limit_can_be_loosened():
    lines = ("200 g pasta", "2 cloves garlic", "1 cup dragon fruit")
    assert map_recipe(_recipe(*lines), LOOKUP, max_unrecognized=1).ok


def test_section_headers_and_blank_lines_are_ignored():
    result = map_recipe(_recipe("For the sauce:", "", "  ", "2 cloves garlic", "salt"), LOOKUP)
    assert result.ok and result.unrecognized == ()


def test_duplicate_ingredients_are_listed_once_keeping_the_first():
    result = map_recipe(_recipe("1 tsp salt", "2 cloves garlic", "salt, to taste"), LOOKUP)
    assert [i.name for i in result.ingredients] == ["salt", "garlic"]
    assert result.ingredients[0].quantity == 1.0


def test_too_few_ingredients_is_rejected():
    result = map_recipe(_recipe("2 cloves garlic"), LOOKUP)
    assert not result.ok and "only 1" in result.reason
    assert map_recipe(_recipe("2 cloves garlic"), LOOKUP, min_ingredients=1).ok


def test_no_ingredient_lines_is_rejected():
    result = map_recipe(_recipe(), LOOKUP)
    assert not result.ok and "no ingredient lines" in result.reason


# ---- with the real vocabulary (arrives with SCRUM-38) -------------------------

SEED = Path(__file__).resolve().parent.parent / "seed"


@pytest.mark.skipif(
    not (SEED / "ingredients.csv").exists(), reason="seed CSVs arrive with SCRUM-38"
)
def test_realistic_recipe_with_the_seed_vocabulary():
    lookup = load_seed_lookup(SEED)
    lines = (
        "2 lbs boneless skinless chicken breasts",
        "3 cloves garlic, minced",
        "1 cup rice",
        "2 tablespoons olive oil",
        "Salt and pepper to taste",
    )
    result = map_recipe(_recipe(*lines), lookup)
    assert result.ok, (result.reason, result.unrecognized)
    names = [i.name for i in result.ingredients]
    assert {"chicken breast", "garlic", "olive oil", "salt"} <= set(names)
