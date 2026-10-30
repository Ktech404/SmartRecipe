"""Recipe search provider interface.  (SCRUM-13)

An "interface" is a promise: any provider (LangSearch today, something else
later) must offer a search() method that takes a RecipeSearchQuery and returns
RawRecipe objects. The rest of the app only ever talks to this interface, so
swapping providers does not touch the matching logic (requirement 2.5.2).

Why RawRecipe looks like this
- LangSearch is a general web search, not a recipe API. It gives us a page
  title, a URL, and the page's text. So page_text is the main field.
- ingredient_lines and instructions start empty. The ingestion step fills them
  by asking Gemini to read page_text (SCRUM-15). A provider that already returns
  structured data can fill them directly and leave page_text empty.
- Nothing here is stored yet. Ingestion decides what goes into the database.

The interface is synchronous to keep it simple. FastAPI runs normal `def`
endpoints in a thread pool, which is fine at our scale.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

# frozen=True makes instances read-only, so nothing can change them by accident.


@dataclass(frozen=True)
class RecipeSearchQuery:
    ingredients: tuple[str, ...]
    max_minutes: int | None = None
    servings: int | None = None
    tools: tuple[str, ...] = ()
    description: str | None = None
    limit: int = 10


@dataclass(frozen=True)
class RawRecipe:
    """A recipe as the provider returned it, before parsing and storage."""

    source_url: str
    title: str
    source_name: str | None = None  # the site name, for attribution
    image_url: str | None = None
    # Raw ingredient lines such as "2 cloves garlic, minced". Empty until parsed.
    ingredient_lines: tuple[str, ...] = ()
    instructions: str | None = None
    # Unstructured page text. Gemini turns this into the fields above.
    page_text: str | None = None
    total_minutes: int | None = None
    servings: int | None = None
    cuisine: str | None = None


# --------------------------------------------------------------------------
# Errors. The search flow catches ProviderError to fall back to stored recipes
# (requirement 2.2.1.3). Subclasses say what kind of failure it was.
# --------------------------------------------------------------------------


class ProviderError(Exception):
    """Any failure talking to a recipe provider."""


class ProviderTimeout(ProviderError):
    pass


class ProviderRateLimited(ProviderError):
    """HTTP 429. If retry_after is set, wait that many seconds.

    LangSearch can also return 429 when the daily token allowance is used up.
    That only resets at 00:00 UTC, so retrying right away will not help.
    """

    def __init__(self, message: str = "rate limited", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class RecipeSearchProvider(ABC):
    """Every provider must subclass this and implement search()."""

    name: str

    @abstractmethod
    def search(self, query: RecipeSearchQuery) -> list[RawRecipe]:
        """Return up to query.limit recipes, or raise ProviderError."""
