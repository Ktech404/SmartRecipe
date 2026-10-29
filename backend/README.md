# Backend: Database

Requires Docker Desktop and Python 3.10+.

## Setup

```bash
docker compose up -d                  # Postgres on port 5433
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose exec db psql -U smartrecipe -c "CREATE DATABASE smartrecipe_test;"
alembic upgrade head                  # create tables
python -m scripts.seed                # load starter data (safe to re-run)
```

## Tests

```bash
cd backend && pytest -v
```

Tests run against the `smartrecipe_test` database using the real migration.
