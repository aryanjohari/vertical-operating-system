"""
Deployment tests: root and health endpoints.

Validates that the Railway backend is up and that PostgreSQL and Redis
(Railway Postgres + Railway Redis) are reported healthy.
"""

import pytest


@pytest.mark.deployment
def test_root_returns_200(api_base_url, http_client):
    """GET / returns 200 and system info."""
    r = http_client.get(f"{api_base_url}/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "online"
    assert "system" in data
    assert "version" in data
    assert "loaded_agents" in data


@pytest.mark.deployment
def test_health_returns_200(api_base_url, http_client):
    """GET /health returns 200."""
    r = http_client.get(f"{api_base_url}/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "online"


@pytest.mark.deployment
def test_api_health_includes_redis_and_database(api_base_url, http_client):
    """
    GET /api/health returns redis_ok and database_ok.
    On Railway deployment these should be True (Railway Postgres + Railway Redis).
    """
    r = http_client.get(f"{api_base_url}/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "online"
    assert "redis_ok" in data
    assert "database_ok" in data
    assert data["redis_ok"] is True, "Railway Redis should be connected"
    assert data["database_ok"] is True, "Railway PostgreSQL should be connected"
