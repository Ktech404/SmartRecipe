# Development Plan (Draft)

**Team 7, "Mawazo Lab"**: Kyele Duggan, Manuel Busingye, Kaelynn Danso, Endelia Garcia-Romero
Software Engineering, Fall 2026

> Status: **DRAFT**. To be reviewed and finalized at the team meeting on Saturday at 2 PM.
> Based on: Project Requirements, Use Case and Proposed Technologies; Testing Scenarios; wireframes; ERD.

## 1. Project Overview

**Project:** Smart Recipe Matching

A web application that takes a list of ingredients from the user and returns matching recipes. Recipes are sourced from the web, or generated with AI when there is no good match. User accounts, ingredient inventory, dietary preferences, recipes and shopping lists are stored in a database.

**Problem solved:** People often have plenty of food at home but no idea what to cook, which leads to waste and extra spending.

**Target users:** meal preppers, college students, and budding home cooks.

**Differentiators vs. competitors (e.g., MyFridgeFood):**
- Flexible matching, with perfect-match and near-match tiers
- Ingredient synonym recognition (e.g., "sirloin steak" vs. "beef")
- Substitution suggestions for missing ingredients
- Saved preferences: diets, allergies, blacklisted ingredients

## 2. Tech Stack

| Area | Choice | Notes |
|------|--------|-------|
| Frontend | React + HTML/JSX + CSS | Responsive; WCAG 2.1 AA accessibility |
| Backend | FastAPI (Python), RESTful API | Authentication, matching logic, external API calls |
| Database | PostgreSQL | Users, inventory, recipes, shopping lists; ERD already drafted |
| AI generation | Gemini API | Custom recipes, substitutions, personalization |
| Recipe search | LangSearch API / web-scraping pipeline | Finds recipes across the web |
| Version control | Git + GitHub | `main` protected; PR required with approvals |
| Testing | [Pytest for backend; frontend framework TBD] | Scenarios in Testing Scenarios document |
| Project tracking | Jira (starting next week) | |

## 3. Main Features

**Must-have (MVP):**
1. **User accounts:** register, log in, set dietary/cuisine preferences, allergies and blacklisted ingredients
2. **Ingredient inventory:** add/update/remove items with quantity; mark perishable vs. long shelf-life
3. **Recipe matching:** validate ingredients, return recipes in perfect-match and near-match tiers, exclude conflicts with user restrictions
4. **Recipe details:** ingredients, quantities, steps, source link
5. **Shopping list:** add missing ingredients, edit/remove, mark purchased (moves to inventory)
6. **Database layer:** PostgreSQL schema from the ERD, with recipe storage to avoid duplicates

**Next priority:**
- Ingredient synonym recognition
- Substitution suggestions for near matches
- AI-generated custom recipes when no good match exists (Gemini)
- My Recipes: save, star, sort and filter
- Expiration notifications for perishable items

**Stretch / nice-to-have:**
- "Surprise Me" random recipe search
- Search by prep time, cook time, servings and tools
- Monitoring/alerting, database replication, graceful fallback to cached recipes when external APIs fail

## 4. Architecture

- **Frontend (React):** search UI, inventory, shopping list, recipe pages, loading/error states
- **Backend (FastAPI):** authentication, user preferences, ingredient validation and matching, shopping list logic, calls to Gemini and LangSearch
- **Database (PostgreSQL):** persistent data; designed around the ERD (User, UserPreference, UserInventory, Ingredient, IngredientSynonym, Recipe, RecipeIngredient, BookmarkedRecipe, ShoppingListItem)
- The GenAI and search providers should be swappable without rewriting matching logic.

## 5. Rough Timeline

*Dates are placeholders. Adjust them to the course calendar.*

| Sprint | Dates | Focus | Deliverable |
|--------|-------|-------|-------------|
| Sprint 1 | [dates] | Repo setup, branch protection, project structure, draft dev plan | Protected `main`, initial commits from each member, this plan |
| Sprint 2 | [dates] | Finalize plan and assign tasks (Jira); DB schema in PostgreSQL; FastAPI skeleton; React skeleton; user accounts | Working database, auth endpoints, app shell |
| Sprint 3 | [dates] | Inventory, shopping list, basic recipe search and matching | Core flows working end to end |
| Sprint 4 | [dates] | Tiered matching, synonyms, substitutions, Gemini recipe generation, My Recipes | Full feature set |
| Sprint 5 | [dates] | Testing, accessibility, bug fixes, polish, demo prep | Tested build and final presentation |

## 6. Proposed Work Areas

*Proposed from team strengths; to be confirmed Saturday.*

| Member | Proposed area | Strengths |
|--------|---------------|-----------|
| Manuel | Database (schema, queries) and backend endpoints | SQL, Python, FastAPI/PostgreSQL |
| Kyele | Recipe search/scraping pipeline, backend integration | Python, BeautifulSoup, PostgreSQL |
| Kaelynn | Authentication, security, data protection | Security, Python |
| Endelia | Frontend and testing | HTML/CSS/JS, secure coding, testing |

## 7. Team Workflow

- Work on a personal branch; never push directly to `main`.
- Open a pull request; at least **2 approvals** before merging.
- Clear commit messages that explain what changed.
- Meet before merging when there may be conflicts.
- Weekly Discord meeting; reply to messages within 24 hours.
- Rotating submitter; submit at least 24 hours before the deadline.

## 8. Open Questions for Saturday

- [ ] Confirm the work areas in section 6
- [ ] Final sprint dates from the syllabus
- [ ] Which features are in the MVP vs. next priority
- [ ] Frontend testing framework
- [ ] Who sets up Jira and when
- [ ] Which pull-request approval count we use (2 proposed)
