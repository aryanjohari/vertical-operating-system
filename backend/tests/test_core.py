# backend/tests/test_core.py
"""
Core integration smoke test: auth + health + kernel run in one flow.

Detailed auth tests are in test_auth.py; health and accountant in test_system.py.
This file keeps a single end-to-end smoke test for the core stack (memory, auth, kernel).
"""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_core_smoke_auth_health_run(async_client, temp_db, test_user, test_project, mock_redis):
    """Smoke: login -> health -> POST /api/run (log_usage) returns success with patched memory."""
    temp_db.create_usage_table_if_not_exists()
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.kernel.memory", temp_db):
                with patch("backend.core.auth.memory", temp_db):
                    with patch("backend.modules.system_ops.agents.accountant.memory", temp_db):
                        auth_r = await async_client.post(
                            "/api/auth/verify",
                            json={"email": test_user["email"], "password": test_user["password"]},
                        )
                        assert auth_r.status_code == 200
                        token = auth_r.json()["token"]
                        health_r = await async_client.get("/api/health")
                        assert health_r.status_code == 200
                        run_r = await async_client.post(
                            "/api/run",
                            json={
                                "task": "log_usage",
                                "params": {
                                    "project_id": test_project["project_id"],
                                    "resource": "twilio_voice",
                                    "quantity": 1,
                                },
                            },
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert run_r.status_code == 200
                        assert run_r.json().get("status") == "success"
                        assert "cost_logged" in (run_r.json().get("data") or {})
