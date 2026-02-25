# backend/tests/test_system.py
"""System routes: health, logs, usage, settings; accountant agent (usage ledger)."""
import pytest
import sqlite3
from unittest.mock import patch


@pytest.mark.asyncio
async def test_health_endpoint_redis_available(async_client, mock_redis):
    """GET /api/health returns 200 with status online and redis_ok True when Redis is up."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["system"] == "Apex Kernel"
    assert "loaded_agents" in data
    assert isinstance(data["loaded_agents"], list)
    assert data.get("redis_ok") is True
    assert data.get("database_ok") is True


@pytest.mark.asyncio
async def test_health_endpoint_redis_unavailable(async_client, mock_redis_unavailable):
    """GET /api/health still 200 when Redis unavailable; redis_ok False."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "loaded_agents" in data
    assert data.get("redis_ok") is False


@pytest.mark.asyncio
async def test_health_database_ok(async_client, mock_redis, temp_db):
    """Health reflects database_ok when DB is available."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            response = await async_client.get("/api/health")
            assert response.status_code == 200
            assert response.json().get("database_ok") is True


@pytest.mark.asyncio
async def test_logs_requires_auth(async_client):
    """GET /api/logs without auth returns 401."""
    r = await async_client.get("/api/logs")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logs_success(async_client, auth_headers):
    """GET /api/logs with auth returns 200 (logs may be empty)."""
    r = await async_client.get("/api/logs", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "logs" in data
    assert "total_lines" in data


@pytest.mark.asyncio
async def test_usage_requires_auth(async_client):
    """GET /api/usage without auth returns 401."""
    r = await async_client.get("/api/usage")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_usage_success(async_client, auth_headers):
    """GET /api/usage with auth returns 200 and usage list."""
    r = await async_client.get("/api/usage", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "usage" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_usage_403_when_project_not_owned(async_client, auth_headers, temp_db, test_user):
    """GET /api/usage?project_id=other_project returns 403 when user does not own project."""
    r = await async_client.get(
        "/api/usage",
        params={"project_id": "other_project"},
        headers=auth_headers,
    )
    assert r.status_code == 403
    assert "access denied" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_settings_requires_auth(async_client):
    """GET /api/settings without auth returns 401."""
    r = await async_client.get("/api/settings")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_settings_success(async_client, auth_headers):
    """GET /api/settings with auth returns 200."""
    r = await async_client.get("/api/settings", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_accountant_writes_to_usage_ledger(
    async_client, temp_db, test_user, test_project
):
    """POST /api/run task=log_usage writes to usage_ledger and returns cost_logged."""
    temp_db.create_usage_table_if_not_exists()
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.kernel.memory", temp_db):
                with patch("backend.core.auth.memory", temp_db):
                    with patch(
                        "backend.modules.system_ops.agents.accountant.memory", temp_db
                    ):
                        temp_db.create_usage_table_if_not_exists()
                        auth_r = await async_client.post(
                            "/api/auth/verify",
                            json={
                                "email": test_user["email"],
                                "password": test_user["password"],
                            },
                        )
                        assert auth_r.status_code == 200
                        token = auth_r.json()["token"]
                        response = await async_client.post(
                            "/api/run",
                            json={
                                "task": "log_usage",
                                "params": {
                                    "project_id": test_project["project_id"],
                                    "resource": "twilio_voice",
                                    "quantity": 10,
                                },
                            },
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert response.status_code == 200
                        data = response.json()
                        assert data["status"] == "success"
                        assert "data" in data
                        assert "cost_logged" in data["data"]
                        conn = sqlite3.connect(temp_db.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT * FROM usage_ledger WHERE project_id = ?",
                            (test_project["project_id"],),
                        )
                        rows = cursor.fetchall()
                        conn.close()
                        assert len(rows) == 1
                        row = rows[0]
                        assert row[1] == test_project["project_id"]
                        assert row[2] == "twilio_voice"
                        assert row[3] == 10.0
                        assert row[4] == 0.5
                        assert data["data"]["cost_logged"] == 0.5
