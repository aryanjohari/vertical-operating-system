# backend/tests/test_core.py
import pytest
import jwt
import os
import sqlite3
from unittest.mock import patch, MagicMock
import backend.core.auth as auth_module


@pytest.mark.asyncio
async def test_auth_login_and_token(async_client, temp_db, test_user):
    """Test authentication: login and get JWT token."""
    # Patch the global memory instance to use our test DB
    with patch('backend.core.memory.memory', temp_db):
        with patch('backend.main.memory', temp_db):
            with patch('backend.core.auth.memory', temp_db):
                # Test login
                response = await async_client.post(
                    "/api/auth/verify",
                    json={
                        "email": test_user["email"],
                        "password": test_user["password"]
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["user_id"] == test_user["user_id"]
                assert "token" in data
                assert data["token"] is not None
                
                # Verify token can be decoded
                token = data["token"]
                payload = jwt.decode(token, auth_module.JWT_SECRET, algorithms=[auth_module.JWT_ALGORITHM])
                assert payload["user_id"] == test_user["user_id"]


@pytest.mark.asyncio
async def test_health_endpoint(async_client, mock_redis):
    """Test health endpoint with Redis available."""
    response = await async_client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["system"] == "Apex Kernel"
    assert "loaded_agents" in data
    assert isinstance(data["loaded_agents"], list)


@pytest.mark.asyncio
async def test_health_endpoint_redis_unavailable(async_client, mock_redis_unavailable):
    """Test health endpoint when Redis is unavailable."""
    response = await async_client.get("/api/health")
    
    # Health endpoint should still work even if Redis is unavailable
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "loaded_agents" in data


@pytest.mark.asyncio
async def test_accountant_writes_to_usage_ledger(async_client, temp_db, test_user, test_project):
    """Test that AccountantAgent writes to usage_ledger table."""
    # Ensure usage_ledger table exists
    temp_db.create_usage_table_if_not_exists()
    
    # Patch memory (including auth)
    with patch('backend.core.memory.memory', temp_db):
        with patch('backend.main.memory', temp_db):
            with patch('backend.core.kernel.memory', temp_db):
                with patch('backend.core.auth.memory', temp_db):
                    with patch('backend.modules.system_ops.agents.accountant.memory', temp_db):
                        # Get auth token
                        auth_response = await async_client.post(
                            "/api/auth/verify",
                            json={
                                "email": test_user["email"],
                                "password": test_user["password"]
                            }
                        )
                        assert auth_response.status_code == 200
                        auth_data = auth_response.json()
                        assert auth_data["success"] is True
                        assert "token" in auth_data
                        token = auth_data["token"]
                        
                        # Trigger log_usage task
                        response = await async_client.post(
                            "/api/run",
                            json={
                                "task": "log_usage",
                                "params": {
                                    "project_id": test_project["project_id"],
                                    "resource": "twilio_voice",
                                    "quantity": 10
                                }
                            },
                            headers={"Authorization": f"Bearer {token}"}
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["status"] == "success"
                        assert "data" in data
                        assert "cost_logged" in data["data"]
                        
                        # Verify record was written to usage_ledger table
                        conn = sqlite3.connect(temp_db.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT * FROM usage_ledger WHERE project_id = ?",
                            (test_project["project_id"],)
                        )
                        rows = cursor.fetchall()
                        conn.close()
                        
                        assert len(rows) == 1
                        row = rows[0]
                        # Row structure: (id, project_id, resource_type, quantity, cost_usd, timestamp)
                        assert row[1] == test_project["project_id"]  # project_id
                        assert row[2] == "twilio_voice"  # resource_type
                        assert row[3] == 10.0  # quantity
                        assert row[4] == 0.5  # cost_usd (10 * 0.05)
                        
                        # Verify cost_logged matches
                        assert data["data"]["cost_logged"] == 0.5
