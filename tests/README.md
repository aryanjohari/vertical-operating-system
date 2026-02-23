# Deployment-level tests

These tests run against **live deployments** (Railway backend + optional Vercel frontend). They verify endpoints, connectivity to **Railway PostgreSQL** and **Railway Redis**, and that the frontend is reachable on Vercel.

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

- **Unit tests** (mocked DB/Redis): `pytest backend/tests/ -v`
- **Deployment tests** (real Railway + Vercel): `pytest tests/ -v` with `API_BASE_URL` (and optionally `FRONTEND_URL`) set.
