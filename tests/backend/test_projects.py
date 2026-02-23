"""
Deployment tests: project and campaign endpoints.

GET/POST /api/projects, project DNA, analytics, campaigns.
Requires auth.
"""

import pytest


@pytest.mark.deployment
def test_api_projects_list_requires_auth(api_base_url, http_client):
    """GET /api/projects without token returns 401."""
    r = http_client.get(f"{api_base_url}/api/projects")
    assert r.status_code == 401


@pytest.mark.deployment
def test_api_projects_list_with_auth(api_base_url, http_client, auth_headers):
    """GET /api/projects with valid token returns 200 and list."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(f"{api_base_url}/api/projects", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "projects" in data
    assert isinstance(data["projects"], list)


@pytest.mark.deployment
def test_api_schemas_profile(api_base_url, http_client, auth_headers):
    """GET /api/schemas/profile returns 200 (auth required)."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(f"{api_base_url}/api/schemas/profile", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.deployment
def test_api_schemas_campaign_pseo(api_base_url, http_client, auth_headers):
    """GET /api/schemas/campaign/pseo returns 200."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(
        f"{api_base_url}/api/schemas/campaign/pseo",
        headers=auth_headers,
    )
    assert r.status_code == 200


@pytest.mark.deployment
def test_api_schemas_campaign_lead_gen(api_base_url, http_client, auth_headers):
    """GET /api/schemas/campaign/lead_gen returns 200."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(
        f"{api_base_url}/api/schemas/campaign/lead_gen",
        headers=auth_headers,
    )
    assert r.status_code == 200
