"""Spike: how good is LangSearch at finding recipe pages, and what does it cost?

Sends ingredient-style searches to the LangSearch web search API and measures:
  - tokens used per search (this is what the free plan limits)
  - latency
  - how many results contain ingredients and steps in the text we got back
  - how often the text hit the character limit (steps may be cut off)

Setup (PowerShell example):
    $env:LANGSEARCH_API_KEY = "your key"      # from langsearch.com/dashboard

Run from the backend/ folder. START SMALL, then scale up:
    python scripts/spike_langsearch.py                  # 3 searches, 5 results each
    python scripts/spike_langsearch.py --queries 12     # the full list
    python scripts/spike_langsearch.py --max-chars 5000 # allow longer page text

Safety: the run stops once it has used --max-tokens tokens (default 50,000), so a
mistake cannot burn your whole daily allowance. After the run, compare the token
total printed here with "Tokens used today" on the LangSearch dashboard.

Output: scripts/spike_output/langsearch_<mode>.json (read by spike_parse_recipe.py).
Add `spike_output/` to .gitignore. Do not commit page text or keys.

Request and response format: https://docs.langsearch.com/reference/search-api-guide.md
Tokens counted: input = your query, output = returned page text (or snippet).
Titles, URLs, and dates do not count. Standard library only.
"""

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

API_URL = "https://api.langsearch.com/v1/web-search"
OUTPUT_DIR = Path(__file__).parent / "spike_output"

QUERIES = [
    "recipe with chicken breast rice garlic lemon",
    "easy recipes using black beans and corn tortillas",
    "recipe with spaghetti garlic olive oil",
    "what to make with ground beef and bell peppers",
    "vegetarian recipe with chickpeas spinach and tomato",
    "salmon recipe with lemon and asparagus",
    "gluten free dinner with rice shrimp and ginger",
    "recipe using eggs potatoes and onion",
    "quick pasta with mushrooms and cream",
    "recipe with sweet potato and black beans",
    "tofu stir fry with broccoli and soy sauce",
    "recipe with chicken thighs and potatoes in the oven",
]

INGREDIENT_HINTS = ("ingredient",)
STEP_HINTS = ("instruction", "direction", "method", "step 1", "preparation")


def search(api_key: str, query: str, mode: str, count: int, max_chars: int) -> dict:
    body = {"query": query, "count": count, "freshness": "noLimit"}
    if mode == "text":
        # Asking for text makes each result's page text come back (and cost tokens).
        body["contents"] = {"text": {"maxCharacters": max_chars}}
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def classify(text: str) -> dict:
    """Does this text look like it contains a recipe's ingredients and steps?"""
    lowered = text.lower()
    return {
        "has_ingredients": any(h in lowered for h in INGREDIENT_HINTS),
        "has_steps": any(h in lowered for h in STEP_HINTS),
    }


def tokens_used(payload: dict) -> int:
    """Input plus output tokens, as the response reports them."""
    usage = payload.get("usage", {})
    return usage.get("input_tokens", 0) + usage.get("output_tokens", 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["text", "snippet"], default="text")
    parser.add_argument("--queries", type=int, default=3, help="how many searches to run")
    parser.add_argument("--count", type=int, default=5, help="results per search (1-50)")
    parser.add_argument("--max-chars", type=int, default=3000, help="page text limit per result")
    parser.add_argument("--max-tokens", type=int, default=50_000, help="stop after this many tokens")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between calls")
    args = parser.parse_args()

    api_key = os.environ.get("LANGSEARCH_API_KEY")
    if not api_key:
        raise SystemExit("Set LANGSEARCH_API_KEY first.")

    runs, latencies, per_search_tokens = [], [], []
    total_tokens = total_results = 0
    both = ingredients_only = neither = truncated = 0

    for query in QUERIES[: args.queries]:
        if total_tokens >= args.max_tokens:
            print(f"Stopping: reached the --max-tokens budget ({args.max_tokens}).")
            break

        started = time.perf_counter()
        try:
            payload = search(api_key, query, args.mode, args.count, args.max_chars)
        except urllib.error.HTTPError as error:
            print(f"HTTP {error.code} for {query!r}: {error.read()[:200]!r}")
            if error.code == 429:
                print("Rate or token limit. If the daily allowance is gone, wait for 00:00 UTC.")
                break
            continue
        except Exception as error:  # timeouts, DNS, bad JSON
            print(f"ERROR for {query!r}: {error}")
            continue

        elapsed = time.perf_counter() - started
        latencies.append(elapsed)
        spent = tokens_used(payload)
        total_tokens += spent
        per_search_tokens.append(spent)

        pages = payload.get("data", {}).get("webPages", {}).get("value", [])
        results = []
        for page in pages:
            text = page.get("text") or page.get("snippet") or ""
            flags = classify(text)
            hit_limit = args.mode == "text" and len(text) >= args.max_chars * 0.95
            results.append(
                {
                    "name": page.get("name"),
                    "url": page.get("url"),
                    "domain": urlparse(page.get("url", "")).netloc,
                    "text": text,
                    "text_length": len(text),
                    "truncated": hit_limit,
                    **flags,
                }
            )
            total_results += 1
            truncated += hit_limit
            if flags["has_ingredients"] and flags["has_steps"]:
                both += 1
            elif flags["has_ingredients"]:
                ingredients_only += 1
            else:
                neither += 1

        runs.append({"query": query, "latency_s": round(elapsed, 2), "tokens": spent, "results": results})
        print(f"{elapsed:5.2f}s  {spent:6d} tokens  {len(results):2d} results  {query}")
        time.sleep(args.delay)

    if not runs:
        raise SystemExit("No successful searches. Check the key and your allowance.")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"langsearch_{args.mode}.json"
    out_path.write_text(json.dumps(runs, indent=2), encoding="utf-8")

    average = statistics.mean(per_search_tokens)
    print("\n--- Summary: paste into docs/search-provider-spike.md ---")
    print(f"Mode: {args.mode}   count={args.count}   max_chars={args.max_chars}")
    print(f"Searches OK: {len(runs)}   Results: {total_results}")
    print(f"Latency: median {statistics.median(latencies):.2f}s, max {max(latencies):.2f}s")
    print(f"TOKENS this run: {total_tokens}   average per search: {average:.0f}   "
          f"per result: {total_tokens / max(total_results, 1):.0f}")
    print(f"Projected cost of all {len(QUERIES)} searches at this setting: ~{average * len(QUERIES):.0f} tokens")
    print("Check: does 'Tokens used today' on the dashboard match the total above?")
    print(f"Ingredients + steps both in text: {both}   ingredients but no steps: {ingredients_only}   "
          f"neither: {neither}")
    if args.mode == "text":
        print(f"Text hit the character limit: {truncated}/{total_results} "
              f"({100 * truncated / max(total_results, 1):.0f}%). If 'ingredients but no steps' "
              f"is high, try a larger --max-chars.")
    domains: dict[str, int] = {}
    for run in runs:
        for r in run["results"]:
            domains[r["domain"]] = domains.get(r["domain"], 0) + 1
    print("Top domains:", sorted(domains.items(), key=lambda kv: -kv[1])[:8])
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
