# Spike: LangSearch as the Recipe Search Provider (SCRUM-14)

**Status:** Results and terms check recorded. 
**Goal:** find out whether LangSearch finds usable recipe pages, what a search costs against the free plan, and how often the returned text includes the steps.

## Summary
 
- LangSearch is cheap and fast enough for the prototype. A 10-result search costs about 2,400 tokens and takes under 2.5 seconds, against a daily allowance of several million tokens.
- It returns a short **passage** from each page, not the whole page. The passage is usually the part that best matches the query, often the ingredient list.
- About half of all results contain no recipe text at all, and only about a quarter include the steps. Expect to discard roughly half of what comes back.
- Cooking steps need another route: the source link, or Gemini reading the page itself (to be tested in SCRUM-15).


## Account limits (from the LangSearch dashboard and docs)
 
| Limit | Our free plan | Notes |
|---|---|---|
| Price | $0/month | Input and output tokens both cost $0 per million. |
| Requests per second | 5 | Plenty. The script pauses 1 second between calls. |
| Tokens per minute | 1,000,000 | Rolling 60-second window. Not a concern. |
| Tokens per day | More than about 4,000,000 | The dashboard showed under 0.1% used after 3,955 tokens. Exact figure: ____ (tokens used today divided by percent used, after the full run). Resets 00:00 UTC (8 PM Eastern until Nov 1, then 7 PM). |
| Request quotas | None | No separate per-minute or per-day request limits, only tokens. |
| Shared by | All API keys on the account, including MCP | A new key does not add allowance. |
 
How tokens are counted: input is the search query. Output is the returned page text, or the snippet when no full text is returned. Titles, URLs, and dates are free. A search that finishes on the server counts even if our client timed out, so never retry immediately after a timeout.

## Runs

All runs used `scripts/spike_langsearch.py` in text mode.

| Run | Searches | Results per search | `max_chars` | Tokens | Notes |
|---|---|---|---|---|---|
| 1 | 3 | 5 | 3,000 | 3,955 | First test. The script total matched the dashboard exactly (3,955). |
| 2 | 3 | 5 | 10,000 | 3,955 | Identical to run 1 in every number. |
| 3 | 1 | 5 | 300 | 333 | Same query as the first search of run 1, which used 911 tokens. 4 of 5 results hit the limit. |
| 4 | 12 | 10 | 3,000 | 28,970 | The full sample. This is the data the parsing spike reads. |

Dashboard "tokens used today" after all four runs: 37,213

## Results from the full run (run 4)
 
| Measure | Result |
|---|---|
| Searches run | 12 |
| Results returned | 120 |
| Tokens used | 28,970 |
| Average tokens per search | 2,414 |
| Average tokens per result | 241 |
| Median / max latency | 1.71 s / 2.37 s |
| Results with ingredients AND steps in the text | 26 (22%) |
| Results with ingredients but no steps | 31 (26%) |
| Results with neither (blog posts, lists, archive copies, off-topic pages) | 63 (52%) |
| Results that hit the character limit | 1 of 120 (1%) |
| Unique URLs among the 120 results | 120 (no repeated URLs) |
| Unique texts among the 120 results | 102 (18 results, 15%, repeat the exact text of another result under a different URL) |
| Most common domains | recipemenu.neocities.org (5), angiesrecipes.blogspot.com (5), food.com (3), asliceofsouthern.blogspot.com (3), web.archive.org (3), fabulousouthernbelle.blogspot.com (3), katiegalusha.blogspot.com (3), wellplated.com (3) |
 
The "ingredients" and "steps" categories come from a keyword check on the returned text, not from parsing. A real recipe whose excerpt never uses the word "ingredient" counts as "neither," so the true recipe rate may be somewhat higher. The category counts also include the duplicate texts, so the number of distinct recipes is somewhat lower. The parsing spike (SCRUM-15) will give the real number.

## What we learned about `maxCharacters`
 
- It works as a cap. At 300 characters a search dropped from 911 to 333 tokens.
- Raising it from 3,000 to 10,000 changed nothing. The returned passages are usually 200 to 2,500 characters long, which is under the cap, so the cap is not what cuts off the steps.
- Unconfirmed: whether adding words like "ingredients and directions" to a query pulls the steps into the returned passage. This is cheap to test in SCRUM-15.

## What this means for the project
 
- **Token cost is not a constraint.** At about 2,400 tokens per 10-result search and an allowance above 4 million per day, we could run more than 1,600 searches a day.
- **Rough ingestion estimate:** about 57 of 120 results carried an ingredient list (26 + 31). To load around 100 recipes we would run perhaps 20 to 25 searches, roughly 50,000 to 60,000 tokens. This is an estimate until SCRUM-15 shows how many of those pages Gemini can parse.
- **Speed:** 1.7 seconds per search is fine for ingesting recipes ahead of time. It is too slow to call live on every user search once a Gemini parse is added, which supports ingesting first and searching our own database (requirements 1.6.1 and 2.3.1).
- **Quality filter needed:** about half of results are not recipes. Ingestion must discard pages with no ingredient list.
- **Dedupe:** all 120 URLs were unique, but only 102 of the 120 texts were, so 18 results (15%) repeat another result's text under a different URL. The duplicates come mostly from a few blog domains (angiesrecipes.blogspot.com, asliceofsouthern.blogspot.com, fabuloussouthernbelle.blogspot.com, katiegalusha.blogspot.com) and a few recipe sites (averiecooks.com, greatist.com, glutenfreeandmore.com). web.archive.org accounts for only 2, so skipping the archive domain would not fix most of them. The likely cause, not yet confirmed, is one post reachable at several URLs on the same site (for example label, archive, or mobile pages). A plain URL check will not catch these. Ingestion should normalize URLs before comparing them (drop query strings and fragments), skip recipes it has already stored by URL (requirement 1.6.3), and also compare content, for example a hash of the normalized text, or the title plus the ingredient list after parsing.

## Terms check
 
Source: LangSearch Terms of Service and Privacy Policy, both effective 2024-12-19, read October 29, 2026. This is a student's reading, not legal advice.
 
- **Storing returned text and parsed results:** the terms do not address it. They grant a non-exclusive, non-transferable, revocable license to use the API for the purposes the terms specify, but no purposes are listed, and they prohibit scraping, mining, or harvesting data from the service. Keeping a small set of results for a class prototype is neither clearly allowed nor clearly forbidden. The terms say other uses need prior written consent. LangSearch's FAQ and docs also say nothing about storing results. The docs describe using the returned text to compose answers with citations, which is similar to how we plan to use it.
- **Automated or bulk use:** no rule beyond not interfering with or disrupting the service. The service is an API meant for programmatic use. Our scripts pause between calls and stay far below the account limits.
- **Availability:** free-access with no guarantee. LangSearch may modify, suspend, or discontinue the service at its discretion and may terminate access for violations. Pre-load recipes before the demo.
- **Privacy:** the policy says LangSearch collects usage data, including search queries and API requests. Do not put personal data in queries.
- **Attribution:** none required by the terms. We still show the source link and site name (requirement 2.8.2).

## Recommendation

- **Is LangSearch good enough for the prototype?** Yes, for finding recipe URLs and ingredient lists.
- **Settings to use:** `count` of 10 and the default `maxCharacters` of 3,000. Lowering the cap saves tokens but risks cutting ingredient lists. Raising it does nothing.
- **Steps:** do not rely on LangSearch text for steps. Show the source link, or test Gemini reading the page (SCRUM-15).
- **Plan for the demo:** pre-load 50 to 100 recipes before demo day so the demo does not depend on live calls.
- **Risks:** about half of results are not recipes; passages may omit steps; terms on storing text are unchecked; and the same pages repeat across queries.