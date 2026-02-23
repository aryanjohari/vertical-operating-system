"""
Deployment tests: Vercel frontend pages.

Smoke tests that key pages return 200 or expected redirects.
Run with FRONTEND_URL set to your Vercel app URL.
"""

import pytest


@pytest.mark.deployment
def test_frontend_root_returns_ok(frontend_url, http_client):
    """GET / returns 200 or 307/308 redirect (e.g. to login)."""
    r = http_client.get(frontend_url, follow_redirects=False)
    assert r.status_code in (200, 307, 308, 301, 302)


@pytest.mark.deployment
def test_frontend_login_page(frontend_url, http_client):
    """GET /login returns 200."""
    r = http_client.get(f"{frontend_url}/login", follow_redirects=False)
    assert r.status_code == 200


@pytest.mark.deployment
def test_frontend_static_asset_or_api_ready(frontend_url, http_client):
    """Frontend is reachable (same as root)."""
    r = http_client.get(frontend_url, follow_redirects=True)
    assert r.status_code == 200
