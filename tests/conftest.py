"""
Deployment-level test configuration.

These tests run against live deployments:
- Backend: Railway (API_BASE_URL) — uses Railway PostgreSQL and Railway Redis
- Frontend: Vercel (FRONTEND_URL)

Set env vars before running:
  export API_BASE_URL=https://your-backend.railway.app
  export FRONTEND_URL=https://your-app.vercel.app   # optional, for frontend smoke tests
  export DEPLOYMENT_TEST_USER_EMAIL=test@example.com   # optional, for auth tests
  export DEPLOYMENT_TEST_USER_PASSWORD=yourpassword    # optional

Run: pytest tests/ -v
"""

import os

import pytest
import httpx

# Load .env from project root so API_BASE_URL etc. can be set there
from dotenv import load_dotenv
load_dotenv()


def _get_api_base_url() -> str:
    url = os.getenv("API_BASE_URL", "").rstrip("/")
    if not url:
        pytest.skip(
            "API_BASE_URL not set. Set it to your Railway backend URL to run deployment tests."
        )
    return url


def _get_frontend_url() -> str:
    url = os.getenv("FRONTEND_URL", "").rstrip("/")
    if not url:
        pytest.skip(
            "FRONTEND_URL not set. Set it to your Vercel app URL to run frontend deployment tests."
        )
    return url


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return _get_api_base_url()


@pytest.fixture(scope="session")
def frontend_url() -> str:
    return _get_frontend_url()


@pytest.fixture(scope="session")
def http_client():
    """Sync HTTP client for deployment tests (no transport, real requests)."""
    with httpx.Client(timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def auth_headers(api_base_url, http_client):
    """
    Optional: get Bearer token using DEPLOYMENT_TEST_USER_EMAIL / DEPLOYMENT_TEST_USER_PASSWORD.
    If not set, returns None (tests that need auth will skip or use public endpoints only).
    """
    email = os.getenv("DEPLOYMENT_TEST_USER_EMAIL")
    password = os.getenv("DEPLOYMENT_TEST_USER_PASSWORD")
    if not email or not password:
        return None
    try:
        r = http_client.post(
            f"{api_base_url}/api/auth/verify",
            json={"email": email, "password": password},
        )
        if r.status_code != 200:
            return None
        data = r.json()
        token = data.get("token") if data.get("success") else None
        if not token:
            return None
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        return None
