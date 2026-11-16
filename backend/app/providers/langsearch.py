"""LangSearch recipe search provider.  (SCRUM-30)

LangSearch is a general web search API, not a recipe API. We send it a query
built from the user's ingredients and get back web pages: a title, a URL and a
text excerpt. Each page becomes a RawRecipe whose page_text is the excerpt; the
Gemini parser (SCRUM-31) later turns that text into ingredients and steps.

What we learned in the spike (docs/search-provider-spike.md):
- about half of the results are not recipes, so the parser must be able to say no
- the excerpt is usually the part of the page that best matches the query
- tokens, not requests, are what the free plan limits; one 10-result search
  costs about 2,400 tokens
- LangSearch can answer 429 when the daily token allowance is used up, and it
  only resets at 00:00 UTC, so retrying straight away will not help
- a search that finishes on the server still costs tokens when our side timed
  out, so this class never retries on its own

Standard library only. The HTTP call is a small function that tests replace
(the `post` argument), so no test touches the network.
"""

import json
import os
import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import urlparse

from app.providers.base import (
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    RawRecipe,
    RecipeSearchProvider,
    RecipeSearchQuery,
)

API_URL = "https://api.langsearch.com/v1/web-search"
MAX_COUNT = 50  # LangSearch accepts 1-50 results per search

# Pages that are archive copies, not the original recipe page.
DEFAULT_EXCLUDED_DOMAINS = ("web.archive.org",)

# Some sites publish the same recipe once per language under a language prefix
# (umami.recipes/pl/recipe/abc, /sv/recipe/abc, ...). The first live test returned
# 10 results that were only 3 recipes, because of this. Our app is English-only,
# so any URL whose first path segment is one of these language codes is dropped
# and the unprefixed (English) copy is kept.
_NON_ENGLISH_PREFIXES = frozenset(
    """ar bg cs da de el es et fi fr he hi hr hu it ja ko lt lv nb nl no pl pt ro
    ru sk sl sv th tr vi zh zh-hans zh-hant zh-cn zh-tw pt-br""".split()
)

# post(url, headers, body, timeout) -> parsed JSON. Raises a ProviderError subclass.
PostFunction = Callable[[str, dict[str, str], dict, float], dict]


def _post_json(url: str, headers: dict[str, str], body: dict, timeout: float) -> dict:
    """Send a JSON POST and return the parsed JSON, mapping failures to ProviderErrors."""
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                wait = float(retry_after) if retry_after is not None else None
            except ValueError:
                wait = None
            raise ProviderRateLimited("LangSearch rate limit or daily token limit", wait) from error
        if error.code in (401, 403):
            raise ProviderError(f"LangSearch rejected the API key (HTTP {error.code})") from error
        raise ProviderError(f"LangSearch returned HTTP {error.code}") from error
    except (TimeoutError, socket.timeout) as error:
        raise ProviderTimeout("LangSearch timed out") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise ProviderTimeout("LangSearch timed out") from error
        raise ProviderError(f"Could not reach LangSearch: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise ProviderError("LangSearch returned a response that is not JSON") from error


def _site_name(url: str) -> str | None:
    host = urlparse(url).hostname
    if not host:
        return None
    return host[4:] if host.startswith("www.") else host


def _is_localized_copy(url: str) -> bool:
    """True for URLs like https://site.com/pl/recipe/abc (a translated copy)."""
    path = urlparse(url).path.lstrip("/")
    first, _, rest = path.partition("/")
    return bool(rest) and first.lower() in _NON_ENGLISH_PREFIXES


def build_query_text(query: RecipeSearchQuery) -> str:
    """Turn the structured query into the plain-text search LangSearch expects."""
    parts = ["recipe with " + " ".join(query.ingredients)] if query.ingredients else ["recipe"]
    if query.description:
        parts.append(query.description.strip())
    return " ".join(parts)


class LangSearchProvider(RecipeSearchProvider):
    name = "langsearch"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 30.0,
        max_chars: int = 3000,
        excluded_domains: tuple[str, ...] = DEFAULT_EXCLUDED_DOMAINS,
        overfetch: int = 2,
        post: PostFunction = _post_json,
    ) -> None:
        if not api_key:
            raise ValueError("LangSearch needs an API key")
        self._api_key = api_key
        self._timeout = timeout
        self._max_chars = max_chars
        self._excluded = {d.lower() for d in excluded_domains}
        # We drop non-recipes' duplicates and translated copies after the search,
        # so ask for more than the caller wants and trim to the limit afterwards.
        # Tokens are not our constraint (see the spike), so this is cheap.
        self._overfetch = max(1, overfetch)
        self._post = post
        self.tokens_used = 0  # running total for this object, for logging

    @classmethod
    def from_env(cls, **kwargs) -> "LangSearchProvider":
        key = os.environ.get("LANGSEARCH_API_KEY")
        if not key:
            raise ProviderError("LANGSEARCH_API_KEY is not set")
        return cls(key, **kwargs)

    def search(self, query: RecipeSearchQuery) -> list[RawRecipe]:
        body = {
            "query": build_query_text(query),
            "count": max(1, min(query.limit * self._overfetch, MAX_COUNT)),
            "freshness": "noLimit",
            # Ask for page text; without this we only get a short snippet.
            "contents": {"text": {"maxCharacters": self._max_chars}},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = self._post(API_URL, headers, body, self._timeout)
        return self._parse(payload, query.limit)

    def _parse(self, payload: dict, limit: int) -> list[RawRecipe]:
        if not isinstance(payload, dict):
            raise ProviderError("LangSearch returned an unexpected response")
        code = payload.get("code")
        if code not in (None, 200):
            raise ProviderError(f"LangSearch reported an error (code {code})")

        usage = payload.get("usage") or {}
        self.tokens_used += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        pages = ((payload.get("data") or {}).get("webPages") or {}).get("value") or []
        recipes: list[RawRecipe] = []
        for page in pages:
            url = (page.get("url") or "").strip()
            title = (page.get("name") or "").strip()
            text = (page.get("text") or page.get("snippet") or "").strip()
            site = _site_name(url)
            if not url or not title or not text or site is None:
                continue
            if site in self._excluded or _is_localized_copy(url):
                continue
            recipes.append(
                RawRecipe(source_url=url, title=title, source_name=site, page_text=text)
            )
        return recipes[:limit]
