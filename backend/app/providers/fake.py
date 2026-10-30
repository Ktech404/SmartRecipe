"""A fake provider for tests and for working without API keys.  (SCRUM-13)

It returns whatever recipes you give it, or raises an error you choose. That
lets us test "what happens when the provider is down" without a real outage.
"""

from collections.abc import Iterable

from app.providers.base import (
    ProviderError,
    RawRecipe,
    RecipeSearchProvider,
    RecipeSearchQuery,
)


class FakeRecipeProvider(RecipeSearchProvider):
    name = "fake"

    def __init__(
        self,
        recipes: Iterable[RawRecipe] = (),
        error: ProviderError | None = None,
    ) -> None:
        self._recipes = list(recipes)
        self._error = error
        self.queries: list[RecipeSearchQuery] = []  # every query we were asked

    def search(self, query: RecipeSearchQuery) -> list[RawRecipe]:
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        return self._recipes[: query.limit]
