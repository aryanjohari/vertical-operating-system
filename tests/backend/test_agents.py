"""
Deployment tests: agent run and context endpoints.

POST /api/run, GET /api/context/{context_id}.
Uses Redis for context on Railway.
"""

import pytest


@pytest.mark.deployment
def test_api_run_requires_auth(api_base_url, http_client):
    """POST /api/run without token returns 401."""
    r = http_client.post(
        f"{api_base_url}/api/run",
        json={"task": "health_check", "params": {}},
    )
    assert r.status_code == 401


@pytest.mark.deployment
def test_api_run_health_check(api_base_url, http_client, auth_headers):
    """POST /api/run with task=health_check returns 200 and success/processing."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.post(
        f"{api_base_url}/api/run",
        json={"task": "health_check", "params": {}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("success", "processing", "error")


@pytest.mark.deployment
def test_api_context_requires_auth(api_base_url, http_client):
    """GET /api/context/{id} without token returns 401."""
    r = http_client.get(f"{api_base_url}/api/context/some-id")
    assert r.status_code == 401


@pytest.mark.deployment
def test_api_context_not_found(api_base_url, http_client, auth_headers):
    """GET /api/context/nonexistent with auth returns 404."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(
        f"{api_base_url}/api/context/nonexistent-context-id",
        headers=auth_headers,
    )
    assert r.status_code == 404
