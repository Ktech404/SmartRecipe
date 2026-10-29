"""Tests for the search contract (SCRUM-12). Needs pydantic (installed with fastapi)."""
import pytest
from pydantic import ValidationError

from app.schemas.search import (
    EXAMPLE_REQUEST,
    EXAMPLE_RESPONSE,
    IngredientInput,
    SearchRequest,
    SearchResponse,
)


def test_documented_examples_are_valid():
    # If someone edits a model and forgets the example, this fails.
    SearchRequest.model_validate(EXAMPLE_REQUEST)
    SearchResponse.model_validate(EXAMPLE_RESPONSE)


def test_ingredient_name_is_trimmed():
    assert IngredientInput(name="  Garlic  ").name == "Garlic"


def test_blank_ingredient_name_is_rejected():
    with pytest.raises(ValidationError):
        IngredientInput(name="   ")


@pytest.mark.parametrize("quantity", [0, -1])
def test_non_positive_quantity_is_rejected(quantity):
    with pytest.raises(ValidationError):
        IngredientInput(name="rice", quantity=quantity)


def test_unknown_unit_is_rejected():
    with pytest.raises(ValidationError):
        IngredientInput(name="rice", unit="bucket")


def test_defaults():
    request = SearchRequest(ingredients=[])
    assert (request.limit, request.offset, request.tools) == (20, 0, [])


@pytest.mark.parametrize(
    "field, value",
    [("limit", 0), ("limit", 51), ("offset", -1), ("max_minutes", 0), ("servings", 0)],
)
def test_out_of_range_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        SearchRequest(ingredients=[], **{field: value})


def test_tools_are_cleaned():
    request = SearchRequest(ingredients=[], tools=[" Oven ", "", "AIR FRYER"])
    assert request.tools == ["oven", "air fryer"]


def test_too_many_ingredients_are_rejected():
    items = [{"name": f"item{i}"} for i in range(51)]
    with pytest.raises(ValidationError):
        SearchRequest(ingredients=items)
