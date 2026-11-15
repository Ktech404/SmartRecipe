"""Run one real search through LangSearchProvider and print what came back.

Uses about 2,500 tokens of your daily allowance (one 10-result search).
Run from backend/:
    python -m scripts.try_langsearch chicken rice garlic
Needs LANGSEARCH_API_KEY in your environment or in backend/.env.
"""

import sys

from dotenv import load_dotenv

from app.providers.base import ProviderError, RecipeSearchQuery
from app.providers.langsearch import LangSearchProvider


def main() -> None:
    load_dotenv()
    ingredients = tuple(sys.argv[1:]) or ("chicken", "rice", "garlic")
    provider = LangSearchProvider.from_env()
    try:
        results = provider.search(RecipeSearchQuery(ingredients=ingredients, limit=10))
    except ProviderError as error:
        raise SystemExit(f"Search failed: {type(error).__name__}: {error}")
    print(f"{len(results)} results, {provider.tokens_used} tokens\n")
    for r in results:
        print(f"- {r.title}\n  {r.source_url}  ({r.source_name}, {len(r.page_text or '')} chars)")


if __name__ == "__main__":
    main()
