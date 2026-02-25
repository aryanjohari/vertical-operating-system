# backend/tests/test_schemas.py
"""Schema routes: profile, campaign pseo, lead_gen; success and 500 on missing template."""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_profile_schema_requires_auth(async_client):
    """GET /api/schemas/profile without auth returns 401."""
    r = await async_client.get("/api/schemas/profile")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_schema_success(async_client, auth_headers):
    """GET /api/schemas/profile returns 200 with schema and defaults."""
    r = await async_client.get("/api/schemas/profile", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "schema" in data
    assert "defaults" in data


@pytest.mark.asyncio
async def test_get_profile_schema_500_when_template_missing(async_client, auth_headers):
    """GET /api/schemas/profile returns 500 when template file is missing."""
    with patch("backend.routers.schemas.load_yaml_template", side_effect=FileNotFoundError("Not found")):
        r = await async_client.get("/api/schemas/profile", headers=auth_headers)
        assert r.status_code == 500
        assert "template" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_get_pseo_schema_requires_auth(async_client):
    """GET /api/schemas/campaign/pseo without auth returns 401."""
    r = await async_client.get("/api/schemas/campaign/pseo")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_pseo_schema_success(async_client, auth_headers):
    """GET /api/schemas/campaign/pseo returns 200."""
    r = await async_client.get("/api/schemas/campaign/pseo", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "schema" in data
    assert "defaults" in data


@pytest.mark.asyncio
async def test_get_pseo_schema_500_when_template_missing(async_client, auth_headers):
    """GET /api/schemas/campaign/pseo returns 500 when template missing."""
    with patch("backend.routers.schemas.load_yaml_template", side_effect=FileNotFoundError("Not found")):
        r = await async_client.get("/api/schemas/campaign/pseo", headers=auth_headers)
        assert r.status_code == 500


@pytest.mark.asyncio
async def test_get_lead_gen_schema_requires_auth(async_client):
    """GET /api/schemas/campaign/lead_gen without auth returns 401."""
    r = await async_client.get("/api/schemas/campaign/lead_gen")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_lead_gen_schema_success(async_client, auth_headers):
    """GET /api/schemas/campaign/lead_gen returns 200."""
    r = await async_client.get("/api/schemas/campaign/lead_gen", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "schema" in data
    assert "defaults" in data


@pytest.mark.asyncio
async def test_get_lead_gen_schema_500_when_template_missing(async_client, auth_headers):
    """GET /api/schemas/campaign/lead_gen returns 500 when template missing."""
    with patch("backend.routers.schemas.load_yaml_template", side_effect=FileNotFoundError("Not found")):
        r = await async_client.get("/api/schemas/campaign/lead_gen", headers=auth_headers)
        assert r.status_code == 500
