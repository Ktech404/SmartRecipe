"""Spike: can Gemini turn recipe page text into structured data?  (SCRUM-15)

Reads the page text saved by spike_langsearch.py, asks Gemini for structured
output, and measures:
  - how often we get usable INGREDIENTS (what matching and tiers depend on)
  - how often we also get STEPS (LangSearch often returns only an excerpt)
  - whether our keyword check for "looks like a recipe" misses real recipes
  - how many parsed ingredient lines our normalizer and seed list recognize
  - tokens and time per page

Ingredients and steps are scored separately on purpose. A page with a full
ingredient list but no steps is still useful to us.

Setup (PowerShell example):
    pip install google-genai pydantic
    $env:GEMINI_API_KEY = "your key"
    $env:GEMINI_MODEL   = "gemini-3.8-flash"   # confirm the exact name in AI Studio > Get code

Run from the backend/ folder, AFTER spike_langsearch.py:
    python scripts/spike_parse_recipe.py --limit 1 --unflagged 0   # one page first
    python scripts/spike_parse_recipe.py                           # 8 pages + 2 unflagged
    python scripts/spike_parse_recipe.py --limit 20

To compare models, rerun with GEMINI_MODEL=gemini-3.5-flash-lite on the same pages.
If many pages say "no parsed output", try --max-output-tokens 8192.

Ingredient recognition needs app/services/normalization.py and seed/*.csv. If they
are not in your working copy yet, the script skips that measure and says so.

Output: scripts/spike_output/parse_results.json (contains parsed recipe text, so
keep it out of git). Standard Gemini free-tier limits apply, so the script pauses
between calls.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

INPUT_PATH = Path(__file__).parent / "spike_output" / "langsearch_text.json"
OUTPUT_PATH = Path(__file__).parent / "spike_output" / "parse_results.json"

PROMPT = """Extract the recipe from the web page text below.
If the page is not a single recipe (a list of recipes, an article, a blog
index), set is_recipe to false and leave the other fields empty.
Rules:
- ingredient_lines: one string per ingredient, exactly as written on the page.
- instructions: one string per step, in order. If the text has no steps, or ends
  before the steps begin, leave instructions empty. Do not invent steps.
- Do not invent anything that is not in the text.

PAGE TEXT:
{text}
"""


class ParsedRecipe(BaseModel):
    is_recipe: bool
    title: str | None = None
    ingredient_lines: list[str] = []
    instructions: list[str] = []
    total_minutes: int | None = None
    servings: int | None = None
    cuisine: str | None = None


def load_recognizer():
    """Return (lookup, resolve) if the normalizer and seed data exist, else (None, None)."""
    try:
        from app.services.normalization import load_seed_lookup, resolve_ingredient

        return load_seed_lookup(BACKEND_DIR / "seed"), resolve_ingredient
    except (ImportError, FileNotFoundError) as error:
        print(f"Note: skipping ingredient recognition ({type(error).__name__}: {error}).")
        print("      Add app/services/normalization.py and seed/*.csv to measure it later.\n")
        return None, None


def collect_pages(limit: int, unflagged: int) -> list[dict]:
    """Pick pages to parse, skipping repeated URLs and repeated text.

    `limit` pages whose text mentions ingredients, plus `unflagged` pages that
    did not, to check whether our keyword test is missing real recipes.
    """
    runs = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    seen_urls, seen_texts = set(), set()
    flagged, other = [], []
    for run in runs:
        for page in run["results"]:
            text = page["text"].strip()
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if not text or page["url"] in seen_urls or digest in seen_texts:
                continue
            seen_urls.add(page["url"])
            seen_texts.add(digest)
            (flagged if page["has_ingredients"] else other).append(page)
    return flagged[:limit] + other[:unflagged]


def classify(parsed: ParsedRecipe | None, finish_reason: str = "?") -> tuple[str, str | None]:
    """Sort one parse into a category. Returns (category, reason_if_failed)."""
    if parsed is None:
        # Known SDK behavior: parsed is None when the output hits the token limit.
        return "no_output", f"no parsed output (finish_reason={finish_reason})"
    if not parsed.is_recipe:
        return "not_recipe", "model says page is not a recipe"
    if not parsed.ingredient_lines:
        return "no_ingredients", "recipe but no ingredients found"
    if not parsed.instructions:
        return "ingredients_only", None  # still useful: ingredients drive matching
    return "full", None


def token_counts(response) -> tuple[int, int]:
    """(input, output) tokens if the SDK reports them, else (0, 0)."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0, 0
    return (
        getattr(meta, "prompt_token_count", 0) or 0,
        getattr(meta, "candidates_token_count", 0) or 0,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=8, help="pages that mention ingredients")
    parser.add_argument("--unflagged", type=int, default=2, help="extra pages that did not")
    parser.add_argument("--delay", type=float, default=4.0, help="seconds between calls")
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    args = parser.parse_args()

    model = os.environ.get("GEMINI_MODEL")
    if not model or not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Set GEMINI_API_KEY and GEMINI_MODEL first.")
    if not INPUT_PATH.exists():
        raise SystemExit(f"Run spike_langsearch.py first ({INPUT_PATH} not found).")

    from google import genai  # imported late so --help works without the package

    client = genai.Client()  # reads GEMINI_API_KEY from the environment
    lookup, resolve = load_recognizer()

    outcomes, latencies = [], []
    tokens_in = tokens_out = lines_total = lines_known = 0
    unrecognized: dict[str, int] = {}

    pages = collect_pages(args.limit, args.unflagged)
    if not pages:
        raise SystemExit("No pages to parse. Check the LangSearch output file.")

    for page in pages:
        started = time.perf_counter()
        domain = urlparse(page["url"]).netloc
        record = {
            "url": page["url"],
            "domain": domain,
            "keyword_flagged": page["has_ingredients"],
            "steps_keyword": page["has_steps"],
            "category": None,
            "reason": None,
        }
        try:
            response = client.models.generate_content(
                model=model,
                contents=PROMPT.format(text=page["text"]),
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ParsedRecipe,
                    "max_output_tokens": args.max_output_tokens,
                },
            )
            finish = response.candidates[0].finish_reason if response.candidates else "?"
            category, reason = classify(response.parsed, str(finish))
            record["category"], record["reason"] = category, reason
            used_in, used_out = token_counts(response)
            tokens_in += used_in
            tokens_out += used_out

            parsed = response.parsed
            if category in ("full", "ingredients_only"):
                record["parsed"] = parsed.model_dump()
                if lookup is not None:
                    known = [resolve(line, lookup) for line in parsed.ingredient_lines]
                    lines_total += len(known)
                    lines_known += sum(k is not None for k in known)
                    record["unrecognized_lines"] = [
                        line for line, k in zip(parsed.ingredient_lines, known) if k is None
                    ]
                    for line in record["unrecognized_lines"]:
                        unrecognized[line] = unrecognized.get(line, 0) + 1
        except Exception as error:
            record["category"] = "error"
            record["reason"] = f"{type(error).__name__}: {error}"
        latencies.append(time.perf_counter() - started)
        outcomes.append(record)

        detail = ""
        if "parsed" in record:
            p = record["parsed"]
            detail = f"{len(p['ingredient_lines'])} ingredients, {len(p['instructions'])} steps"
        print(f"[{record['category']:<16}] {domain:<40} {detail or record['reason'] or ''}")
        time.sleep(args.delay)

    OUTPUT_PATH.write_text(json.dumps(outcomes, indent=2), encoding="utf-8")

    total = len(outcomes)
    by_cat: dict[str, int] = {}
    for r in outcomes:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    full = by_cat.get("full", 0)
    ing = full + by_cat.get("ingredients_only", 0)

    print("\n--- Summary: paste into docs/recipe-parsing-spike.md ---")
    print(f"Model: {model}   Pages parsed: {total}")
    print(f"By category: {by_cat}")
    print(f"Usable ingredients: {ing}/{total} ({100 * ing / total:.0f}%)")
    print(f"Ingredients AND steps: {full}/{total} ({100 * full / total:.0f}%)")

    flagged = [r for r in outcomes if r["keyword_flagged"]]
    unflagged = [r for r in outcomes if not r["keyword_flagged"]]
    if flagged:
        ok = sum(r["category"] in ("full", "ingredients_only") for r in flagged)
        print(f"Pages our keyword check flagged: usable ingredients {ok}/{len(flagged)}")
    if unflagged:
        real = sum(r["category"] in ("full", "ingredients_only") for r in unflagged)
        print(f"Pages our keyword check did NOT flag: {real}/{len(unflagged)} were real recipes "
              f"(if above 0, the keyword check misses some)")
    with_hint = [r for r in outcomes if r["steps_keyword"]]
    if with_hint:
        got = sum(r["category"] == "full" for r in with_hint)
        print(f"Pages whose text mentioned steps: Gemini found steps in {got}/{len(with_hint)}")

    print(f"Average time per page: {sum(latencies) / len(latencies):.1f}s")
    if tokens_in or tokens_out:
        print(f"Gemini tokens per page: about {tokens_in // total} in, {tokens_out // total} out")
    if lines_total:
        print(f"Ingredient lines recognized by seed list: {lines_known}/{lines_total} "
              f"({100 * lines_known / lines_total:.0f}%)")
        common = sorted(unrecognized.items(), key=lambda kv: -kv[1])[:10]
        print("Unrecognized lines (first 10, add common ones to the seed list):")
        for line, count in common:
            print(f"   {count}x  {line}")
    reasons: dict[str, int] = {}
    for r in outcomes:
        if r["reason"]:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    print("Failure reasons:", reasons or "none")
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
