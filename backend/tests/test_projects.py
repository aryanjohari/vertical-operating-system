# backend/tests/test_projects.py
"""Projects routes: CRUD, DNA, analytics, campaigns; success and 400/403/404/500 paths."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.core.models import AgentOutput


@pytest.mark.asyncio
async def test_get_projects_requires_auth(async_client):
    """GET /api/projects without auth returns 401."""
    r = await async_client.get("/api/projects")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_projects_success(async_client, auth_headers):
    """GET /api/projects returns 200 and list of projects."""
    r = await async_client.get("/api/projects", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "projects" in data
    assert isinstance(data["projects"], list)


@pytest.mark.asyncio
async def test_create_project_simple_success(async_client, auth_headers):
    """POST /api/projects with name and niche creates project and returns 200."""
    r = await async_client.post(
        "/api/projects",
        json={"name": "My Business", "niche": "fitness"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "project_id" in data
    assert "fitness" in data["project_id"].lower() or data["project_id"]


@pytest.mark.asyncio
async def test_create_project_400_missing_name_niche(async_client, auth_headers):
    """POST /api/projects without name/niche (and no profile) returns 400."""
    r = await async_client.post(
        "/api/projects",
        json={},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "name" in r.json().get("detail", "").lower() or "niche" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_create_project_requires_auth(async_client):
    """POST /api/projects without auth returns 401."""
    r = await async_client.post(
        "/api/projects",
        json={"name": "X", "niche": "y"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_dna_403_when_not_owner(async_client, auth_headers):
    """GET /api/projects/other_project/dna returns 403 when user does not own project."""
    r = await async_client.get(
        "/api/projects/other_project/dna",
        headers=auth_headers,
    )
    assert r.status_code == 403
    assert "access denied" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_get_dna_404_when_config_missing(async_client, auth_headers, temp_db, test_project):
    """GET /api/projects/{id}/dna returns 404 when config loader returns error."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.projects.memory", temp_db):
                    mock_loader = MagicMock()
                    mock_loader.load.return_value = {"error": "Config not found"}
                    with patch(
                        "backend.routers.projects.ConfigLoader",
                        return_value=mock_loader,
                    ):
                        r = await async_client.get(
                            f"/api/projects/{test_project['project_id']}/dna",
                            headers=auth_headers,
                        )
                        assert r.status_code == 404


@pytest.mark.asyncio
async def test_analytics_snapshot_403(async_client, auth_headers):
    """GET analytics/snapshot for non-owned project returns 403."""
    r = await async_client.get(
        "/api/projects/other_project/analytics/snapshot",
        params={"module": "pseo"},
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_analytics_snapshot_400_invalid_module(async_client, auth_headers, temp_db, test_project):
    """GET analytics/snapshot with invalid module returns 400."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.projects.memory", temp_db):
                    r = await async_client.get(
                        f"/api/projects/{test_project['project_id']}/analytics/snapshot",
                        params={"module": "invalid"},
                        headers=auth_headers,
                    )
                    assert r.status_code == 400
                    assert "module" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_get_campaigns_403(async_client, auth_headers):
    """GET /api/projects/other_project/campaigns returns 403."""
    r = await async_client.get(
        "/api/projects/other_project/campaigns",
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_campaigns_success(async_client, auth_headers, temp_db, test_project):
    """GET /api/projects/{id}/campaigns returns 200 and list."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.projects.memory", temp_db):
                    r = await async_client.get(
                        f"/api/projects/{test_project['project_id']}/campaigns",
                        headers=auth_headers,
                    )
                    assert r.status_code == 200
                    assert "campaigns" in r.json()


@pytest.mark.asyncio
async def test_create_campaign_403(async_client, auth_headers):
    """POST /api/projects/other_project/campaigns returns 403."""
    r = await async_client.post(
        "/api/projects/other_project/campaigns",
        json={"module": "pseo", "form_data": {"name": "Camp"}},
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_campaign_400_invalid_module(async_client, auth_headers, temp_db, test_project):
    """POST create campaign with module not pseo/lead_gen returns 400."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.projects.memory", temp_db):
                    r = await async_client.post(
                        f"/api/projects/{test_project['project_id']}/campaigns",
                        json={"module": "other", "form_data": {"name": "C"}},
                        headers=auth_headers,
                    )
                    assert r.status_code == 400
                    assert "module" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_create_campaign_400_missing_form_data(async_client, auth_headers, temp_db, test_project):
    """POST create campaign without form_data returns 400."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.projects.memory", temp_db):
                    r = await async_client.post(
                        f"/api/projects/{test_project['project_id']}/campaigns",
                        json={"module": "pseo", "name": "C"},
                        headers=auth_headers,
                    )
                    assert r.status_code == 400
                    assert "form_data" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_create_campaign_success(async_client, auth_headers, temp_db, test_project, mock_llm_gateway):
    """POST create campaign with valid payload returns 200 and campaign_id (kernel mocked)."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.projects.memory", temp_db):
                    with patch("backend.routers.projects.kernel") as mock_kernel:
                        mock_kernel.dispatch = AsyncMock(
                            return_value=AgentOutput(
                                status="success",
                                data={"campaign_id": "cmp_test123"},
                                message="OK",
                            )
                        )
                        r = await async_client.post(
                            f"/api/projects/{test_project['project_id']}/campaigns",
                            json={
                                "module": "pseo",
                                "name": "Test Campaign",
                                "form_data": {"site_url": "https://example.com"},
                            },
                            headers=auth_headers,
                        )
                        assert r.status_code == 200
                        data = r.json()
                        assert data.get("success") is True
                        assert data.get("campaign_id") == "cmp_test123"


@pytest.mark.asyncio
async def test_get_campaign_404(async_client, auth_headers, temp_db, test_project):
    """GET /api/projects/{id}/campaigns/nonexistent returns 404."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.projects.memory", temp_db):
                    r = await async_client.get(
                        f"/api/projects/{test_project['project_id']}/campaigns/nonexistent_campaign",
                        headers=auth_headers,
                    )
                    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_campaign_400_no_config(async_client, auth_headers, temp_db, test_project):
    """PATCH campaign without config or config_partial returns 400."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.projects.memory", temp_db):
                    r = await async_client.patch(
                        f"/api/projects/{test_project['project_id']}/campaigns/some_campaign",
                        json={},
                        headers=auth_headers,
                    )
                    assert r.status_code in (400, 404)
