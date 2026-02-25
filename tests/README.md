# Deployment-level tests

These tests run against **live deployments** (Railway backend + optional Vercel frontend). They verify endpoints, connectivity to **Railway PostgreSQL** and **Railway Redis**, and that the frontend is reachable on Vercel.

## Test directory layout

- **`backend/tests/`** — Unit/integration tests (mocked DB, Redis, LLM). Run with `pytest backend/tests/` or `make test`. Do not remove; this is the main test suite for pre-deploy.
- **`tests/`** (this folder) — Deployment/smoke tests (live Railway + Vercel). Run with `pytest tests/` or `make test-deploy`. Keep both directories; they serve different purposes.

**Run all test commands from the repository root** so `pytest.ini` and `pythonpath` resolve correctly and imports like `backend.core.models` work.

## Single-command test runs (Makefile)

From the project root you can run:

| Command | Description |
|---------|-------------|
| `make test` or `make test-unit` | Run **unit tests** only (`pytest backend/tests/ -v`). No env vars required. |
| `make test-deploy` | Run **deployment tests** only. Requires `API_BASE_URL`. Optionally set `FRONTEND_URL`, `DEPLOYMENT_TEST_USER_EMAIL`, `DEPLOYMENT_TEST_USER_PASSWORD`. |
| `make test-all` | Run unit tests, then deployment tests if `API_BASE_URL` is set. If not set, prints a note and skips deployment. |

Example:

```bash
make test
export API_BASE_URL=https://your-backend.railway.app
make test-deploy
# Or run both (unit first, then deploy if API_BASE_URL set):
make test-all
```

## Prerequisites

- Python env with project dependencies: `pip install -r requirements.txt`
- Backend deployed on **Railway** (with Railway Postgres and Railway Redis)
- Optional: frontend deployed on **Vercel**

## Environment variables

Set before running deployment tests:

| Variable | Required | Description |
|----------|----------|-------------|
| `API_BASE_URL` | Yes (for backend tests) | Backend URL, e.g. `https://your-app.railway.app` |
| `FRONTEND_URL` | No (for frontend tests) | Vercel app URL, e.g. `https://your-app.vercel.app` |
| `DEPLOYMENT_TEST_USER_EMAIL` | No | Email for auth tests (login, protected endpoints) |
| `DEPLOYMENT_TEST_USER_PASSWORD` | No | Password for the above user |

You can use a `.env` in the project root; `tests/conftest.py` loads it via `dotenv`.

## Run all deployment tests

From the project root:

```bash
# Backend only (requires API_BASE_URL)
export API_BASE_URL=https://your-backend.railway.app
pytest tests/ -v

# Backend + frontend (also set FRONTEND_URL for Vercel smoke tests)
export API_BASE_URL=https://your-backend.railway.app
export FRONTEND_URL=https://your-app.vercel.app
pytest tests/ -v

# With auth (to test protected endpoints)
export API_BASE_URL=https://your-backend.railway.app
export DEPLOYMENT_TEST_USER_EMAIL=you@example.com
export DEPLOYMENT_TEST_USER_PASSWORD=yourpassword
pytest tests/ -v
```

## Run only backend or only frontend

```bash
# Backend deployment tests only
pytest tests/backend/ -v

# Frontend (Vercel) deployment tests only (requires FRONTEND_URL)
pytest tests/frontend/ -v
```

## Run by marker

```bash
pytest tests/ -v -m deployment
```

## What is tested

### Backend (Railway)

- **Health**: `GET /`, `GET /health`, `GET /api/health` — including `redis_ok` and `database_ok` (Railway Redis + Railway Postgres).
- **Auth**: `POST /api/auth/verify`, `POST /api/auth/register`.
- **System**: `GET /api/settings`, `GET /api/logs`, `GET /api/usage` (with auth).
- **Projects**: `GET /api/projects`, schemas (`/api/schemas/profile`, etc.).
- **Entities & leads**: `GET /api/entities`, `GET /api/leads` (with auth).
- **Agents**: `POST /api/run`, `GET /api/context/{id}` (auth; context uses Redis).
- **Voice & webhooks**: `POST /api/voice/connect`, `/api/voice/incoming`, `/api/voice/status`, `POST /api/webhooks/google-ads`, `POST /api/webhooks/wordpress`.

### Frontend (Vercel)

- `GET /` and `GET /login` return 200 or expected redirect.

## Unit tests vs deployment tests

- **Unit tests** (mocked DB/Redis/LLM): `pytest backend/tests/ -v` or `make test`. Cover auth, system, projects, schemas, entities, agents, voice, webhooks with validation and error paths. No `API_BASE_URL` needed.
- **Deployment tests** (real Railway + Vercel): `pytest tests/ -v` or `make test-deploy` with `API_BASE_URL` (and optionally `FRONTEND_URL`) set. Catch deployment-related errors: connectivity, env (e.g. `DATABASE_URL`, `REDIS_URL`), and critical paths. Assert `GET /api/health` returns `database_ok` and `redis_ok` to verify Railway Postgres/Redis.
