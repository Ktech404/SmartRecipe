"""Live-search settings and the fetcher wrapper. No network, keys or database."""

from app.providers.base import RecipeSearchQuery
from app.services.ingestion import IngestReport
from app.services.live_search import (
    IngestLiveFetcher,
    LazyLiveFetcher,
    LiveSearchSettings,
    build_live_fetcher,
)

QUERY = RecipeSearchQuery(ingredients=("chicken", "rice"), limit=6)


class FakeIngestor:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def run(self, queries, *, target=None, max_searches=None):
        self.calls.append((list(queries), target, max_searches))
        return self.report


def fetch(report, **settings):
    ingestor = FakeIngestor(report)
    outcome = IngestLiveFetcher(ingestor, LiveSearchSettings(**settings)).fetch(QUERY)
    return outcome, ingestor


# ---- settings --------------------------------------------------------------


def test_defaults():
    s = LiveSearchSettings.from_env({})
    assert s.enabled and s.thin_threshold == 5 and s.max_pages == 6
    assert s.target == 3 and s.parse_delay == 1.0
    assert s.workers == 2 and s.cache_hours == 24.0


def test_settings_come_from_the_environment():
    s = LiveSearchSettings.from_env(
        {
            "LIVE_SEARCH_ENABLED": "false",
            "LIVE_SEARCH_THIN_THRESHOLD": "8",
            "LIVE_SEARCH_MAX_PAGES": "4",
            "LIVE_SEARCH_TARGET": "2",
            "LIVE_SEARCH_PARSE_DELAY": "0.5",
            "LIVE_SEARCH_WORKERS": "3",
            "LIVE_SEARCH_CACHE_HOURS": "0",
        }
    )
    assert not s.enabled and s.thin_threshold == 8 and s.max_pages == 4
    assert s.target == 2 and s.parse_delay == 0.5
    assert s.workers == 3 and s.cache_hours == 0


def test_bad_values_fall_back_to_the_defaults():
    s = LiveSearchSettings.from_env(
        {"LIVE_SEARCH_THIN_THRESHOLD": "lots", "LIVE_SEARCH_MAX_PAGES": "0", "LIVE_SEARCH_PARSE_DELAY": "-1"}
    )
    assert s.thin_threshold == 5 and s.max_pages == 6 and s.parse_delay == 1.0


# ---- the fetcher -----------------------------------------------------------


def test_stored_recipes_are_reported_and_the_ingestor_is_told_to_stop_early():
    outcome, ingestor = fetch(IngestReport(searches=1, stored=2), target=3)
    assert outcome.ok and outcome.stored == 2
    [(queries, target, max_searches)] = ingestor.calls
    assert queries == [QUERY] and target == 3 and max_searches == 1


def test_a_healthy_search_that_found_nothing_usable_is_still_ok():
    outcome, _ = fetch(IngestReport(searches=1, results=10, rejected_mapping=4))
    assert outcome.ok and outcome.stored == 0


def test_a_failed_search_is_not_ok():
    outcome, _ = fetch(IngestReport(searches=1, search_errors=1))
    assert not outcome.ok and outcome.stored == 0


def test_a_rate_limit_is_not_ok():
    outcome, _ = fetch(IngestReport(searches=1, stopped_reason="Gemini rate limit reached"))
    assert not outcome.ok and "rate limit" in outcome.reason


def test_only_parse_errors_is_not_ok():
    outcome, _ = fetch(IngestReport(searches=1, results=5, parse_errors=5))
    assert not outcome.ok


def test_some_stored_recipes_beat_a_late_failure():
    outcome, _ = fetch(IngestReport(searches=1, stored=1, parse_errors=2, stopped_reason="stopped"))
    assert outcome.ok and outcome.stored == 1


# ---- building it -----------------------------------------------------------


def test_no_fetcher_when_disabled(monkeypatch):
    monkeypatch.setenv("LANGSEARCH_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    assert build_live_fetcher(None, LiveSearchSettings(enabled=False)) is None


def test_no_fetcher_when_a_key_is_missing(monkeypatch):
    monkeypatch.setenv("LANGSEARCH_API_KEY", "x")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert build_live_fetcher(None, LiveSearchSettings()) is None
    monkeypatch.delenv("LANGSEARCH_API_KEY")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    assert build_live_fetcher(None, LiveSearchSettings()) is None


def test_with_both_keys_the_fetcher_is_lazy_and_builds_nothing_yet(monkeypatch):
    monkeypatch.setenv("LANGSEARCH_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    fetcher = build_live_fetcher(None, LiveSearchSettings())
    assert isinstance(fetcher, LazyLiveFetcher)  # no session or API client was touched


# ---- recent searches --------------------------------------------------------


def test_recent_search_is_remembered_until_it_expires():
    from app.services.live_search import RecentSearchCache

    now = [0.0]
    cache = RecentSearchCache(clock=lambda: now[0])
    key = (1, 2)
    assert not cache.seen(key, 100)
    cache.remember(key)
    assert cache.seen(key, 100) and not cache.seen((1, 3), 100)
    now[0] = 99
    assert cache.seen(key, 100)
    now[0] = 100
    assert not cache.seen(key, 100)


def test_a_zero_lifetime_never_remembers():
    from app.services.live_search import RecentSearchCache

    cache = RecentSearchCache()
    cache.remember((1,))
    assert not cache.seen((1,), 0)


def test_the_cache_drops_its_oldest_entry_when_full():
    from app.services.live_search import RecentSearchCache

    now = [0.0]
    cache = RecentSearchCache(clock=lambda: now[0], max_entries=2)
    for n in range(3):
        now[0] = n
        cache.remember((n,))
    assert not cache.seen((0,), 1000) and cache.seen((1,), 1000) and cache.seen((2,), 1000)
