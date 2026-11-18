"""Fill the recipe database: search, parse, map, store.  (SCRUM-33)

For every query this runs the pipeline built in Sprint 3:

    LangSearch (30)  ->  skip pages we already have (29)  ->  Gemini parser (31)
    ->  ingredient mapping (32)  ->  storage (36)

Everything that touches the database goes through a small repository object, so
the logic here can be tested with an in-memory fake and no database. The real
one is SqlRecipeRepository at the bottom.

Rules worth knowing:
- Duplicates are skipped BEFORE the Gemini call wherever possible, because a
  Gemini call is the slow and rate-limited step: same normalized URL (in this
  run or already stored), or the same site with the same page title.
- A recipe with an ingredient line we do not recognize is skipped (team
  decision). Those lines are collected in the report so the vocabulary can grow.
- A Gemini or LangSearch rate limit stops the whole run. Hammering a limit that
  resets later only wastes time. Any other failure is counted and the run goes on.
- Each stored recipe is committed on its own, so a crash loses at most one.
"""

import re
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol

from app.providers.base import (
    ProviderError,
    ProviderRateLimited,
    RawRecipe,
    RecipeSearchProvider,
    RecipeSearchQuery,
)
from app.services.dedupe import normalize_url
from app.services.ingredient_mapping import map_recipe
from app.services.normalization import normalize_ingredient
from app.services.recipe_parser import GeminiRecipeParser, ParserError, ParserRateLimited
from app.services.recipe_storage import (
    IngredientEntry,
    RecipeStorageError,
    RecipeToStore,
)


class RecipeRepository(Protocol):
    """What ingestion needs from the database. Tests supply a fake."""

    def has_url(self, normalized_url: str) -> bool: ...
    def has_title(self, site: str, title: str) -> bool: ...
    def save(self, recipe: RecipeToStore) -> bool:
        """Store the recipe. True if new, False if it was already there."""
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


@dataclass
class IngestReport:
    searches: int = 0
    search_errors: int = 0
    results: int = 0
    bad_url: int = 0
    duplicate_url: int = 0  # already stored, or repeated in this run
    duplicate_title: int = 0  # same site and same title as another recipe
    duplicate_content: int = 0  # same recipe found at a different URL
    parse_errors: int = 0
    not_usable: Counter = field(default_factory=Counter)  # parser outcome -> count
    rejected_mapping: int = 0  # unrecognized ingredient lines
    store_errors: int = 0
    stored: int = 0
    would_store: int = 0  # dry run only
    unrecognized: Counter = field(default_factory=Counter)  # key -> count
    unrecognized_examples: dict[str, str] = field(default_factory=dict)
    stopped_reason: str | None = None

    def format(self, top_unrecognized: int = 30) -> str:
        lines = [
            f"Searches run:               {self.searches}  (failed: {self.search_errors})",
            f"Pages returned:             {self.results}",
            f"  skipped, bad URL:         {self.bad_url}",
            f"  skipped, already have:    {self.duplicate_url} by URL, "
            f"{self.duplicate_title} by site+title, {self.duplicate_content} by content",
            f"  parse errors:             {self.parse_errors}",
        ]
        for outcome, count in sorted(self.not_usable.items()):
            lines.append(f"  not stored, {outcome}: {count}")
        lines += [
            f"  not stored, unrecognized ingredients: {self.rejected_mapping}",
            f"  store errors:             {self.store_errors}",
            f"RECIPES STORED:             {self.stored}",
        ]
        if self.would_store:
            lines.append(f"Would store (dry run):      {self.would_store}")
        if self.stopped_reason:
            lines.append(f"\nSTOPPED EARLY: {self.stopped_reason}")
        if self.unrecognized:
            lines.append(f"\nMost common unrecognized ingredients (add to seed/*.csv):")
            for key, count in self.unrecognized.most_common(top_unrecognized):
                lines.append(f"  {count:3d}x  {key}   e.g. {self.unrecognized_examples[key]!r}")
        return "\n".join(lines)


class _Stop(Exception):
    """Internal: end the whole run (rate limit, target reached)."""


def _title_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class Ingestor:
    def __init__(
        self,
        provider: RecipeSearchProvider,
        parser: GeminiRecipeParser,
        lookup: dict[str, str],
        repository: RecipeRepository,
        *,
        max_unrecognized: int = 0,
        dry_run: bool = False,
        search_delay: float = 1.0,
        parse_delay: float = 5.0,  # keeps us under the Gemini free-tier per-minute limit
        sleep: Callable[[float], None] = time.sleep,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self._progress = progress or (lambda message: None)
        self._provider = provider
        self._parser = parser
        self._lookup = lookup
        self._repo = repository
        self._max_unrecognized = max_unrecognized
        self._dry_run = dry_run
        self._search_delay = search_delay
        self._parse_delay = parse_delay
        self._sleep = sleep
        self._seen_urls: set[str] = set()
        self._seen_titles: set[tuple[str, str]] = set()

    def run(
        self,
        queries: Iterable[RecipeSearchQuery],
        *,
        target: int | None = None,
        max_searches: int | None = None,
    ) -> IngestReport:
        report = IngestReport()
        try:
            for query in queries:
                if max_searches is not None and report.searches >= max_searches:
                    report.stopped_reason = f"reached --max-searches ({max_searches})"
                    break
                self._run_query(query, report, target)
                if self._target_reached(report, target):
                    report.stopped_reason = f"reached the target of {target} recipes"
                    break
                self._sleep(self._search_delay)
        except _Stop as stop:
            report.stopped_reason = str(stop)
        except KeyboardInterrupt:
            report.stopped_reason = "interrupted with Ctrl+C (recipes already stored are kept)"
        return report

    # ------------------------------------------------------------------

    def _target_reached(self, report: IngestReport, target: int | None) -> bool:
        return target is not None and (report.stored + report.would_store) >= target

    def _run_query(self, query: RecipeSearchQuery, report: IngestReport, target: int | None) -> None:
        report.searches += 1
        self._progress(f"\n[search {report.searches}] {', '.join(query.ingredients)}")
        try:
            results = self._provider.search(query)
        except ProviderRateLimited as error:
            raise _Stop(f"LangSearch rate or token limit reached ({error})") from error
        except ProviderError as error:
            report.search_errors += 1
            self._progress(f"  search failed: {type(error).__name__}")
            return
        self._progress(f"  {len(results)} pages returned")
        for raw in results:
            report.results += 1
            self._process(raw, report)
            if self._target_reached(report, target):
                return

    def _process(self, raw: RawRecipe, report: IngestReport) -> None:
        label = raw.title[:70]
        say = self._progress
        url = normalize_url(raw.source_url)
        if url is None:
            report.bad_url += 1
            say(f"  skip (bad URL)        {label}")
            return
        if url in self._seen_urls or self._repo.has_url(url):
            report.duplicate_url += 1
            say(f"  skip (already have)   {label}")
            return
        self._seen_urls.add(url)

        # Same site and same page title: almost always the same recipe reached by
        # a different URL (comment links, mobile pages). Skip before paying for Gemini.
        if raw.source_name:
            key = (raw.source_name, _title_key(raw.title))
            if key in self._seen_titles:
                report.duplicate_title += 1
                say(f"  skip (same title)     {label}")
                return
            self._seen_titles.add(key)

        try:
            parsed = self._parser.parse(raw)
        except ParserRateLimited as error:
            raise _Stop(f"Gemini rate limit reached ({error}); wait and run again") from error
        except ParserError as error:
            report.parse_errors += 1
            say(f"  skip (parse error: {type(error).__name__})  {label}")
            self._sleep(self._parse_delay)
            return
        self._sleep(self._parse_delay)

        if not parsed.usable:
            report.not_usable[parsed.outcome.value] += 1
            say(f"  skip ({parsed.outcome.value})  {label}")
            return
        recipe = parsed.recipe

        # Now we know the parsed title; the same site may already have it stored.
        if recipe.source_name and self._repo.has_title(recipe.source_name, recipe.title):
            report.duplicate_title += 1
            say(f"  skip (same title)     {recipe.title[:70]}")
            return

        mapped = map_recipe(recipe, self._lookup, max_unrecognized=self._max_unrecognized)
        for line in mapped.unrecognized:
            key = normalize_ingredient(line) or line.strip().lower()
            report.unrecognized[key] += 1
            report.unrecognized_examples.setdefault(key, line)
        if not mapped.ok:
            report.rejected_mapping += 1
            examples = "; ".join(l.strip()[:40] for l in mapped.unrecognized[:3]) or mapped.reason
            say(f"  skip (unrecognized: {examples})  {label}")
            return

        to_store = RecipeToStore(
            title=recipe.title,
            source_url=recipe.source_url,
            ingredients=[
                IngredientEntry(m.name, m.quantity, m.unit, m.is_optional, raw_text=m.line)
                for m in mapped.ingredients
            ],
            instructions=recipe.instructions,
            source_name=recipe.source_name,
            image_url=recipe.image_url,
            total_minutes=recipe.total_minutes,
            servings=recipe.servings,
            cuisine=recipe.cuisine,
        )
        if self._dry_run:
            report.would_store += 1
            say(f"  would store           {recipe.title[:70]}  ({len(to_store.ingredients)} ingredients)")
            return
        try:
            created = self._repo.save(to_store)
        except RecipeStorageError as error:
            self._repo.rollback()
            report.store_errors += 1
            say(f"  skip (store error: {type(error).__name__})  {label}")
            return
        self._repo.commit()
        if created:
            report.stored += 1
            say(f"  STORED #{report.stored:<3}         {recipe.title[:70]}  ({len(to_store.ingredients)} ingredients)")
        else:
            report.duplicate_content += 1
            say(f"  skip (same recipe)    {recipe.title[:70]}")


# ---------------------------------------------------------------------------
# The real repository, backed by PostgreSQL.
# ---------------------------------------------------------------------------


class SqlRecipeRepository:
    def __init__(self, session) -> None:
        self._session = session

    def has_url(self, normalized_url: str) -> bool:
        from sqlalchemy import select

        from app.db.models import Recipe

        stmt = select(Recipe.recipe_id).where(Recipe.source_url == normalized_url).limit(1)
        return self._session.execute(stmt).first() is not None

    def has_title(self, site: str, title: str) -> bool:
        from sqlalchemy import func, select

        from app.db.models import Recipe

        stmt = (
            select(Recipe.recipe_id)
            .where(Recipe.source_name == site, func.lower(Recipe.title) == title.strip().lower())
            .limit(1)
        )
        return self._session.execute(stmt).first() is not None

    def save(self, recipe: RecipeToStore) -> bool:
        from app.services.recipe_storage import store_recipe

        return store_recipe(self._session, recipe).created

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
