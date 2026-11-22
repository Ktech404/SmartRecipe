"""Ingestion logic with an in-memory repository: no database, key or network."""

import pytest

from app.providers.base import (
    ProviderError,
    ProviderRateLimited,
    RawRecipe,
    RecipeSearchProvider,
    RecipeSearchQuery,
)
from app.services.ingestion import Ingestor
from app.services.normalization import build_lookup
from app.services.recipe_parser import (
    GeminiRecipeParser,
    GenerateResult,
    ParsedRecipe,
    ParserRateLimited,
    ParserUnavailable,
)
from app.services.recipe_storage import InvalidRecipe

LOOKUP = build_lookup(["garlic", "pasta", "salt", "rice", "onion"], {})
QUERY = RecipeSearchQuery(ingredients=("garlic",))


def raw(marker="A", url=None, title=None, site="example.com"):
    return RawRecipe(
        source_url=url or f"https://{site}/{marker}",
        title=title or f"Recipe {marker}",
        source_name=site,
        page_text=f"PAGE_{marker}",
    )


def good(title="Garlic Pasta", lines=("2 cloves garlic, minced", "200 g pasta"), steps=("Cook it.",)):
    return ParsedRecipe(
        is_recipe=True, title=title, ingredient_lines=list(lines), instructions=list(steps),
        total_minutes=20, servings=4,
    )


class FakeRepo:
    def __init__(self, urls=(), titles=(), created=True, error=None):
        self.urls, self.titles = set(urls), {(s, t.lower()) for s, t in titles}
        self.saved, self.commits, self.rollbacks = [], 0, 0
        self._created, self._error = created, error

    def has_url(self, url):
        return url in self.urls

    def has_title(self, site, title):
        return (site, title.lower()) in self.titles

    def save(self, recipe):
        if self._error:
            raise self._error
        self.saved.append(recipe)
        return self._created

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class ScriptedProvider(RecipeSearchProvider):
    """Each search() returns (or raises) the next scripted item."""

    name = "scripted"

    def __init__(self, *responses):
        self.responses, self.queries = list(responses), []
        self.tokens_used = 0

    def search(self, query):
        self.queries.append(query)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Generator:
    """Fake Gemini: picks the answer by the PAGE_x marker found in the prompt."""

    def __init__(self, answers):
        self.answers, self.calls = answers, 0

    def __call__(self, prompt, max_output_tokens):
        self.calls += 1
        for marker, answer in self.answers.items():
            if marker in prompt:
                if isinstance(answer, Exception):
                    raise answer
                return GenerateResult(answer, "STOP")
        raise AssertionError("no scripted answer for this prompt")


def build(provider, answers, repo=None, **options):
    generator = Generator(answers)
    parser = GeminiRecipeParser(generate=generator, sleep=lambda s: None)
    repo = repo or FakeRepo()
    sleeps = []
    options.setdefault("sleep", sleeps.append)
    ingestor = Ingestor(provider, parser, LOOKUP, repo, **options)
    return ingestor, repo, generator, sleeps


def test_stores_a_recipe_end_to_end():
    ingestor, repo, gen, _ = build(ScriptedProvider([raw("A")]), {"PAGE_A": good()})
    report = ingestor.run([QUERY])
    assert report.stored == 1 and repo.commits == 1
    [saved] = repo.saved
    assert saved.title == "Garlic Pasta" and saved.source_name == "example.com"
    assert saved.instructions == "Cook it." and saved.total_minutes == 20 and saved.servings == 4
    assert [(i.name, i.quantity, i.unit) for i in saved.ingredients] == [
        ("garlic", 2.0, "clove"), ("pasta", 200.0, "g"),
    ]
    assert saved.ingredients[0].raw_text == "2 cloves garlic, minced"


def test_url_already_stored_never_reaches_gemini():
    repo = FakeRepo(urls={"https://example.com/A"})
    ingestor, _, gen, _ = build(ScriptedProvider([raw("A")]), {"PAGE_A": good()}, repo)
    report = ingestor.run([QUERY])
    assert report.duplicate_url == 1 and gen.calls == 0 and repo.saved == []


def test_tracking_variant_of_a_url_seen_this_run_is_skipped():
    pages = [raw("A"), raw("A", url="https://www.example.com/A?utm_source=x")]
    ingestor, repo, gen, _ = build(ScriptedProvider(pages), {"PAGE_A": good()})
    report = ingestor.run([QUERY])
    assert report.stored == 1 and report.duplicate_url == 1 and gen.calls == 1


def test_same_site_same_title_is_parsed_once():
    pages = [raw("A", title="Lemon Chicken!"), raw("B", title="lemon chicken")]
    ingestor, repo, gen, _ = build(
        ScriptedProvider(pages), {"PAGE_A": good(), "PAGE_B": good()}
    )
    report = ingestor.run([QUERY])
    assert report.stored == 1 and report.duplicate_title == 1 and gen.calls == 1


def test_parsed_title_already_stored_for_that_site_is_skipped():
    repo = FakeRepo(titles={("example.com", "Garlic Pasta")})
    ingestor, _, gen, _ = build(ScriptedProvider([raw("A")]), {"PAGE_A": good()}, repo)
    report = ingestor.run([QUERY])
    assert report.duplicate_title == 1 and repo.saved == []


def test_not_a_recipe_is_counted_and_not_stored():
    ingestor, repo, _, _ = build(
        ScriptedProvider([raw("A")]), {"PAGE_A": ParsedRecipe(is_recipe=False)}
    )
    report = ingestor.run([QUERY])
    assert report.not_usable["not_recipe"] == 1 and repo.saved == []


def test_unrecognized_ingredient_rejects_the_recipe_and_is_reported():
    answer = good(lines=("2 cloves garlic", "200 g pasta", "1 cup dragon fruit"))
    ingestor, repo, _, _ = build(ScriptedProvider([raw("A")]), {"PAGE_A": answer})
    report = ingestor.run([QUERY])
    assert report.rejected_mapping == 1 and report.stored == 0
    assert report.unrecognized["dragon fruit"] == 1
    assert report.unrecognized_examples["dragon fruit"] == "1 cup dragon fruit"


def test_allowing_unrecognized_lines_keeps_the_recipe():
    answer = good(lines=("2 cloves garlic", "200 g pasta", "1 cup dragon fruit"))
    ingestor, repo, _, _ = build(
        ScriptedProvider([raw("A")]), {"PAGE_A": answer}, max_unrecognized=1
    )
    report = ingestor.run([QUERY])
    assert report.stored == 1 and report.unrecognized["dragon fruit"] == 1


def test_gemini_rate_limit_stops_the_whole_run():
    provider = ScriptedProvider([raw("A")], [raw("B")])
    ingestor, repo, _, _ = build(provider, {"PAGE_A": ParserRateLimited("429")})
    report = ingestor.run([QUERY, QUERY])
    assert report.stopped_reason.startswith("Gemini rate limit")
    assert report.searches == 1 and len(provider.queries) == 1


def test_langsearch_rate_limit_stops_the_whole_run():
    provider = ScriptedProvider(ProviderRateLimited("daily tokens"), [raw("A")])
    ingestor, _, _, _ = build(provider, {"PAGE_A": good()})
    report = ingestor.run([QUERY, QUERY])
    assert report.stopped_reason.startswith("LangSearch rate")
    assert len(provider.queries) == 1


def test_a_failed_search_is_counted_and_the_run_continues():
    provider = ScriptedProvider(ProviderError("boom"), [raw("A")])
    ingestor, repo, _, _ = build(provider, {"PAGE_A": good()})
    report = ingestor.run([QUERY, QUERY])
    assert report.search_errors == 1 and report.stored == 1 and report.searches == 2


def test_a_parse_error_is_counted_and_the_next_page_is_still_tried():
    provider = ScriptedProvider([raw("A"), raw("B")])
    ingestor, repo, _, _ = build(
        provider, {"PAGE_A": ParserUnavailable("503"), "PAGE_B": good(title="Other")}
    )
    # GeminiRecipeParser retries server errors; give it no waiting and the same error each time
    report = ingestor.run([QUERY])
    assert report.parse_errors == 1 and report.stored == 1


def test_dry_run_stores_nothing():
    ingestor, repo, _, _ = build(ScriptedProvider([raw("A")]), {"PAGE_A": good()}, dry_run=True)
    report = ingestor.run([QUERY])
    assert report.would_store == 1 and report.stored == 0
    assert repo.saved == [] and repo.commits == 0


def test_target_stops_the_run():
    provider = ScriptedProvider([raw("A"), raw("B")], [raw("C")])
    ingestor, repo, _, _ = build(
        provider,
        {"PAGE_A": good(title="One"), "PAGE_B": good(title="Two"), "PAGE_C": good(title="Three")},
    )
    report = ingestor.run([QUERY, QUERY], target=1)
    assert report.stored == 1 and "target" in report.stopped_reason
    assert len(provider.queries) == 1


def test_max_searches_stops_the_run():
    provider = ScriptedProvider([], [])
    ingestor, _, _, _ = build(provider, {})
    report = ingestor.run([QUERY, QUERY, QUERY], max_searches=2)
    assert report.searches == 2 and "max-searches" in report.stopped_reason


def test_same_recipe_found_under_a_new_url_counts_as_duplicate_content():
    ingestor, repo, _, _ = build(
        ScriptedProvider([raw("A")]), {"PAGE_A": good()}, FakeRepo(created=False)
    )
    report = ingestor.run([QUERY])
    assert report.duplicate_content == 1 and report.stored == 0


def test_a_storage_error_is_counted_and_rolled_back():
    repo = FakeRepo(error=InvalidRecipe("bad"))
    ingestor, _, _, _ = build(ScriptedProvider([raw("A")]), {"PAGE_A": good()}, repo)
    report = ingestor.run([QUERY])
    assert report.store_errors == 1 and repo.rollbacks == 1 and repo.commits == 0


def test_waits_between_gemini_calls_and_between_searches():
    ingestor, _, _, sleeps = build(
        ScriptedProvider([raw("A")]), {"PAGE_A": good()}, search_delay=1.5, parse_delay=5.0
    )
    ingestor.run([QUERY])
    assert 5.0 in sleeps and 1.5 in sleeps


def test_bad_url_is_skipped():
    ingestor, repo, gen, _ = build(ScriptedProvider([raw("A", url="not a url")]), {})
    report = ingestor.run([QUERY])
    assert report.bad_url == 1 and gen.calls == 0


def test_report_text_mentions_the_key_numbers():
    answer = good(lines=("2 cloves garlic", "1 cup dragon fruit"))
    ingestor, _, _, _ = build(ScriptedProvider([raw("A")]), {"PAGE_A": answer})
    text = ingestor.run([QUERY]).format()
    assert "RECIPES STORED" in text and "dragon fruit" in text


def test_progress_lines_are_reported():
    messages = []
    ingestor, _, _, _ = build(
        ScriptedProvider([raw("A"), raw("B", title="Dragon")]),
        {"PAGE_A": good(), "PAGE_B": good(title="Dragon", lines=("1 cup dragon fruit", "salt"))},
        progress=messages.append,
    )
    ingestor.run([QUERY])
    text = "\n".join(messages)
    assert "[search 1] garlic" in text and "2 pages returned" in text
    assert "STORED #1" in text and "skip (unrecognized: 1 cup dragon fruit)" in text


def test_ctrl_c_ends_the_run_and_returns_the_report():
    class Interrupted(RecipeSearchProvider):
        name = "x"

        def search(self, query):
            raise KeyboardInterrupt

    ingestor, _, _, _ = build(Interrupted(), {})
    report = ingestor.run([QUERY, QUERY])
    assert "Ctrl+C" in report.stopped_reason
