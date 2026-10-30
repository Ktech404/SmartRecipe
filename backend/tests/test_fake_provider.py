"""Tests for the provider interface and fake provider (SCRUM-13)."""
import pytest

from app.providers.base import (
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    RawRecipe,
    RecipeSearchProvider,
    RecipeSearchQuery,
)
from app.providers.fake import FakeRecipeProvider


def _recipe(n: int) -> RawRecipe:
    return RawRecipe(source_url=f"https://example.com/{n}", title=f"Recipe {n}")


def test_returns_recipes_up_to_limit():
    provider = FakeRecipeProvider([_recipe(1), _recipe(2), _recipe(3)])
    results = provider.search(RecipeSearchQuery(ingredients=("rice",), limit=2))
    assert [r.title for r in results] == ["Recipe 1", "Recipe 2"]


def test_records_queries():
    provider = FakeRecipeProvider([_recipe(1)])
    query = RecipeSearchQuery(ingredients=("rice", "garlic"), max_minutes=30)
    provider.search(query)
    assert provider.queries == [query]


def test_raises_configured_error():
    provider = FakeRecipeProvider(error=ProviderTimeout("slow"))
    with pytest.raises(ProviderError):
        provider.search(RecipeSearchQuery(ingredients=("rice",)))


def test_error_types_share_a_base_class():
    assert issubclass(ProviderTimeout, ProviderError)
    assert issubclass(ProviderRateLimited, ProviderError)
    assert ProviderRateLimited(retry_after=5).retry_after == 5


def test_interface_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        RecipeSearchProvider()


def test_raw_recipe_can_carry_page_text_before_parsing():
    recipe = RawRecipe(
        source_url="https://example.com/x",
        title="Garlic rice",
        page_text="Ingredients: 2 cloves garlic ... Instructions: ...",
    )
    assert recipe.ingredient_lines == ()
    assert recipe.instructions is None
    assert "Ingredients" in recipe.page_text
