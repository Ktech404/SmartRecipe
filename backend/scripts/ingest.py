"""Load recipes into the database: search the web, parse, map, store.

Run from backend/ (needs Docker running, the database migrated and seeded, and
LANGSEARCH_API_KEY and GEMINI_API_KEY in your environment or backend/.env):

    python -m scripts.ingest "chicken, rice, garlic"      # one search
    python -m scripts.ingest --default --target 60         # preload for the demo
    python -m scripts.ingest --file my_queries.txt         # one query per line
    python -m scripts.ingest "chicken, rice" --dry-run     # parse and map, store nothing

Each query is a comma-separated list of ingredients. START SMALL (one query, or
--dry-run) before a big run: every page costs one Gemini call, and the free tier
has per-minute and per-day limits. The run stops by itself on a rate limit.

The summary at the end lists the ingredient lines we did not recognize. Those
recipes were skipped; add the common ones to backend/seed/*.csv and re-seed.
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from app.providers.base import ProviderError, RecipeSearchQuery
from app.providers.langsearch import LangSearchProvider
from app.services.ingestion import Ingestor, SqlRecipeRepository
from app.services.ingredient_mapping import load_lookup_from_db
from app.services.recipe_parser import GeminiRecipeParser

# A spread of everyday ingredient combinations, for preloading before a demo.
DEFAULT_QUERIES = [
    "chicken, rice, garlic",
    "black beans, corn, tortilla",
    "spaghetti, garlic, olive oil",
    "ground beef, bell pepper, onion",
    "chickpeas, spinach, tomato",
    "salmon, lemon, asparagus",
    "eggs, potatoes, onion",
    "pasta, mushrooms, cream",
    "sweet potato, black beans",
    "tofu, broccoli, soy sauce",
    "chicken thighs, potatoes",
    "shrimp, rice, ginger",
    "lentils, carrots, onion",
    "pork chops, apples",
    "beef, broccoli, rice",
    "zucchini, tomato, mozzarella",
    "quinoa, avocado, lime",
    "cheddar cheese, bread, butter",
    "turkey, cranberry, sweet potato",
    "rice, eggs, peas",
]


def to_query(text: str, limit: int) -> RecipeSearchQuery:
    ingredients = tuple(part.strip() for part in text.split(",") if part.strip())
    return RecipeSearchQuery(ingredients=ingredients, limit=limit)


def main() -> None:
    load_dotenv()
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    cli.add_argument("queries", nargs="*", help='e.g. "chicken, rice, garlic"')
    cli.add_argument("--file", type=Path, help="text file with one query per line")
    cli.add_argument("--default", action="store_true", help="use the built-in list of queries")
    cli.add_argument("--target", type=int, help="stop after storing this many recipes")
    cli.add_argument("--max-searches", type=int, help="stop after this many searches")
    cli.add_argument("--limit", type=int, default=10, help="results wanted per search")
    cli.add_argument("--dry-run", action="store_true", help="parse and map, but store nothing")
    cli.add_argument("--allow-unrecognized", type=int, default=0,
                     help="keep recipes with up to this many unrecognized ingredient lines")
    cli.add_argument("--parse-delay", type=float, default=5.0, help="seconds between Gemini calls")
    cli.add_argument("--prefilter", action="store_true",
                     help="skip pages that cannot be a recipe before calling Gemini (saves quota)")
    cli.add_argument("--workers", type=int, default=1,
                     help="parse this many pages at once (faster, but reaches rate limits sooner)")
    args = cli.parse_args()

    texts = list(args.queries)
    if args.file:
        texts += [l.strip() for l in args.file.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.default:
        texts += DEFAULT_QUERIES
    if not texts:
        raise SystemExit('Give at least one query, --file, or --default. Example: "chicken, rice, garlic"')
    queries = [to_query(t, args.limit) for t in texts]

    try:
        provider = LangSearchProvider.from_env()
    except ProviderError as error:
        raise SystemExit(f"{error}. Add it to backend/.env.")
    parser = GeminiRecipeParser()

    from app.db.session import SessionLocal  # imported late so --help works without a database

    with SessionLocal() as session:
        lookup = load_lookup_from_db(session)
        if not lookup:
            raise SystemExit("The ingredient table is empty. Run: python -m scripts.seed")
        print(f"{len(queries)} queries, {len(lookup)} known ingredient names, "
              f"model {parser.model}{'  [DRY RUN]' if args.dry_run else ''}")
        print("Press Ctrl+C at any time to stop safely; recipes already stored are kept.")
        ingestor = Ingestor(
            provider, parser, lookup, SqlRecipeRepository(session),
            max_unrecognized=args.allow_unrecognized,
            dry_run=args.dry_run,
            parse_delay=args.parse_delay,
            prefilter=args.prefilter,
            workers=args.workers,
            progress=lambda message: print(message, flush=True),
        )
        report = ingestor.run(queries, target=args.target, max_searches=args.max_searches)

    print(report.format())
    print(f"\nLangSearch tokens: {provider.tokens_used}   "
          f"Gemini tokens: {parser.input_tokens} in, {parser.output_tokens} out")


if __name__ == "__main__":
    main()
