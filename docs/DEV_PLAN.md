# SmartRecipe (Smart Recipe Matching): Development Plan

Team 7 "Mawazo Lab": Kyele Duggan, Manuel Busingye, Kaelynn Danso, Endelia Garcia-Romero
Software Engineering, Fall 2026 (David James)

Sources: Requirements doc, ERD (`Smart_Recipe_ERD.drawio`), wireframes, testing scenarios, project deck, team doc.
Status: revision of the first draft, for review at the Saturday 2 PM meeting. Sprint dates are proposals, not commitments.

---

## 1. Overview

SmartRecipe takes the ingredients a user already owns and returns recipes ranked by how well they match, with substitutions for near matches. When nothing fits, it generates a custom recipe. Users keep preferences, an ingredient inventory, saved recipes, and a shopping list.

What sets it apart from tools like MyFridgeFood (per the deck): synonym-aware matching ("sirloin steak" vs "beef"), tiered results with substitutes instead of exact-match-only, and persistent personalization (diets, allergies, blacklists).

**Why it is not a single LLM prompt** (deck, slide 7): mutable per-user data, a web-scraping/search pipeline that grows the recipe store, deterministic ranking logic, and backend validation that rejects non-food input.

## 2. Tech stack and architecture

| Layer | Choice | Responsibility |
|---|---|---|
| Frontend | React + JSX/CSS | Pages, forms, loading/error states, calls REST API |
| Backend | FastAPI (Python) | Auth, validation, matching/ranking, shopping list logic, external API calls |
| Database | PostgreSQL | All persistent data |
| GenAI | Gemini API | Recipe generation, substitutions, personalization |
| Recipe search | LangSearch API | Find recipes on the web |

Suggested supporting tools (not in the requirements, so confirm as a team): SQLAlchemy + Alembic (ORM and migrations), Pydantic (validation), pytest + httpx (backend tests), Vitest + React Testing Library (frontend), Docker Compose (shared local Postgres), GitHub Actions (CI).

**Backend structure** (supports requirement 2.5.2, swappable providers):

```
backend/app/
  api/            routers: auth, users, ingredients, recipes, my_recipes, shopping_list
  core/           config, security (hashing, JWT), error handling
  db/             models, session, migrations
  services/
    matching.py       ingredient normalization, scoring, tiering
    recipe_store.py   dedupe, persist, reuse
    shopping.py       aggregation, add/remove recipe
  providers/
    base.py           RecipeSearchProvider, GenAIProvider (interfaces)
    langsearch.py     implements RecipeSearchProvider
    gemini.py         implements GenAIProvider
```

Core logic depends only on the interfaces in `providers/base.py`. A provider outage falls back to stored recipes (requirement 2.2.1.3).

**Search flow**

1. Client posts ingredients plus optional details (max time, servings, tools, free-text description).
2. Backend normalizes each ingredient through synonyms and validates it against the `ingredient` table (1.3.2, 1.3.7). Too few or invalid ingredients returns a clear error (1.3.12).
3. Backend queries the local recipe store first, and calls LangSearch when local results are thin. Fetched recipes are parsed into `recipe` and `recipe_ingredient` rows, deduplicated by source URL (1.6.1 to 1.6.3).
4. Exclude recipes that hit the user's allergies, blacklist, or diet conflicts (1.3.10).
5. Score and tier each recipe; for near matches, list missing ingredients and ask Gemini for substitutes (1.3.8, 1.3.9).
6. Return ordered results. If the user taps "Generate it!" (or no matches exist), Gemini generates a recipe constrained to validated ingredients and the user's restrictions (1.5.x), and it is stored with `generated_tag = true`.

**Scoring sketch:** `match = covered_required_ingredients / total_required_ingredients`, with pantry staples (salt, pepper, water, oil) weighted low or ignored. Missing ingredients that have a substitute in the user's inventory count as partially covered. Tier thresholds go in config so they can be tuned.

## 3. ERD review: gaps between ERD, requirements, and wireframes

The ERD covers the core well. Resolve these before writing migrations.

**Must fix (the app cannot do what the wireframes show without these)**

| # | Issue | Evidence | Proposed fix |
|---|---|---|---|
| 1 | `IngredientSnonym` is misnamed and its key is wrong: PK is `User_ID`, with an `Ingredient_ID` FK and an `Alias` | Synonyms are global, not per user (1.3.7) | Rename `IngredientSynonym`; PK `Synonym_ID`; FK `Ingredient_ID`; unique `Alias`; drop `User_ID` (or keep only if per-user aliases are intended) |
| 2 | No star flag on saved recipes | Wireframe "Star and add to MyRecipes", "Starred" filter, test 3.5 and 4.2 | Add `Is_Starred boolean` to `BookmarkedRecipe` |
| 3 | Shopping list cannot track which recipe an item came from | Wireframe "Recipes in cart (3)", "2 recipes" badge, "Removing a recipe also removes its ingredients", test 5.2 | Add `Source_Recipe_ID` (nullable, null = added manually) to `ShoppingListItem` and store one row per recipe contribution; aggregate on read. Add `Unit` |
| 4 | `Recipe` lacks fields the UI shows and filters on | Cards show time, rating, review count; search filters time, servings, tools | Add `Total_Minutes`, `Servings`, `Rating_Avg`, `Rating_Count`, `Cuisine`, `Tools` (text array) |
| 5 | Password column | Req. 2.4.1.3 and 2.4.2.1 | Rename `Password_Hash`; store Argon2/bcrypt hash only |
| 6 | No way to tag a recipe with a diet | Req. 1.3.10 requires excluding diet conflicts | Add `RecipeDiet(Recipe_ID, Preference_ID)`, filled from source data or by Gemini classification at ingest |

**Should fix or decide**

| # | Issue | Recommendation |
|---|---|---|
| 7 | Requirements and wireframes disagree on tiers: 1.3.5 says two tiers (perfect, near); wireframe shows three (Best, Partial, Low) | Pick one. The wireframe version is richer; if kept, update requirement 1.3.5 and the icons in 2.1.1.3 |
| 8 | Budget appears in the use case diagram and architecture section but nowhere in the functional requirements, ERD, or wireframes | Either drop it from the docs or add a requirement and `Budget` field. Recommend deferring |
| 9 | Expiry notifications (1.2.6): the ERD stores `Expiration_Date`, but nothing records notifications | Start with a computed "expiring soon" badge on inventory (query on read). Email or push alerts are a stretch goal |
| 10 | `UserInventory` has no uniqueness rule | Add unique `(User_ID, Ingredient_ID)` to prevent duplicate rows (1.1.2 style) |
| 11 | Recipe dedupe (1.6.3) | Unique index on normalized `Source_URL`; generated recipes have no URL, so dedupe on a hash of title plus ingredient set if wanted |
| 12 | Wireframes show profile picture and Delete account; neither is in the requirements or ERD | Delete account is simple (cascade deletes) and worth including. Profile picture: add `Avatar_URL` or drop from scope |
| 13 | Cooking tools are a search filter only | Fine to keep as a request parameter; saved tool preferences are optional later |
| 14 | `Preference.Type` is free text | Constrain to `dietary` or `cuisine`. Likewise `Restriction_Type` to `allergy` or `blacklist`, `Shelf_Life_Type` to `perishable` or `long_life`, `Status` to `pending` or `purchased` |
| 15 | Units | Store units as a controlled list (g, kg, oz, lb, ml, l, tsp, tbsp, cup, clove, can, pack, count). Summing across different units needs a small conversion table; otherwise show separate lines |

### Proposed PostgreSQL schema (after fixes)

```sql
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE users (
  user_id        BIGSERIAL PRIMARY KEY,
  username       CITEXT NOT NULL UNIQUE,
  email          CITEXT NOT NULL UNIQUE,
  password_hash  TEXT NOT NULL,
  avatar_url     TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ingredient (
  ingredient_id  BIGSERIAL PRIMARY KEY,
  name           CITEXT NOT NULL UNIQUE,
  category       TEXT,
  is_staple      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE ingredient_synonym (
  synonym_id     BIGSERIAL PRIMARY KEY,
  ingredient_id  BIGINT NOT NULL REFERENCES ingredient ON DELETE CASCADE,
  alias          CITEXT NOT NULL UNIQUE
);

CREATE TABLE preference (
  preference_id  BIGSERIAL PRIMARY KEY,
  name           CITEXT NOT NULL,
  type           TEXT NOT NULL CHECK (type IN ('dietary','cuisine')),
  UNIQUE (name, type)
);

CREATE TABLE user_preference (
  user_id        BIGINT REFERENCES users ON DELETE CASCADE,
  preference_id  BIGINT REFERENCES preference ON DELETE CASCADE,
  PRIMARY KEY (user_id, preference_id)
);

CREATE TABLE user_restricted (
  user_id          BIGINT REFERENCES users ON DELETE CASCADE,
  ingredient_id    BIGINT REFERENCES ingredient ON DELETE CASCADE,
  restriction_type TEXT NOT NULL CHECK (restriction_type IN ('allergy','blacklist')),
  PRIMARY KEY (user_id, ingredient_id)
);

CREATE TABLE user_inventory (
  inventory_id    BIGSERIAL PRIMARY KEY,
  user_id         BIGINT NOT NULL REFERENCES users ON DELETE CASCADE,
  ingredient_id   BIGINT NOT NULL REFERENCES ingredient,
  quantity        NUMERIC(10,2),
  unit            TEXT,
  shelf_life_type TEXT NOT NULL DEFAULT 'long_life' CHECK (shelf_life_type IN ('perishable','long_life')),
  expiration_date DATE,
  added_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, ingredient_id)
);

CREATE TABLE recipe (
  recipe_id      BIGSERIAL PRIMARY KEY,
  title          TEXT NOT NULL,
  instructions   TEXT NOT NULL,
  image_url      TEXT,
  source_url     TEXT UNIQUE,            -- NULL for generated recipes
  generated_tag  BOOLEAN NOT NULL DEFAULT FALSE,
  total_minutes  INT,
  servings       INT,
  rating_avg     NUMERIC(2,1),
  rating_count   INT,
  cuisine        TEXT,
  tools          TEXT[],
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE recipe_ingredient (
  recipe_ingredient_id BIGSERIAL PRIMARY KEY,
  recipe_id     BIGINT NOT NULL REFERENCES recipe ON DELETE CASCADE,
  ingredient_id BIGINT NOT NULL REFERENCES ingredient,
  quantity      NUMERIC(10,2),
  unit          TEXT,
  is_optional   BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX ON recipe_ingredient (ingredient_id);   -- supports ingredient-based ranking (1.6.2)
CREATE INDEX ON recipe_ingredient (recipe_id);

CREATE TABLE recipe_diet (
  recipe_id     BIGINT REFERENCES recipe ON DELETE CASCADE,
  preference_id BIGINT REFERENCES preference ON DELETE CASCADE,
  PRIMARY KEY (recipe_id, preference_id)
);

CREATE TABLE bookmarked_recipe (
  user_id       BIGINT REFERENCES users ON DELETE CASCADE,
  recipe_id     BIGINT REFERENCES recipe ON DELETE CASCADE,
  is_starred    BOOLEAN NOT NULL DEFAULT FALSE,
  bookmarked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, recipe_id)
);

-- One row per contribution; source_recipe_id NULL = added manually.
CREATE TABLE shopping_list_item (
  item_id          BIGSERIAL PRIMARY KEY,
  user_id          BIGINT NOT NULL REFERENCES users ON DELETE CASCADE,
  ingredient_id    BIGINT NOT NULL REFERENCES ingredient,
  quantity         NUMERIC(10,2),
  unit             TEXT,
  source_recipe_id BIGINT REFERENCES recipe ON DELETE SET NULL,
  status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','purchased'))
);
CREATE INDEX ON shopping_list_item (user_id, ingredient_id);
```

The shopping list screen (ingredients list plus "Recipes in cart") is built by `GROUP BY ingredient_id, unit` over this table, which makes "remove recipe" a single delete and keeps ingredients still needed by other recipes (test 5.2).

## 4. Features and priorities

**Must have (MVP)**

- Register, log in, log out, auto-logout after inactivity (1.1.1 to 1.1.3, 2.4.1.2)
- Preferences, allergies, blacklist (1.1.4 to 1.1.6)
- Owned ingredients with quantity and unit; edit, delete (1.2.1 to 1.2.3, 1.2.5)
- Ingredient search with validation and synonyms (1.3.1, 1.3.2, 1.3.7, 1.3.12)
- Recipe matching with tiers, restriction filtering, detail page (1.3.3 to 1.3.6, 1.3.10, 1.3.11)
- Recipe ingestion from LangSearch and store/reuse (1.6.x)
- My Recipes: save, star, search, sort, filter, remove
- Shopping list: add from recipe, add manually, edit, remove, remove recipe

**Should have**

- Substitution suggestions and missing-ingredient lists (1.3.8, 1.3.9)
- Generate a recipe via Gemini (1.5.x), including the three one-click options (random from owned, random from diet/cuisine, Surprise me)
- Mark shopping items purchased and move to inventory (1.4.3)
- Perishable vs long-life indicators and expiring-soon badge (1.2.4, 2.1.1.4)
- Accessibility pass to WCAG 2.1 AA (2.1.2)

**Later or stretch**

- Expiry notifications by email or push (1.2.6)
- Budget feature, profile picture, bulk ingredient import
- Replication, backup automation, uptime monitoring (2.2.x), which are mostly deployment concerns

## 5. API design (REST, all under `/api/v1`, JSON, JWT auth except register/login)

| Area | Endpoint | Purpose |
|---|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout` | Account lifecycle; duplicate email/username returns 409 |
| User | `GET/PATCH /users/me`, `DELETE /users/me` | Account info, delete account |
| Prefs | `GET /users/me/preferences`, `PUT /users/me/preferences` | Diets and cuisines |
| Restrictions | `GET/POST /users/me/restrictions`, `DELETE /users/me/restrictions/{ingredient_id}` | Allergies and blacklist |
| Inventory | `GET/POST /inventory`, `PATCH/DELETE /inventory/{id}` | Owned ingredients |
| Ingredients | `GET /ingredients?q=` | Autocomplete and validation |
| Search | `POST /recipes/search` | Body: ingredients, max_minutes, servings, tools, description |
| Random | `POST /recipes/random` | Body: `mode` = `owned` or `preferences` or `surprise` |
| Generate | `POST /recipes/generate` | Gemini generation from a prior search payload |
| Detail | `GET /recipes/{id}` | Ingredients, steps, source link |
| My Recipes | `GET /my-recipes?sort=&starred=&q=&cuisine=`, `PUT /my-recipes/{id}` (`starred` in body), `DELETE /my-recipes/{id}` | Save, star, remove |
| Shopping | `GET /shopping-list`, `POST /shopping-list/items`, `PATCH/DELETE /shopping-list/items/{id}`, `POST /shopping-list/recipes/{recipe_id}`, `DELETE /shopping-list/recipes/{recipe_id}`, `POST /shopping-list/items/{id}/purchase` | Cart behavior |

Error format: `{ "error": { "code": "...", "message": "..." } }`. No stack traces or internal IDs beyond what the client needs (2.4.2.4). Use a consistent ID strategy and decide early whether to expose opaque IDs.

## 6. Frontend pages (from wireframes)

1. **Home**: hero, "Start searching", how-it-works cards. Two panels are crossed out in the wireframe ("How to use it", "Good to know"); decide whether they are cut or just undesigned.
2. **User information**: account info (Update info, Log out, Delete account), owned ingredients with inline edit, allergies, preferred cuisine.
3. **Search/Generate**: three one-click cards, ingredient builder (name, qty, unit, edit, delete), recipe details (time, servings, tools), meal description, Search.
4. **Results**: summary of the search with Edit search, "Generate it!" button, tiered cards.
5. **Recipe detail**: Add to MyRecipes, Star and add, Add ingredients to shopping list, ingredient checklist, source link. Note the wireframe checks owned ingredients, which implies the page needs inventory data.
6. **My Recipes**: search, sort, quick filters.
7. **Shopping list**: manual add, recipes in cart, aggregated ingredients with source badge.

Shared: navbar, auth guard, loading/empty/error states, responsive layout (2.7.1.2).

## 7. Sprint plan (2-week sprints; dates TBD at Saturday's meeting)

| Sprint | Goal | Key tasks | Done when |
|---|---|---|---|
| 0 (done) | Project setup | Repo, branch protection, README, contribution workflow, first plan draft | PR merged |
| 1 | Foundations | Docker Compose with Postgres; Alembic migrations from section 3 schema; seed `ingredient`, `synonym`, `preference`; FastAPI skeleton with config and error handler; auth (register, login, hashing, JWT); React app shell, router, login/register pages; CI running lint and tests | A user can register, log in, and see a protected page |
| 2 | Profile, inventory, search API | User info page and endpoints; inventory CRUD; restrictions; ingredient autocomplete; `RecipeSearchProvider` plus LangSearch implementation; recipe parsing and storage with dedupe; search page UI | Search returns stored recipes for validated ingredients |
| 3 | Matching and recipe views | Normalization and synonym matching; scoring and tiers; restriction filtering; results page; recipe detail page; My Recipes (save, star, filter, sort, remove) | Test scenarios 1.x to 4.x pass manually |
| 4 | Generation and shopping | Gemini provider; Generate button and three one-click options; substitutions for near matches; shopping list (aggregation, add recipe, remove recipe, manual edits); purchased-to-inventory | Test scenarios 5.x pass; Generate works with fallback |
| 5 | Hardening and demo | Accessibility audit; error and loading states; provider-outage fallback; performance check (3 s for 20 ingredients); security review; seed demo data; full test pass; final report and demo script | Release candidate demoed |

If the semester ends sooner than five sprints, merge sprints 4 and 5 and move the "Should have" generation items last. Tell me the final deadline and I will re-cut this.

## 8. Suggested ownership (to be agreed by the team)

Based on the strengths listed in the team document. These are suggestions only.

| Area | Lead | Support | Why |
|---|---|---|---|
| Database schema, migrations, core FastAPI, matching logic | Manuel | Kyele | SQL, FastAPI, PostgreSQL experience |
| Recipe ingestion (LangSearch, parsing, dedupe) and Gemini provider | Kyele | Manuel | Web-import and data experience |
| Auth, security, encryption at rest, input validation | Kaelynn | Endelia | Security focus |
| Frontend pages, accessibility, test suites | Endelia | Manuel (React/TS) | Frontend and testing interest; Manuel has React experience |

Everyone writes tests for their own endpoints and reviews at least one other person's PR. Merges follow the team agreement: meet to discuss conflicts, clear commit messages, 2 approvals required.

## 9. Testing strategy

- **Unit (pytest):** ingredient normalization, synonym lookup, scoring and tier thresholds, shopping list aggregation, unit conversion, restriction filtering. Mock providers behind the interfaces.
- **API (pytest + httpx, test database):** each endpoint, including auth failures, duplicate registration, invalid ingredients.
- **Frontend (Vitest + RTL):** forms, inline edit, filters, loading and error states.
- **End to end:** the 22 scenarios in the Testing Scenarios document, run manually per sprint and automated (Playwright or Cypress) for the most important flows.

| Scenario group | Covers |
|---|---|
| 1.x Homepage/User info | Login, account update, owned ingredients, allergies, cuisines, logout |
| 2.x Recipe search | Ingredient CRUD before search, search details, three one-click modes |
| 3.x Results/Details | Tier display, Generate it, detail view, save, star, add to shopping list |
| 4.x My Recipes | Search, sort, starred filter, remove |
| 5.x Shopping list | Add/edit/delete, multi-recipe aggregation, remove one recipe, review |

**Non-functional checks:** search under 3 s with 20 ingredients, synonym matching adds under 1 s, generation under 10 s or shows a loading state, WCAG contrast and keyboard checks, HTTPS only.

## 10. Risks and open questions

| Risk or question | Mitigation or recommendation |
|---|---|
| Scraped recipe sites are inconsistent or block scraping; ingredient parsing ("2 cloves garlic, minced") is hard | Use LangSearch for discovery, parse with Gemini structured output plus a validator; keep a seed set of recipes for demos |
| External free-tier API limits and latency | Cache aggressively, reuse stored recipes first, fallback path, rate-limit per user |
| Gemini generating unsafe or invalid recipes (allergens, non-food) | Pass restrictions in the prompt and re-check the output against `user_restricted` before returning |
| Ingredient list coverage (what counts as "recognized food", 1.3.2) | Seed from an open ingredient dataset; allow admin-curated additions |
| Unit conversion when aggregating | Convert within unit families; otherwise show separate lines |
| Source attribution and copyright (2.8.2) | Show source link and site name; store a summary and structured data rather than copying page text |
| Encryption at rest (2.4.2.2) may depend on the hosting choice | Decide hosting early; use managed Postgres encryption or column encryption for sensitive fields |
| Scope vs timeline | MVP list in section 4 is the line; everything else moves only if ahead of schedule |

**Decisions needed from the team**

1. Two tiers or three (item 7 in the ERD review)?
2. Keep or cut budget, profile picture, and the crossed-out home panels?
3. Final semester deadline and demo date, to lock sprint dates.
4. Hosting target (needed for 2.2.x and 2.4.2.2).
5. Should shopping list edits on an aggregated line adjust the source rows, or add a manual adjustment row?
