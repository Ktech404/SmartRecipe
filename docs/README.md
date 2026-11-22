# Smart Recipe

An online web application that leverages AI to match whatever ingredients you have in your house to delicious, affordable, real recipes that you make on a busy weeknight, or a Sunday dinner!

Built by Team 7 (Mawazo Lab) for Software Engineering, Fall 2026.

## Features

- Search for recipes by the ingredients you have, ranked as best, partial or low matches
- Filters for cooking time, available tools and servings
- Allergy and blacklist restrictions, including allergen groups, applied before results are shown
- Substitution suggestions for missing ingredients
- Live recipe search: when stored results are thin, new recipes are found online (LangSearch), parsed with Gemini and saved for next time
- User accounts with registration and login

## Tech stack

- Frontend: Next.js (`smart-recipe/`)
- Backend: FastAPI, SQLAlchemy, Alembic (`backend/`)
- Database: PostgreSQL 16 (Docker)
- AI and search: Gemini and LangSearch

## Requirements

- Python 3.10 or newer
- Node.js and npm
- Docker (for PostgreSQL)
- A LangSearch API key and a Gemini API key (only needed for live search and loading recipes)

## How to run

### 1. Database

From the repository root:

```
docker compose up -d
```

### 2. Backend

```
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
copy .env.example .env            # then fill in the values
python -m alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

The API runs at http://localhost:8000 and its interactive docs are at http://localhost:8000/docs. `JWT_SECRET_KEY` in `.env` must be at least 32 bytes. See `backend/README.md` for the search API, live search settings and loading recipes.

### 3. Frontend

```
cd smart-recipe
npm install
npm run dev
```

The app runs at http://localhost:3000.

### Tests

```
cd backend
python -m pytest
```

The database tests use a separate `smartrecipe_test` database.

## Project layout

- `backend/`: API, services, seed data, scripts and tests
- `smart-recipe/`: Next.js frontend
- `docs/`: project documents
- `testing/`: manual testing records
- `docker-compose.yml`: local PostgreSQL