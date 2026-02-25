# backend/tests/test_entities.py
"""Entities and leads routes: GET/POST/PUT/DELETE entities, GET/POST leads; 403/404/500 paths."""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_entities_requires_auth(async_client):
    """GET /api/entities without auth returns 401."""
    r = await async_client.get("/api/entities")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_entities_success(async_client, auth_headers):
    """GET /api/entities returns 200 and list of entities."""
    r = await async_client.get("/api/entities", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "entities" in data
    assert isinstance(data["entities"], list)


@pytest.mark.asyncio
async def test_get_entities_403_when_project_not_owned(async_client, auth_headers):
    """GET /api/entities?project_id=other returns 403 when user does not own project."""
    r = await async_client.get(
        "/api/entities",
        params={"project_id": "other_project"},
        headers=auth_headers,
    )
    assert r.status_code == 403
    assert "access denied" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_create_entity_success(async_client, auth_headers, temp_db, test_project):
    """POST /api/entities with valid payload creates entity and returns 200."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.entities.memory", temp_db):
                    r = await async_client.post(
                        "/api/entities",
                        json={
                            "entity_type": "seo_keyword",
                            "name": "test keyword",
                            "project_id": test_project["project_id"],
                        },
                        headers=auth_headers,
                    )
                    assert r.status_code == 200
                    data = r.json()
                    assert data.get("success") is True
                    assert "entity" in data
                    assert data["entity"]["entity_type"] == "seo_keyword"


@pytest.mark.asyncio
async def test_create_entity_403_when_project_not_owned(async_client, auth_headers):
    """POST /api/entities with project_id user does not own returns 403."""
    r = await async_client.post(
        "/api/entities",
        json={
            "entity_type": "seo_keyword",
            "name": "x",
            "project_id": "other_project",
        },
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_put_entity_404_when_not_found(async_client, auth_headers):
    """PUT /api/entities/nonexistent_id returns 404."""
    r = await async_client.put(
        "/api/entities/nonexistent_entity_id_123",
        json={"name": "Updated"},
        headers=auth_headers,
    )
    assert r.status_code == 404
    assert "not found" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_delete_entity_404_when_not_found(async_client, auth_headers):
    """DELETE /api/entities/nonexistent_id returns 404."""
    r = await async_client.delete(
        "/api/entities/nonexistent_entity_id_123",
        headers=auth_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_entity_success(async_client, auth_headers, temp_db, test_project):
    """DELETE /api/entities/{id} returns 200 when entity exists and belongs to user."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.entities.memory", temp_db):
                    create_r = await async_client.post(
                        "/api/entities",
                        json={
                            "entity_type": "seo_keyword",
                            "name": "to delete",
                            "project_id": test_project["project_id"],
                        },
                        headers=auth_headers,
                    )
                    assert create_r.status_code == 200
                    entity_id = create_r.json()["entity"]["id"]
                    del_r = await async_client.delete(
                        f"/api/entities/{entity_id}",
                        headers=auth_headers,
                    )
                    assert del_r.status_code == 200
                    assert del_r.json().get("success") is True


@pytest.mark.asyncio
async def test_post_leads_403_when_project_not_owned(async_client, auth_headers):
    """POST /api/leads with project_id user does not own returns 403."""
    r = await async_client.post(
        "/api/leads",
        json={
            "project_id": "other_project",
            "source": "web",
            "data": {"email": "a@b.com"},
        },
        headers=auth_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_post_leads_success(async_client, auth_headers, temp_db, test_project):
    """POST /api/leads with valid payload returns 200 and lead_id."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.routers.entities.memory", temp_db):
                    r = await async_client.post(
                        "/api/leads",
                        json={
                            "project_id": test_project["project_id"],
                            "source": "contact_form",
                            "data": {"email": "lead@example.com", "name": "Lead"},
                        },
                        headers=auth_headers,
                    )
                    assert r.status_code == 200
                    data = r.json()
                    assert data.get("success") is True
                    assert "lead_id" in data


@pytest.mark.asyncio
async def test_get_leads_requires_auth(async_client):
    """GET /api/leads without auth returns 401."""
    r = await async_client.get("/api/leads")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_leads_success(async_client, auth_headers):
    """GET /api/leads returns 200 and list of leads."""
    r = await async_client.get("/api/leads", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "leads" in data
    assert isinstance(data["leads"], list)
