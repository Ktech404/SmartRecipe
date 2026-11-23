# SmartRecipe backend

Requires Python 3.10+ and Docker Desktop with Linux containers.
Run Docker commands from the repository root; run Python commands from `backend`.

## Installation

```powershell
docker compose up -d
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv/Scripts/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the generated value into `JWT_SECRET_KEY` in your local `.env`.
Keep `.env` and `.venv` untracked. On macOS/Linux use `.venv/bin/python`
and `cp .env.example .env` instead.

## Environment

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Development PostgreSQL SQLAlchemy URL, using `postgresql+psycopg` |
| `TEST_DATABASE_URL` | Disposable PostgreSQL database; name must end in `_test` and differ from development |
| `JWT_SECRET_KEY` | Required random signing secret, at least 32 bytes; no default |
| `LANGSEARCH_API_KEY` | API key for LangSearch recipe search (from the LangSearch dashboard) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime, 1–1440 minutes; default 30 |
| `GEMINI_API_KEY` | API key for Gemini recipe parsing (Google AI Studio) |
| `GEMINI_MODEL` | Optional. Gemini model name; default `gemini-3.5-flash-lite` |
| `LIVE_SEARCH_ENABLED` | Optional. `false` turns the web fallback of `POST /recipes/search` off; default `true` |
| `LIVE_SEARCH_THIN_THRESHOLD` | Optional. Search the web when fewer than this many best or partial matches are stored; default 5 |
| `LIVE_SEARCH_MAX_PAGES` | Optional. Web pages requested per live search; default 6 |
| `LIVE_SEARCH_TARGET` | Optional. Stop a live search after storing this many new recipes; default 3 |
| `LIVE_SEARCH_PARSE_DELAY` | Optional. Seconds to wait between Gemini calls (or batches); default 1.0 |
| `LIVE_SEARCH_WORKERS` | Optional. Pages parsed at the same time; default 2. Use 1 if Gemini rate limits |
| `LIVE_SEARCH_CACHE_HOURS` | Optional. Do not repeat a successful web search for the same ingredients for this long; default 24, `0` turns it off |

Live search needs both `LANGSEARCH_API_KEY` and `GEMINI_API_KEY`. Without them the
search endpoint still works from stored recipes and reports `degraded: true`.

The example database credentials are for the local Docker service only.
Use independent credentials and HTTPS for deployed services. Do not log request
bodies, passwords, bearer tokens, or SQL parameter values. Changing the signing
secret invalidates existing tokens.

## Migrations and server

From `backend`, after configuring `.env`:

```powershell
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m scripts.seed
.venv/Scripts/python -m uvicorn app.main:app --reload
```

Seeding is idempotent and required for search. It loads the ingredient vocabulary,
allergen groups and ingredient hierarchy from `backend/seed/` (`ingredients.csv`,
`ingredient_synonyms.csv`, `allergen_groups.csv`, `ingredient_allergen_groups.csv`,
`ingredient_parents.csv`), plus the dietary and cuisine preferences defined in
`scripts/seed.py`. `ingredient_parents.csv` says which ingredients are kinds of another
("cheddar cheese" is a kind of "cheese"); matching, restrictions and substitute
suggestions all use it. To change the vocabulary, edit the CSV files and run the seed
again. Synonyms follow the CSV exactly (changed aliases are updated and removed ones
are deleted); ingredients are never deleted. Schema changes remain managed by Alembic;
the application does not create tables automatically.

Health: <http://127.0.0.1:8000/health>. Interactive documentation:
<http://127.0.0.1:8000/docs> and <http://127.0.0.1:8000/redoc>.
OpenAPI: <http://127.0.0.1:8000/openapi.json>.

## Authentication API

| Method and path | Contract |
| --- | --- |
| `POST /auth/register` | JSON `username`, `email`, `password`; public profile (201), duplicate (409), invalid request (422) |
| `POST /auth/login` | JSON `username`, `password`; returns `access_token`, `token_type`, `expires_in`; invalid credentials (401) |
| `GET /auth/me` | `Authorization: Bearer <access_token>`; public profile, invalid/missing/expired token (401) |

Usernames accept 3–50 ASCII letters, digits, or underscores. Registration passwords
accept 12–128 characters; passwords are not trimmed. Email must be valid and at most
254 characters. PostgreSQL CITEXT constraints enforce case-insensitive username/email
uniqueness. Passwords use Argon2id hashing. JWTs use HS256, expiration, user ID
subject, issuer and audience validation. Profiles never include password fields.
Request validation responses omit submitted inputs. Swagger's Authorize dialog
accepts the access token returned by JSON login.

## Recipe search API

`POST /recipes/search` finds recipes that match the ingredients a user has. It needs
`Authorization: Bearer <access_token>`.

Request (only `ingredients` is required):

```json
{
  "ingredients": [{"name": "chicken breast"}, {"name": "rice"}, {"name": "garlic"}],
  "max_minutes": 30,
  "servings": 2,
  "tools": ["oven"],
  "description": "a cozy weeknight dinner",
  "limit": 20,
  "offset": 0
}
```

- At least 2 different ingredients are required. Names are matched through the
  ingredient vocabulary and its synonyms, so "chicken" finds every kind of chicken.
- `max_minutes` keeps recipes with no stored time. `tools` is the tools the user
  has: a recipe is dropped if it needs a tool that is not listed.
- The user's saved allergies, allergen groups and blacklist are always applied.
- `limit` is 1–50 (default 20); `offset` pages through the results.

Response: `results` (each with `recipe_id`, `title`, `source_url`, `tier`,
`match_score` and `missing_ingredients` with quantities and substitute suggestions),
`total`, `limit`, `offset` and `degraded`.

Tiers come from `app/services/matching.py`: `best` at 0.8 or more of the recipe's
required ingredients covered, `partial` at 0.5 or more, `low` below that. Recipes
under 0.25 are not returned. Owning a more specific ingredient covers a general one
("cheddar" covers "cheese"), and the reverse; siblings do not cover each other but
are suggested as substitutes.

Errors use one body, `{"error": {"code", "message", ...}}`, with status 422 and
codes `too_few_ingredients`, `invalid_ingredients` (lists the names that are not
recognized as food) and `validation_error`. A missing or expired token returns 401.

When fewer than `LIVE_SEARCH_THIN_THRESHOLD` good matches are stored (first page only),
the endpoint searches the web, parses and stores new recipes, and searches again. This
takes roughly 10–20 seconds. If the web part fails, the stored results are returned with
`degraded: true`. A successful web search for the same ingredients is not repeated for
`LIVE_SEARCH_CACHE_HOURS`.

## Loading recipes (ingestion)

Recipes are collected from the web with LangSearch, parsed by Gemini, mapped to the
ingredient vocabulary and stored. Run from `backend`, after `alembic upgrade head` and
`scripts.seed`:

```powershell
.venv/Scripts/python -m scripts.ingest "chicken, rice, garlic"
.venv/Scripts/python -m scripts.ingest "chicken, rice, garlic" --dry-run
.venv/Scripts/python -m scripts.ingest --file queries.txt --limit 10
.venv/Scripts/python -m scripts.ingest --default --target 60
```

- `--dry-run` parses and maps but stores nothing. Ctrl+C stops safely; stored recipes
  are kept.
- A recipe is skipped if any ingredient line is not in the vocabulary
  (`--allow-unrecognized N` loosens this). The run ends with a list of the most common
  unrecognized lines: add them to `seed/ingredients.csv` or `seed/ingredient_synonyms.csv`
  and run `scripts.seed` again.
- `--prefilter` skips pages that cannot be recipes before spending Gemini calls;
  `--workers N` parses N pages at the same time.
- Duplicates are skipped by URL, by site and title, and by content.
- A full `--default` run uses roughly 130k LangSearch tokens and 100k Gemini input
  tokens. A Gemini rate limit stops the run cleanly; run it again after it resets.

## Testing

Create the disposable database once from the repository root:

```powershell
docker compose exec -T db createdb -U smartrecipe smartrecipe_test
```

From `backend`:

```powershell
.venv/Scripts/python -m pytest -v
.venv/Scripts/python -m pip check
```

With `TEST_DATABASE_URL` configured, tests run real PostgreSQL migrations and
exercise authentication, CITEXT uniqueness, constraints, cascades and seeds.
The session fixture rolls back each test, including commits issued by API handlers.
The session-level migration fixture resets the dedicated test database. Never put
valuable data in that database. A guard rejects non-PostgreSQL targets, names without
`_test`, and names matching `DATABASE_URL`, before any migration reset.

Without `TEST_DATABASE_URL`, PostgreSQL tests are explicitly skipped. Health,
request validation, configuration and safety tests run without a database connection;
they are not substitutes for PostgreSQL integration tests. Tests generate an ephemeral
signing secret instead of using a deployment secret.
