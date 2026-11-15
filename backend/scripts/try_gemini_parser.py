"""Parse a few saved LangSearch pages with GeminiRecipeParser and print the results.

Uses your Gemini free-tier quota, not LangSearch tokens: it reads the page text
saved by the spike (scripts/spike_output/langsearch_text.json).

Run from backend/:
    python -m scripts.try_gemini_parser            # 3 pages
    python -m scripts.try_gemini_parser --pages 8

Needs GEMINI_API_KEY in your environment or backend/.env. GEMINI_MODEL is
optional (default gemini-3.5-flash-lite). Install the SDK first if needed:
    pip install google-genai
"""

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from app.providers.base import RawRecipe
from app.services.recipe_parser import GeminiRecipeParser, ParserError, ParserRateLimited

INPUT_PATH = Path(__file__).parent / "spike_output" / "langsearch_text.json"


def main() -> None:
    load_dotenv()
    cli = argparse.ArgumentParser()
    cli.add_argument("--pages", type=int, default=3)
    cli.add_argument("--delay", type=float, default=4.0, help="seconds between calls")
    args = cli.parse_args()
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found. Run the LangSearch spike first.")

    pages = [p for run in json.loads(INPUT_PATH.read_text(encoding="utf-8")) for p in run["results"]]
    parser = GeminiRecipeParser()
    print(f"Model: {parser.model}\n")

    for page in pages[: args.pages]:
        raw = RawRecipe(source_url=page["url"], title=page["name"], page_text=page["text"])
        started = time.perf_counter()
        try:
            result = parser.parse(raw)
        except ParserRateLimited as error:
            print(f"[rate limited] {error}. Stopping; wait a minute (or until tomorrow if it is the daily limit).")
            break
        except ParserError as error:
            # One bad page should not end the whole run.
            print(f"[error] {page['url']}\n        {type(error).__name__}: {error}")
            time.sleep(args.delay)
            continue
        took = time.perf_counter() - started
        line = f"[{result.outcome.value:<16}] {took:4.1f}s  {page['url']}"
        if result.recipe:
            r = result.recipe
            steps = len((r.instructions or "").splitlines())
            line += (f"\n    {r.title} | {len(r.ingredient_lines)} ingredients, {steps} steps, "
                     f"minutes={r.total_minutes}, servings={r.servings}, cuisine={r.cuisine}")
        elif result.reason:
            line += f"\n    {result.reason}"
        print(line)
        time.sleep(args.delay)

    print(f"\nTokens: {parser.input_tokens} in, {parser.output_tokens} out")


if __name__ == "__main__":
    main()
