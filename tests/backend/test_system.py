"""
Deployment tests: system endpoints (logs, usage, settings).

These require auth; they are run only when auth_headers is available.
"""

import pytest


@pytest.mark.deployment
def test_api_settings_requires_auth(api_base_url, http_client):
    """GET /api/settings without token returns 401."""
    r = http_client.get(f"{api_base_url}/api/settings")
    assert r.status_code == 401


@pytest.mark.deployment
def test_api_settings_with_auth(api_base_url, http_client, auth_headers):
    """GET /api/settings with valid token returns 200."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured (DEPLOYMENT_TEST_USER_*)")
    r = http_client.get(f"{api_base_url}/api/settings", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "wp_url" in data
    assert "wp_user" in data


@pytest.mark.deployment
def test_api_logs_requires_auth(api_base_url, http_client):
    """GET /api/logs without token returns 401."""
    r = http_client.get(f"{api_base_url}/api/logs")
    assert r.status_code == 401


@pytest.mark.deployment
def test_api_logs_with_auth(api_base_url, http_client, auth_headers):
    """GET /api/logs with valid token returns 200 and logs array."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(f"{api_base_url}/api/logs", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)


@pytest.mark.deployment
def test_api_usage_requires_auth(api_base_url, http_client):
    """GET /api/usage without token returns 401."""
    r = http_client.get(f"{api_base_url}/api/usage")
    assert r.status_code == 401


@pytest.mark.deployment
def test_api_usage_with_auth(api_base_url, http_client, auth_headers):
    """GET /api/usage with valid token returns 200 and usage array."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(f"{api_base_url}/api/usage", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "usage" in data
    assert "total" in data
