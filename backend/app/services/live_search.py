"""Fetch new recipes from the web when the stored ones are not enough.  (SCRUM-35)

The search endpoint looks in the database first. If that finds fewer than
`thin_threshold` good matches (best or partial tier), it asks a LiveFetcher to
search the web, parse the pages and store the new recipes, then searches the
database again. The fetcher reuses the ingestion pipeline from SCRUM-33
(LangSearch -> Gemini parser -> ingredient mapping -> storage), so a live
search also grows the recipe store for the next user.

A LiveFetcher never raises for normal trouble. It returns a LiveOutcome with
ok=False, and the endpoint then answers from the stored recipes and sets
`degraded: true` (requirement 2.2.1.3).

Settings (all optional environment variables):
    LIVE_SEARCH_ENABLED      "false" turns live search off. Default true.
    LIVE_SEARCH_THIN_THRESHOLD  Fetch when fewer than this many good stored
                             matches exist. Default 5.
    LIVE_SEARCH_MAX_PAGES    Web pages to request per search. Default 6.
    LIVE_SEARCH_TARGET       Stop after storing this many new recipes. Default 3.
    LIVE_SEARCH_PARSE_DELAY  Seconds between Gemini calls (or batches). Default 1.0.
    LIVE_SEARCH_WORKERS      Pages parsed at the same time. Default 2.
    LIVE_SEARCH_CACHE_HOURS  After a successful web search for some ingredients,
                             do not search the web for the same ingredients again
                             for this many hours. 0 turns this off. Default 24.

To save Gemini quota the fetcher skips pages that cannot be recipes before parsing
(see prefilter_reason in ingestion.py).
"""

import logging
import os
import threading
import time
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from typing import Protocol

from app.providers.base import ProviderError, RecipeSearchQuery

log = logging.getLogger("uvicorn.error")  # shows up in the uvicorn window


@dataclass(frozen=True)
class LiveSearchSettings:
    enabled: bool = True
    thin_threshold: int = 5
    max_pages: int = 6
    target: int = 3
    parse_delay: float = 1.0
    workers: int = 2
    cache_hours: float = 24.0
    provider_timeout: float = 15.0
    parser_timeout: float = 30.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LiveSearchSettings":
        env = os.environ if env is None else env
        defaults = cls()

        def number(name: str, default, kind, minimum):
            try:
                value = kind(env[name])
            except (KeyError, ValueError):
                return default
            return value if value >= minimum else default

        return cls(
            enabled=env.get("LIVE_SEARCH_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off"),
            thin_threshold=number("LIVE_SEARCH_THIN_THRESHOLD", defaults.thin_threshold, int, 1),
            max_pages=number("LIVE_SEARCH_MAX_PAGES", defaults.max_pages, int, 1),
            target=number("LIVE_SEARCH_TARGET", defaults.target, int, 1),
            parse_delay=number("LIVE_SEARCH_PARSE_DELAY", defaults.parse_delay, float, 0.0),
            workers=number("LIVE_SEARCH_WORKERS", defaults.workers, int, 1),
            cache_hours=number("LIVE_SEARCH_CACHE_HOURS", defaults.cache_hours, float, 0.0),
        )


class RecentSearchCache:
    """Remembers which ingredient sets were just searched on the web.

    Kept in memory: it is per server process and starts empty after a restart,
    which only costs one extra web search. Safe to share between requests.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic, max_entries: int = 1000) -> None:
        self._clock = clock
        self._max = max_entries
        self._seen: dict[Hashable, float] = {}
        self._lock = threading.Lock()

    def seen(self, key: Hashable, ttl_seconds: float) -> bool:
        if ttl_seconds <= 0:
            return False
        with self._lock:
            when = self._seen.get(key)
            if when is None:
                return False
            if self._clock() - when >= ttl_seconds:
                del self._seen[key]
                return False
            return True

    def remember(self, key: Hashable) -> None:
        with self._lock:
            self._seen[key] = self._clock()
            while len(self._seen) > self._max:
                del self._seen[min(self._seen, key=self._seen.get)]


_RECENT_SEARCHES = RecentSearchCache()


def get_recent_searches() -> RecentSearchCache:
    return _RECENT_SEARCHES


@dataclass(frozen=True)
class LiveOutcome:
    ok: bool  # False: the provider was unavailable or rate limited
    stored: int = 0  # new recipes added to the database
    reason: str | None = None


class LiveFetcher(Protocol):
    def fetch(self, query: RecipeSearchQuery) -> LiveOutcome: ...


class IngestLiveFetcher:
    """LiveFetcher built on the SCRUM-33 Ingestor."""

    def __init__(self, ingestor, settings: LiveSearchSettings) -> None:
        self._ingestor = ingestor
        self._settings = settings

    def fetch(self, query: RecipeSearchQuery) -> LiveOutcome:
        report = self._ingestor.run([query], target=self._settings.target, max_searches=1)
        log.info(
            "live search %s: pages=%d stored=%d prefiltered=%d dup_url=%d dup_title=%d dup_content=%d "
            "not_usable=%d unrecognized=%d parse_errors=%d search_errors=%d stopped=%s",
            ",".join(query.ingredients), report.results, report.stored, report.prefiltered,
            report.duplicate_url, report.duplicate_title, report.duplicate_content,
            sum(report.not_usable.values()), report.rejected_mapping, report.parse_errors,
            report.search_errors, report.stopped_reason,
        )
        if report.stored > 0:
            return LiveOutcome(True, report.stored)
        if report.search_errors:
            return LiveOutcome(False, 0, "the recipe search provider failed")
        if report.stopped_reason:
            return LiveOutcome(False, 0, report.stopped_reason)
        if report.parse_errors:
            return LiveOutcome(False, 0, "the recipe parser failed")
        # The providers worked; the pages just had nothing we could keep.
        return LiveOutcome(True, 0)


def _build_ingest_fetcher(session, settings: LiveSearchSettings) -> IngestLiveFetcher | None:
    # Imported here so the rest of the app (and its tests) never need these keys.
    from app.providers.langsearch import LangSearchProvider
    from app.services.ingestion import Ingestor, SqlRecipeRepository
    from app.services.ingredient_mapping import load_lookup_from_db
    from app.services.recipe_parser import GeminiRecipeParser

    try:
        provider = LangSearchProvider.from_env(timeout=settings.provider_timeout)
        parser = GeminiRecipeParser(timeout=settings.parser_timeout)
    except (ProviderError, RuntimeError, ValueError):
        return None
    ingestor = Ingestor(
        provider,
        parser,
        load_lookup_from_db(session),
        SqlRecipeRepository(session),
        max_unrecognized=0,
        search_delay=0.0,
        parse_delay=settings.parse_delay,
        prefilter=True,
        workers=settings.workers,
    )
    return IngestLiveFetcher(ingestor, settings)


class LazyLiveFetcher:
    """Builds the real fetcher on first use, so searches that need no web search
    never create API clients or load the ingredient table."""

    def __init__(self, session, settings: LiveSearchSettings) -> None:
        self._session = session
        self._settings = settings

    def fetch(self, query: RecipeSearchQuery) -> LiveOutcome:
        fetcher = _build_ingest_fetcher(self._session, self._settings)
        if fetcher is None:
            return LiveOutcome(False, 0, "live search is not configured")
        return fetcher.fetch(query)


def build_live_fetcher(session, settings: LiveSearchSettings | None = None) -> LiveFetcher | None:
    """The real fetcher, or None when live search is off or the API keys are missing."""
    settings = settings or LiveSearchSettings.from_env()
    if not settings.enabled:
        return None
    if not os.environ.get("LANGSEARCH_API_KEY") or not os.environ.get("GEMINI_API_KEY"):
        return None
    return LazyLiveFetcher(session, settings)
