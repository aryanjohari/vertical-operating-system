# backend/tests/test_agents.py
"""Agents routes: POST /api/run, GET /api/context/{id}; auth, validation, 403/404/500."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_run_requires_auth(async_client):
    """POST /api/run without auth returns 401."""
    r = await async_client.post(
        "/api/run",
        json={"task": "log_usage", "params": {"project_id": "p", "resource": "x", "quantity": 1}},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_run_success_sync(async_client, auth_headers, temp_db, test_project, mock_llm_gateway):
    """POST /api/run with sync task (e.g. log_usage) returns 200 and status success."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                with patch("backend.core.kernel.memory", temp_db):
                    with patch("backend.modules.system_ops.agents.accountant.memory", temp_db):
                        r = await async_client.post(
                            "/api/run",
                            json={
                                "task": "log_usage",
                                "params": {
                                    "project_id": test_project["project_id"],
                                    "resource": "twilio_voice",
                                    "quantity": 5,
                                },
                            },
                            headers=auth_headers,
                        )
                        assert r.status_code == 200
                        data = r.json()
                        assert data.get("status") in ("success", "processing")
                        if data.get("status") == "success":
                            assert "data" in data


@pytest.mark.asyncio
async def test_run_400_invalid_params(async_client, auth_headers):
    """POST /api/run with params that fail schema validation (e.g. log_usage missing resource/quantity) returns 400 or 200 with status error."""
    r = await async_client.post(
        "/api/run",
        json={
            "task": "log_usage",
            "params": {"project_id": "p"},  # missing required resource, quantity
        },
        headers=auth_headers,
    )
    if r.status_code == 400:
        assert "detail" in r.json()
    else:
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "error" or "detail" in data


@pytest.mark.asyncio
async def test_get_context_requires_auth(async_client):
    """GET /api/context/xxx without auth returns 401."""
    r = await async_client.get("/api/context/some-context-id")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_context_404_when_not_found(async_client, auth_headers, mock_redis):
    """GET /api/context/nonexistent returns 404 when context does not exist."""
    with patch("backend.core.context.context_manager.get_context", return_value=None):
        r = await async_client.get(
            "/api/context/nonexistent-context-id",
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert "not found" in r.json().get("detail", "").lower() or "expired" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_get_context_403_when_other_user(async_client, auth_headers, mock_redis):
    """GET /api/context/{id} returns 403 when context belongs to another user."""
    mock_context = MagicMock()
    mock_context.context_id = "ctx-1"
    mock_context.user_id = "other@example.com"
    mock_context.project_id = "proj"
    mock_context.created_at = datetime.utcnow()
    mock_context.expires_at = datetime.utcnow() + timedelta(hours=1)
    mock_context.data = {}
    with patch("backend.core.context.context_manager.get_context", return_value=mock_context):
        r = await async_client.get(
            "/api/context/ctx-1",
            headers=auth_headers,
        )
        assert r.status_code == 403
        assert "access denied" in r.json().get("detail", "").lower() or "denied" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_get_context_success(async_client, auth_headers, mock_redis):
    """GET /api/context/{id} returns 200 when context exists and belongs to user."""
    mock_context = MagicMock()
    mock_context.context_id = "ctx-1"
    mock_context.user_id = "test@example.com"
    mock_context.project_id = "test_project"
    mock_context.created_at = datetime.utcnow()
    mock_context.expires_at = datetime.utcnow() + timedelta(hours=1)
    mock_context.data = {"status": "completed"}
    with patch("backend.core.context.context_manager.get_context", return_value=mock_context):
        r = await async_client.get(
            "/api/context/ctx-1",
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["context_id"] == "ctx-1"
        assert data["user_id"] == "test@example.com"
        assert "data" in data
