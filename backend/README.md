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
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime, 1–1440 minutes; default 30 |

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

Seeding is optional and idempotent. Schema changes remain managed by Alembic;
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
