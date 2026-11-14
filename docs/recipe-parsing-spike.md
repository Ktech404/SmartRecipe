# Spike: Parsing Recipe Pages with Gemini (SCRUM-15)

**Status:** Results and spot check recorded.
**Run date:** October 29, 2026

## Question

Can Gemini structured output turn the page text LangSearch returns into clean `title`, `ingredient_lines`, and `instructions` reliably enough for ingestion (requirement 1.6.2)?

Ingredients and steps are scored separately. LangSearch returns an excerpt of each page, so many results have a full ingredient list and no steps. That is still useful for matching. A few mistakes are acceptable for the prototype. What we need to know is how many, and which kinds.

## Summary

- `gemini-3.5-flash-lite` produced usable ingredients for 8 of 10 pages and ingredients plus steps for 5 of 10, at about 2 seconds per page.
- The two failures look correct: one page was not a recipe, and one excerpt had no ingredient list.
- Gemini mostly copies what it is given, including the source's mistakes. Nearly every discrepancy in the spot check came from the page or from LangSearch's excerpt. The exception is servings: one value is a confirmed misread (an ingredient count read as servings), and another was inferred from a step.
- Our keyword check missed a real recipe, so ingestion should let Gemini decide whether a page is a recipe.
- Total time, servings, and cuisine are often missing from the excerpt, and Gemini usually leaves them empty instead of guessing. Total time was read correctly in every case checked. Servings is the least reliable field.
- `gemini-3.8-flash` was far too slow in testing (88 seconds for a one-word reply, 121 seconds for one recipe page).

## Method

- Input: the 120 results from the full LangSearch run (SCRUM-14), after skipping repeated URLs and repeated text
- Pages parsed: 8 that our keyword check flagged as mentioning ingredients, plus 2 that it did not
- Models: `gemini-3.5-flash-lite` for the main run; `gemini-3.8-flash` on one page and a speed test only
- API key tier: free tier (no charges)
- Prompt and schema: see `PROMPT` and `ParsedRecipe` in `scripts/spike_parse_recipe.py`

## Results

| Measure | gemini-3.5-flash-lite | gemini-3.8-flash |
|---|---|---|
| Pages parsed | 10 | 1 |
| Usable ingredients | 8/10 (80%) | 1/1 |
| Ingredients AND steps | 5/10 (50%) | 0/1 |
| Ingredients only (no steps) | 3 | 1 |
| Not a recipe | 1 | 0 |
| Recipe but no ingredients found | 1 | 0 |
| No parsed output | 0 | 0 |
| API errors | 0 | 0 |
| Flagged pages with usable ingredients | 7/8 | 1/1 |
| Unflagged pages that were real recipes | 1/2 | not tested |
| Gemini found steps when the text mentioned steps | 4/5 | not tested |
| Average time per page | 2.2 s | 121 s |
| Gemini tokens per page (in / out) | about 364 / 251 | about 200 / 144 |

Fields on the 8 parsed recipes (flash-lite):

| Field | Present |
|---|---|
| Title | 6 of 8 |
| Total time | 3 of 8 |
| Servings | 4 of 8 |
| Cuisine | 0 of 8 |

Results by site for the main run (domains only):

| Site | Result |
|---|---|
| cooksrecipes.com | ingredients only (8 ingredients) |
| food.com | ingredients only (8) |
| relish.com | ingredients only (8) |
| recipes.net | full (13 ingredients, 10 steps) |
| a blogspot recipe blog (daddywaddy) | full (7 ingredients, 9 steps) |
| fabuloussouthernbelle.blogspot.com | full (9 ingredients, 11 steps) |
| cleancuisine.com | not a recipe |
| app.samsungfood.com | full (6 ingredients, 2 steps) |
| davita.com | full (10 ingredients, 12 steps), a page the keyword check had not flagged |
| ohsweetbasil.com | recipe but no ingredients in the excerpt, a page the keyword check had not flagged |

## Model speed

| Test | gemini-3.8-flash | gemini-3.5-flash-lite |
|---|---|---|
| One-word reply ("ok") | 88.0 s (52 thinking tokens) | 0.6 s (no thinking tokens) |
| One recipe page | 121 s | 2.2 s average over 10 pages |

The 3.8 Flash slowness did not come from the prompt or from long reasoning, since it was just as slow on a trivial prompt. The cause is not confirmed (queueing or throttling on the free tier is a guess). Retest on another day: ____

## Spot check

Gemini only sees the excerpt LangSearch returns, not the whole page. So each recipe is judged in two steps: did Gemini copy the excerpt correctly, and was the excerpt itself complete and clean compared with the source page?

| Site | Gemini vs. the excerpt | Excerpt vs. the source page |
|---|---|---|
| recipes.net | Faithful: all 13 ingredient lines match the page | The page's own ingredient list omits the bell pepper that step 3 uses |
| daddywaddy blog | Faithful; total time 30 (prep 10 plus cook 20) and 4 servings both match the excerpt | The ingredient list omits salt, pepper, and vegetable oil that the steps use (all staples) |
| fabuloussouthernbelle.blogspot.com | Faithful | Source URL is a blog category page, not the recipe post |
| app.samsungfood.com | Faithful: 2 steps match the excerpt's "2 steps"; summed prep 5 and cook 5 to 10 minutes and read 4 servings correctly | Ingredient quantities are run into the names in the excerpt itself (for example "corn1 cup"), so the garbling comes from LangSearch's extraction |
| davita.com | Faithful, 12 steps. Servings 6 is not a servings field: it comes from the step "divide chicken into 6 servings", so it is an inference from step text | The ingredient list has no quantities |
| cooksrecipes.com | All 8 lines match the excerpt | n/a (ingredients only) |
| food.com | 8 ingredient lines. Total time 20 matches "Ready In: 20mins". Servings returned as 8, but the excerpt's "Serves:" label has no value and the 8 sits beside "Ingredients: 8", so Gemini read the ingredient count as servings (a confirmed Gemini error: the excerpt shows the `Serves:` label followed by a blank line) | n/a (ingredients only); the excerpt's Serves value is blank |
| relish.com | 8 lines | n/a (ingredients only); "Cooked Rice" has no quantity |

Time and servings values checked against the excerpts: total time was correct in all three cases (food.com 20, daddywaddy 30, Samsung Food 10). Servings were correct for daddywaddy (4) and Samsung Food (4), inferred from step text for davita (6), and wrong for food.com (8, the ingredient count). So Gemini made one apparent error in the fields checked.

## Ingredient recognition (preview on one recipe)

The script skipped recognition because the normalizer and seed data were not in this working copy. As a preview, 9 of the 13 lines from the recipes.net recipe matched the seed list. The misses were:

- `long grain rice` (needs a synonym for rice)
- `corn kernels` (needs a synonym for corn)
- `zest , from 1 lemon` (the normalizer keeps only "zest" and loses the lemon)
- `salt & ground black pepper , to taste` (two ingredients on one line)

This is one recipe, not a rate. Rerun the script after SCRUM-16 and the seed data merge.

## Findings

- 80% of this sample of 10 pages yielded usable ingredients, and 50% also yielded steps. When the excerpt contained steps, Gemini found them in 4 of 5 pages.
- Gemini copied ingredient lines and steps as written, including the source's inconsistencies (ingredients used in the steps but missing from the list, missing quantities, parenthetical asides). Extraction quality is bounded by the source page and by LangSearch's excerpt.
- Total time, servings, and cuisine are often missing: 3 of 8 recipes had a total time, 4 of 8 had servings, and none had a cuisine. For the recipes.net page the excerpt had no time block and no servings line, and Gemini left those fields empty and did not guess. Gemini did sum prep and cook time correctly when the excerpt gave them separately.
- Total time was read correctly in all 3 cases checked, including summing separate prep and cook times. Servings was correct in 2 of 4, inferred from step text in 1, and wrong in 1 (an ingredient count read as servings). Servings is the least reliable field.
- Titles were empty for 2 of 8 parsed recipes.
- The keyword check missed a real recipe (1 of 2 unflagged pages).
- Ingredient lines come back as free text as written, not split into amount, unit, and name.
- Some source URLs are blog category pages (`/search/label/...`), not recipe links.
- Gemini free-tier limits we hit: none in 10 calls with a 4-second pause. Rate limits for this project: ____ (read them in AI Studio, Rate Limit page, filtered to this project).

## Recommendation

- **Gemini-based ingestion of ingredients:** go.
- **Model:** `gemini-3.5-flash-lite`. It is fast, free on our key, and faithful to the text. Retest `gemini-3.8-flash` later.
- **Steps:** about half of pages yield steps. For the rest, store the recipe as ingredients only and show the source link for the method.
- **Outcomes at ingestion:** skip pages that are not recipes or have no ingredients; store ingredients-only recipes; retry once on an API error.
- **Do not pre-filter pages with the keyword check.** Send them to Gemini and use `is_recipe`.
- **Servings:** accept a servings value only when the excerpt has an explicit servings label with a number, or leave servings out of the prototype. In this sample one of four values was a misread and one was inferred.
- **Prompt rule to test next:** the misread happened because the excerpt puts each value on the line after its label, so an empty label makes the number above it look like its value. Try adding a rule such as: "Fill servings, total_minutes, and cuisine only when the text gives a value directly after the matching label. If a label has no value, leave the field empty." Rerun on the same pages and check that food.com's servings becomes empty without breaking the values that were correct.
- **Missing fields:** allow null for time, servings, and cuisine. Do not ask Gemini to guess them. Decide how the max-minutes search filter treats recipes with no time.
- **Title:** fall back to the page name from LangSearch when Gemini returns none.
- **URLs:** skip or rewrite source URLs that are blog category pages, and normalize URLs before checking for duplicates.
- **Ingredient quality:** test a follow-up prompt that returns structured ingredients (name, quantity, unit) so the normalizer, shopping list, and substitutions get cleaner input. Handle compound lines ("salt & pepper") and lines like "zest from 1 lemon" in ingestion.

