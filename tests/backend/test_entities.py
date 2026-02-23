"""
Deployment tests: entities and leads endpoints.

GET/POST /api/entities, PUT/DELETE /api/entities/{id}, GET/POST /api/leads.
"""

import pytest


@pytest.mark.deployment
def test_api_entities_list_requires_auth(api_base_url, http_client):
    """GET /api/entities without token returns 401."""
    r = http_client.get(f"{api_base_url}/api/entities")
    assert r.status_code == 401


@pytest.mark.deployment
def test_api_entities_list_with_auth(api_base_url, http_client, auth_headers):
    """GET /api/entities with valid token returns 200."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(
        f"{api_base_url}/api/entities",
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "entities" in data
    assert isinstance(data["entities"], list)


@pytest.mark.deployment
def test_api_leads_list_requires_auth(api_base_url, http_client):
    """GET /api/leads without token returns 401."""
    r = http_client.get(f"{api_base_url}/api/leads")
    assert r.status_code == 401


@pytest.mark.deployment
def test_api_leads_list_with_auth(api_base_url, http_client, auth_headers):
    """GET /api/leads with valid token returns 200."""
    if auth_headers is None:
        pytest.skip("Auth credentials not configured")
    r = http_client.get(f"{api_base_url}/api/leads", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "leads" in data
    assert isinstance(data["leads"], list)
